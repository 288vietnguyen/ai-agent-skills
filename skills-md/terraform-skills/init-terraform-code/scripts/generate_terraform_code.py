#!/usr/bin/env python3
"""
Generate Terraform code by sending a prompt to Amazon Bedrock (Claude Opus 4.6).

Two modes:
  - CREATE: When the change request involves creating new resources, the prompt
    includes resource templates from the assets folder as reference.
  - MODIFY: When modifying existing config, the prompt includes only the
    existing workspace code and standards.

Memory (optional):
  When MEMORYDB_HOST is set, the script checks Amazon MemoryDB (Redis VSS) for
  similar past executions. On a cache hit (similarity > threshold), Steps 1-3
  are skipped and cached context is reused. After successful generation, the
  execution context is stored in MemoryDB for future reuse.

Environment variables:
    AWS_REGION            - AWS region for Bedrock (default: ap-southeast-1)
    AWS_ACCESS_KEY_ID     - AWS access key (or use IAM role)
    AWS_SECRET_ACCESS_KEY - AWS secret key (or use IAM role)
    BEDROCK_MODEL_ID      - Bedrock model ID (default: us.anthropic.claude-opus-4-6-20250610)
    MEMORYDB_HOST         - Amazon MemoryDB endpoint (optional, enables memory)
    MEMORYDB_PORT         - MemoryDB port (default: 6379)
    MEMORY_SIMILARITY_THRESHOLD - Cosine similarity threshold (default: 0.85)
    MEMORY_TTL_DAYS       - Days to keep cached contexts (default: 90)

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

# Resolve assets directory relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "assets", "terraform-template")

# Map of resource keywords to their template subdirectory under module-nonprod/
RESOURCE_TEMPLATE_MAP = {
    "s3": "s3",
}


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


def read_tf_dir(directory: str) -> dict[str, str]:
    """Read all .tf files from a directory."""
    files = {}
    if not os.path.isdir(directory):
        return files
    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(".tf"):
            continue
        filepath = os.path.join(directory, filename)
        with open(filepath) as f:
            files[filename] = f.read()
    return files


def detect_resource_types(change_request: str) -> list[str]:
    """Detect which resource types are requested for creation."""
    cr_lower = change_request.lower()

    # Only match if the request is about creating new resources
    create_keywords = ["create", "add", "new", "provision", "deploy", "setup", "set up", "init"]
    is_create = any(kw in cr_lower for kw in create_keywords)

    if not is_create:
        return []

    matched = []
    for keyword, template_dir in RESOURCE_TEMPLATE_MAP.items():
        if keyword in cr_lower:
            matched.append(template_dir)

    return matched


def load_templates(resource_types: list[str]) -> dict[str, dict[str, str]]:
    """Load template files for the given resource types from assets."""
    templates = {}

    # Load module templates
    for resource_type in resource_types:
        module_dir = os.path.join(ASSETS_DIR, "module-nonprod", resource_type)
        if os.path.isdir(module_dir):
            files = read_tf_dir(module_dir)
            if files:
                templates[f"module-nonprod/{resource_type}"] = files
                print(f"  Loaded module template: module-nonprod/{resource_type}/ ({len(files)} files)")

    # Load environment template (always include when creating new resources)
    env_dir = os.path.join(ASSETS_DIR, "regions", "region-code", "environment")
    if os.path.isdir(env_dir):
        files = read_tf_dir(env_dir)
        if files:
            templates["regions/region-code/environment"] = files
            print(f"  Loaded environment template: regions/region-code/environment/ ({len(files)} files)")

    return templates


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a Senior DevSecOps Engineer and AWS Engineer. You produce production-ready Terraform \
code that strictly follows organizational standards and best practices.

Rules:
- Output ONLY Terraform code change blocks.
- No explanations outside code blocks.
- Each file must be wrapped in a fenced code block with the filename as label:
  ```hcl filename="path/to/file.tf"
  ... code ...
  ```
- DO NOT CHANGE the current setting: module, module's version, provider.tf
- Generate all required files defined in the structure standard.
- Follow the naming conventions, tagging requirements and folder structure.
- If existing code is provided, extend it without breaking current resources.
- When templates are provided, follow the same pattern and structure exactly.
"""


def build_prompt(change_request: str, standards: dict[str, str],
                 existing_files: dict[str, str],
                 templates: dict[str, dict[str, str]]) -> str:
    """Build the user prompt with all context for Bedrock."""
    sections = []

    # Change request
    sections.append(f"## Change Request\n{change_request}")

    # Standards
    if standards:
        for filename, content in standards.items():
            label = filename.replace(".md", "").replace("_", " ").title()
            sections.append(f"## Standard: {label} ({filename})\n{content}")
    else:
        sections.append("## Standards\nNo standards provided.")

    # Templates (for new resource creation)
    if templates:
        for template_path, files in templates.items():
            template_section = f"## Resource Template: {template_path}/\n"
            template_section += "Use this template as the reference structure. Follow the same pattern exactly.\n\n"
            for filename, content in files.items():
                template_section += f"```hcl filename=\"{template_path}/{filename}\"\n{content}\n```\n\n"
            sections.append(template_section)

    # Existing code
    if existing_files:
        code_section = "## Existing Workspace Code\n"
        for filename, content in existing_files.items():
            code_section += f"```hcl filename=\"{filename}\"\n{content}\n```\n\n"
        sections.append(code_section)
    else:
        sections.append("## Existing Workspace Code\nNo existing code. This is a new workspace.")

    # Instructions
    if templates:
        sections.append(
            "## Instructions\n"
            "This is a CREATE request. Generate Terraform code for the new resource(s).\n"
            "Follow the resource templates provided above as the exact pattern.\n"
            "Generate both the module files and the environment-level files that call the module.\n"
            "Each file must be in a separate fenced code block with `filename=\"path/to/file.tf\"` label.\n"
            "Preserve the folder structure from the templates."
        )
    else:
        sections.append(
            "## Instructions\n"
            "This is a MODIFY request. Update the existing Terraform code for the change request.\n"
            "Each file must be in a separate fenced code block with `filename=\"<name>\"` label.\n"
            "Only output files that need to be changed or created."
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
        dirpath = os.path.dirname(filepath)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(filepath, "w") as f:
            f.write(content)
        print(f"  Written: {filename}")


def validate_structure(output_dir: str) -> bool:
    """Validate generated code contains essential Terraform files."""
    required_files = ["main.tf", "variables.tf", "outputs.tf", "providers.tf", "versions.tf"]

    # Check in output_dir and any subdirectories
    all_files = set()
    for _, _, filenames in os.walk(output_dir):
        for f in filenames:
            all_files.add(f)

    missing = [f for f in required_files if f not in all_files]

    if missing:
        print(f"WARNING: Generated code is missing files: {', '.join(missing)}", file=sys.stderr)
        return False

    print("PASS: Generated code matches required structure.")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _init_memory(region: str):
    """Initialize MemoryManager if MEMORYDB_HOST is configured.

    Returns MemoryManager or None if memory is not configured.
    """
    redis_host = os.environ.get("MEMORYDB_HOST", "")
    if not redis_host:
        return None

    redis_port = int(os.environ.get("MEMORYDB_PORT", "6379"))
    redis_username = os.environ.get("MEMORYDB_USERNAME", "")
    redis_password = os.environ.get("MEMORYDB_PASSWORD", "")
    threshold = float(os.environ.get("MEMORY_SIMILARITY_THRESHOLD", "0.85"))
    ttl_days = int(os.environ.get("MEMORY_TTL_DAYS", "90"))
    try:
        from memory.embeddings import BedrockEmbeddings
        from memory.redis_store import RedisMemoryStore
        from memory.manager import MemoryManager

        embeddings = BedrockEmbeddings(region=region)
        store = RedisMemoryStore(
            host=redis_host, port=redis_port,
            username=redis_username, password=redis_password,
            ttl_days=ttl_days,
        )
        manager = MemoryManager(embeddings=embeddings, store=store, threshold=threshold)
        print(f"  Memory enabled: {redis_host}:{redis_port}")
        return manager
    except Exception as e:
        print(f"  WARNING: Failed to initialize memory: {e}", file=sys.stderr)
        print("  Proceeding without memory.", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description="Generate Terraform code via Amazon Bedrock (Claude Opus 4.6)")
    parser.add_argument("--change-request", required=True, help="Description of the change request to implement")
    parser.add_argument("--standards-dir", required=True, help="Directory containing fetched standards files")
    parser.add_argument("--workspace-dir", default="", help="Directory with existing workspace Terraform code")
    parser.add_argument("--output-dir", required=True, help="Directory to write generated Terraform files")
    parser.add_argument("--assets-dir", default=None, help="Path to assets/terraform-template directory (overrides default)")
    parser.add_argument("--region", default=None, help="AWS region for Bedrock (overrides AWS_REGION)")
    parser.add_argument("--model-id", default=None, help="Bedrock model ID (overrides BEDROCK_MODEL_ID)")
    parser.add_argument("--workspace-id", default="", help="Workspace ID (stored in memory for future reference)")
    parser.add_argument("--workspace-name", default="", help="Workspace name (stored in memory for future reference)")
    parser.add_argument("--vcs-repo-url", default="", help="VCS repository URL (stored in memory)")
    parser.add_argument("--vcs-branch", default="", help="VCS branch (stored in memory)")
    args = parser.parse_args()

    region = args.region or os.environ.get("AWS_REGION", "ap-southeast-1")
    model_id = args.model_id or os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)

    global ASSETS_DIR
    if args.assets_dir:
        ASSETS_DIR = args.assets_dir

    # 0. Initialize memory (optional)
    print("Initializing memory...")
    memory = _init_memory(region)

    # 0.1 Check memory for similar past execution
    cached_context = None
    if memory:
        cached_context = memory.find_similar(args.change_request)

    if cached_context:
        # CACHE HIT — reuse cached standards/templates, read existing code fresh
        print(f"\nMEMORY HIT (similarity={cached_context.similarity_score:.3f})")
        print(f"  Reusing cached context from: \"{cached_context.change_request}\"")
        print(f"  Cached workspace: {cached_context.workspace_name} ({cached_context.workspace_id})")
        standards = cached_context.standards
        templates = cached_context.templates
        resource_types = cached_context.resource_types
        executed_steps = ["generate", "push"]

        # Always read existing code fresh (it may have changed outside AI)
        print("\nReading existing workspace code (fresh)...")
        existing_files = read_existing_code(args.workspace_dir)
    else:
        # CACHE MISS — run full flow (Steps 1-3)
        if memory:
            print("\nNo similar past execution found. Running full flow...")

        # 1. Load context
        print("\nLoading organizational standards...")
        standards = load_standards(args.standards_dir)

        print("\nReading existing workspace code...")
        existing_files = read_existing_code(args.workspace_dir)

        # 2. Detect request type and load templates if creating new resources
        print("\nDetecting request type...")
        resource_types = detect_resource_types(args.change_request)

        templates = {}
        if resource_types:
            print(f"  CREATE mode — detected resource types: {', '.join(resource_types)}")
            print("\nLoading resource templates from assets...")
            templates = load_templates(resource_types)
            if not templates:
                print("  WARNING: No matching templates found in assets. Proceeding without templates.", file=sys.stderr)
        else:
            print("  MODIFY mode — no new resource types detected, using existing code context only.")

        executed_steps = ["validate", "clone", "fetch", "generate", "push"]

    # 3. Build prompt
    print("\nBuilding prompt...")
    prompt = build_prompt(args.change_request, standards, existing_files, templates)
    print(f"  Prompt length: {len(prompt)} characters")

    # 4. Call Bedrock
    print("\nInvoking Amazon Bedrock...")
    response_text = invoke_bedrock(prompt, region, model_id)

    # 5. Parse response into files
    print("\nParsing generated code...")
    generated_files = parse_response(response_text)

    if not generated_files:
        print("ERROR: Could not parse any Terraform files from the model response.", file=sys.stderr)
        print("--- Raw response ---", file=sys.stderr)
        print(response_text[:2000], file=sys.stderr)
        sys.exit(1)

    print(f"  Parsed {len(generated_files)} file(s): {', '.join(generated_files.keys())}")

    # 6. Write files
    print(f"\nWriting generated files to '{args.output_dir}'...")
    write_files(generated_files, args.output_dir)

    # 7. Validate structure
    print("\nValidating generated structure...")
    validate_structure(args.output_dir)

    # 8. Store execution in memory for future reuse
    if memory:
        from memory.models import ExecutionContext

        print("\nStoring execution in memory...")
        context = ExecutionContext(
            change_request=args.change_request,
            workspace_id=args.workspace_id,
            workspace_name=args.workspace_name,
            vcs_repo_url=args.vcs_repo_url,
            vcs_branch=args.vcs_branch,
            working_dir=args.workspace_dir,
            standards=standards,
            templates=templates,
            generated_code=generated_files,
            resource_types=resource_types,
            execution_mode="CREATE" if resource_types else "MODIFY",
            executed_steps=executed_steps,
        )
        memory.remember(context)

    print(f"\nSUCCESS: Terraform code generated in '{args.output_dir}'.")


if __name__ == "__main__":
    main()
