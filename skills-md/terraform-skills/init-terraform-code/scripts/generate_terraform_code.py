#!/usr/bin/env python3
"""
Generate Terraform code by sending a prompt to Amazon Bedrock (Claude Opus 4.6).
The prompt includes the change request, organizational standards, existing
workspace code, and structural template so the model produces compliant
Terraform files.

Environment variables:
    AWS_REGION            - AWS region for Bedrock (default: us-east-1)
    AWS_ACCESS_KEY_ID     - AWS access key (or use IAM role)
    AWS_SECRET_ACCESS_KEY - AWS secret key (or use IAM role)
    BEDROCK_MODEL_ID      - Bedrock model ID (default: us.anthropic.claude-opus-4-6-20250610)

Usage:
    python3 generate_terraform_code.py \
        --change-request "Create an S3 bucket for application logs" \
        --standards-dir ./standards \
        --workspace-dir ./workspace-repo/infra \
        --output-dir ./generated

Exit codes:
    0 - Code generated successfully
    1 - Generation or validation failed
"""

import argparse
import json
import os
import re
import sys

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

DEFAULT_MODEL_ID = "us.anthropic.claude-opus-4-6-20250610"
MAX_TOKENS = 16384


# ---------------------------------------------------------------------------
# Context gathering
# ---------------------------------------------------------------------------

def load_standards(standards_dir: str) -> dict[str, str]:
    """Load all .md standard files from the standards directory."""
    standards = {}

    if not os.path.isdir(standards_dir):
        print(f"WARNING: Standards directory '{standards_dir}' not found.", file=sys.stderr)
        return standards

    for filename in sorted(os.listdir(standards_dir)):
        if not filename.endswith(".md"):
            continue
        filepath = os.path.join(standards_dir, filename)
        with open(filepath) as f:
            standards[filename] = f.read()
        print(f"  Loaded: {filename}")

    if not standards:
        print(f"WARNING: No .md files found in {standards_dir}", file=sys.stderr)

    return standards


def read_existing_code(workspace_dir: str) -> dict[str, str]:
    """Read all .tf files from the workspace directory."""
    existing_files = {}

    if not workspace_dir or not os.path.isdir(workspace_dir):
        print(f"  Workspace directory not found. Starting from scratch.")
        return existing_files

    for filename in sorted(os.listdir(workspace_dir)):
        if not filename.endswith(".tf"):
            continue
        filepath = os.path.join(workspace_dir, filename)
        with open(filepath) as f:
            existing_files[filename] = f.read()
        print(f"  Read: {filename}")

    return existing_files


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a Terraform code generator. You produce production-ready Terraform \
code that strictly follows organizational standards and best practices.

Rules:
- Output ONLY Terraform code blocks. No explanations outside code blocks.
- Each file must be wrapped in a fenced code block with the filename as label:
  ```hcl filename="main.tf"
  ... code ...
  ```
- Generate all required files defined in the structure standard.
- Follow the naming conventions, tagging requirements, and best practices exactly.
- If existing code is provided, extend it without breaking current resources.
- Use variables for all configurable values.
- Include meaningful descriptions on all variables and outputs.
"""


def build_prompt(change_request: str, standards: dict[str, str], existing_files: dict[str, str]) -> str:
    """Build the user prompt with all context for Bedrock."""
    sections = []

    # Change request
    sections.append(f"## Change Request\n{change_request}")

    # Standards — include all .md files from the standards directory
    if standards:
        for filename, content in standards.items():
            label = filename.replace(".md", "").replace("_", " ").title()
            sections.append(f"## Standard: {label} ({filename})\n{content}")
    else:
        sections.append("## Standards\nNo standards provided.")

    # Existing code
    if existing_files:
        code_section = "## Existing Workspace Code\n"
        for filename, content in existing_files.items():
            code_section += f"```hcl filename=\"{filename}\"\n{content}\n```\n\n"
        sections.append(code_section)
    else:
        sections.append("## Existing Workspace Code\nNo existing code. This is a new workspace.")

    # Instruction
    sections.append(
        "## Instructions\n"
        "Generate all required Terraform files for the change request above.\n"
        "Each file must be in a separate fenced code block with `filename=\"<name>\"` label.\n"
        "Follow the structure, requirements, and best practices exactly."
    )

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Bedrock invocation
# ---------------------------------------------------------------------------

def invoke_bedrock(prompt: str, region: str, model_id: str) -> str:
    """Send the prompt to Amazon Bedrock and return the response text."""
    try:
        client = boto3.client("bedrock-runtime", region_name=region)
    except NoCredentialsError:
        print("ERROR: AWS credentials not configured.", file=sys.stderr)
        sys.exit(1)

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": prompt},
        ],
    })

    try:
        print(f"  Calling Bedrock model: {model_id} ...")
        response = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )

        response_body = json.loads(response["body"].read())
        output_text = ""
        for block in response_body.get("content", []):
            if block.get("type") == "text":
                output_text += block["text"]

        stop_reason = response_body.get("stop_reason", "unknown")
        usage = response_body.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        print(f"  Bedrock response: stop_reason={stop_reason}, input_tokens={input_tokens}, output_tokens={output_tokens}")

        return output_text

    except ClientError as e:
        print(f"ERROR: Bedrock invocation failed: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def parse_response(response_text: str) -> dict[str, str]:
    """Parse fenced code blocks from the model response into files."""
    files = {}

    # Match ```hcl filename="<name>" ... ``` blocks
    pattern = r'```(?:hcl|terraform)\s+filename="([^"]+)"\s*\n(.*?)```'
    matches = re.findall(pattern, response_text, re.DOTALL)

    for filename, content in matches:
        filename = filename.strip()
        files[filename] = content.strip() + "\n"

    if not files:
        # Fallback: try generic code blocks with filename comment on first line
        pattern = r'```(?:hcl|terraform)?\s*\n#\s*filename:\s*(\S+)\s*\n(.*?)```'
        matches = re.findall(pattern, response_text, re.DOTALL)
        for filename, content in matches:
            files[filename] = content.strip() + "\n"

    return files


# ---------------------------------------------------------------------------
# Write & validate
# ---------------------------------------------------------------------------

def write_files(files: dict[str, str], output_dir: str):
    """Write parsed files to the output directory."""
    os.makedirs(output_dir, exist_ok=True)
    for filename, content in files.items():
        filepath = os.path.join(output_dir, filename)
        # Create subdirectories if filename contains path separators
        os.makedirs(os.path.dirname(filepath), exist_ok=True) if os.path.dirname(filepath) else None
        with open(filepath, "w") as f:
            f.write(content)
        print(f"  Written: {filename}")


def validate_structure(output_dir: str) -> bool:
    """Validate generated code contains essential Terraform files."""
    required_files = ["main.tf", "variables.tf", "outputs.tf", "providers.tf", "versions.tf"]

    missing = []
    for filename in required_files:
        if not os.path.exists(os.path.join(output_dir, filename)):
            missing.append(filename)

    if missing:
        print(f"WARNING: Generated code is missing files: {', '.join(missing)}", file=sys.stderr)
        return False

    print("PASS: Generated code matches required structure.")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate Terraform code via Amazon Bedrock (Claude Opus 4.6)")
    parser.add_argument("--change-request", required=True, help="Description of the change request to implement")
    parser.add_argument("--standards-dir", required=True, help="Directory containing fetched standards files")
    parser.add_argument("--workspace-dir", default="", help="Directory with existing workspace Terraform code")
    parser.add_argument("--output-dir", required=True, help="Directory to write generated Terraform files")
    parser.add_argument("--region", default=None, help="AWS region for Bedrock (overrides AWS_REGION)")
    parser.add_argument("--model-id", default=None, help="Bedrock model ID (overrides BEDROCK_MODEL_ID)")
    args = parser.parse_args()

    region = args.region or os.environ.get("AWS_REGION", "ap-southeast-1")
    model_id = args.model_id or os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)

    # 1. Load context
    print("Loading organizational standards...")
    standards = load_standards(args.standards_dir)

    print("\nReading existing workspace code...")
    existing_files = read_existing_code(args.workspace_dir)

    # 2. Build prompt
    print("\nBuilding prompt...")
    prompt = build_prompt(args.change_request, standards, existing_files)
    print(f"  Prompt length: {len(prompt)} characters")

    # 3. Call Bedrock
    print("\nInvoking Amazon Bedrock...")
    response_text = invoke_bedrock(prompt, region, model_id)

    # 4. Parse response into files
    print("\nParsing generated code...")
    generated_files = parse_response(response_text)

    if not generated_files:
        print("ERROR: Could not parse any Terraform files from the model response.", file=sys.stderr)
        print("--- Raw response ---", file=sys.stderr)
        print(response_text[:2000], file=sys.stderr)
        sys.exit(1)

    print(f"  Parsed {len(generated_files)} file(s): {', '.join(generated_files.keys())}")

    # 5. Write files
    print(f"\nWriting generated files to '{args.output_dir}'...")
    write_files(generated_files, args.output_dir)

    # 6. Validate structure
    print("\nValidating generated structure...")
    validate_structure(args.output_dir)

    print(f"\nSUCCESS: Terraform code generated in '{args.output_dir}'.")


if __name__ == "__main__":
    main()
