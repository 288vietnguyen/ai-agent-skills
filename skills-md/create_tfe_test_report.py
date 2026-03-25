#!/usr/bin/env python3
"""
TFE Test Report - Confluence Page Creator
==========================================
Creates a Confluence Cloud page following the TFE Test Report Template
using Confluence REST API V2 (POST /wiki/api/v2/pages).

Usage:
    python create_tfe_test_report.py

Prerequisites:
    pip install requests

Configuration:
    Set the following environment variables or edit the CONFIG section below:
    - CONFLUENCE_BASE_URL   : e.g. https://your-domain.atlassian.net
    - CONFLUENCE_USER_EMAIL : your Atlassian account email
    - CONFLUENCE_API_TOKEN  : API token from https://id.atlassian.com/manage-profile/security/api-tokens
    - CONFLUENCE_SPACE_ID   : numeric space ID (use GET /wiki/api/v2/spaces to find it)
    - CONFLUENCE_PARENT_ID  : (optional) parent page ID to nest under
"""

import json
import os
import sys
from base64 import b64encode
from datetime import date

import requests

# =============================================================================
# CONFIGURATION
# =============================================================================
CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_BASE_URL", "https://your-domain.atlassian.net")
CONFLUENCE_USER_EMAIL = os.getenv("CONFLUENCE_USER_EMAIL", "user@example.com")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN", "your-api-token")
CONFLUENCE_SPACE_ID = os.getenv("CONFLUENCE_SPACE_ID", "123456789")
CONFLUENCE_PARENT_ID = os.getenv("CONFLUENCE_PARENT_ID", "")  # optional


# =============================================================================
# REPORT DATA — Replace these placeholders with your actual data
# =============================================================================
REPORT_DATA = {
    # -- Cover / Header --
    "action_change": "Deploy VPC and EC2 infrastructure",
    "itsm_request_id": "CHG-001234",

    # -- Sign-off table --
    "signers": [
        {"stt": 1, "unit": "DevSecOps", "sign": ""},
        {"stt": 2, "unit": "IT PM / DL", "sign": ""},
        {"stt": 3, "unit": "SOS", "sign": ""},
        {"stt": 4, "unit": "IT QE", "sign": ""},
    ],

    # -- 1.1 Testing Execution Time --
    "testing_type": "System Testing (ST)",
    "day_start": "2026-03-20",
    "day_end": "2026-03-24",

    # -- 1.2 Test Participants --
    "participants": [
        {
            "full_name": "Nguyen Van A",
            "user_id": "nguyenvana",
            "division": "DSO",
            "type_of_user": "System User",
            "participate": "OAT",
        },
        # Add more participants as needed
    ],

    # -- 1.3 Environment and Testing Tool --
    "aws_account_name": "my-aws-nonprod",
    "aws_account_id": "123456789012",
    "detail_workload": "Deploy VPC, subnets, EC2 instances, and S3 buckets for the staging environment",

    # -- 1.4 Purpose --
    "purpose": "Testing deploy infrastructure by Terraform",

    # -- 2.1 General Test Result --
    "environment": "Nonprod",
    "result_status": "Accepted",  # "Accepted" or "Not Accepted"

    # -- 2.2 Summary Table --
    "workspaces_summary": [
        {
            "workspace_name": "vpc-networking",
            "tfe_run_url": "https://app.terraform.io/app/org/runs/run-abc123",
        },
        {
            "workspace_name": "ec2-compute",
            "tfe_run_url": "https://app.terraform.io/app/org/runs/run-def456",
        },
    ],
    "verify_resources": [
        {"resource": "AWS VPC", "output": "vpc-0abc123def created"},
        {"resource": "AWS Subnet", "output": "subnet-0abc123 created (10.0.1.0/24)"},
        {"resource": "AWS EC2", "output": "i-0abc123def456 created (t3.medium)"},
        {"resource": "AWS S3", "output": "s3://my-app-bucket created"},
    ],

    # -- 2.3 Infrastructure Testing --
    # A. TFE Rollout
    "rollout_workspaces": [
        {
            "workspace_name": "vpc-networking",
            "tfe_run_url": "https://app.terraform.io/app/org/runs/run-abc123",
            "resources": [
                {"resource": "AWS VPC", "change": "1 created, 0 changed, 0 deleted"},
                {"resource": "AWS Subnet", "change": "3 created, 0 changed, 0 deleted"},
                {"resource": "AWS Route Table", "change": "2 created, 0 changed, 0 deleted"},
            ],
        },
        {
            "workspace_name": "ec2-compute",
            "tfe_run_url": "https://app.terraform.io/app/org/runs/run-def456",
            "resources": [
                {"resource": "AWS EC2", "change": "2 created, 0 changed, 0 deleted"},
                {"resource": "AWS Security Group", "change": "1 created, 0 changed, 0 deleted"},
            ],
        },
    ],
    # B. TFE Rollback
    "rollback_workspaces": [
        {
            "workspace_name": "vpc-networking",
            "tfe_run_url": "https://app.terraform.io/app/org/runs/run-rb-abc123",
            "resources": [
                {"resource": "AWS VPC", "change": "0 created, 0 changed, 1 deleted"},
                {"resource": "AWS Subnet", "change": "0 created, 0 changed, 3 deleted"},
                {"resource": "AWS Route Table", "change": "0 created, 0 changed, 2 deleted"},
            ],
        },
        {
            "workspace_name": "ec2-compute",
            "tfe_run_url": "https://app.terraform.io/app/org/runs/run-rb-def456",
            "resources": [
                {"resource": "AWS EC2", "change": "0 created, 0 changed, 2 deleted"},
                {"resource": "AWS Security Group", "change": "0 created, 0 changed, 1 deleted"},
            ],
        },
    ],
}


# =============================================================================
# HTML BUILDER — Generates Confluence Storage Format (XHTML)
# =============================================================================

def build_page_body(data: dict) -> str:
    """Build the full Confluence storage-format HTML for the TFE Test Report."""

    html_parts = []

    # =========================================================================
    # COVER / HEADER
    # =========================================================================
    html_parts.append(f"""
<h1>TFE Test Report</h1>
<p><strong>Request Description:</strong> {data['action_change']}</p>
<p><strong>ID:</strong> ITSM - {data['itsm_request_id']}</p>
""")

    # Sign-off table
    html_parts.append("""
<table data-layout="default">
  <colgroup><col /><col /><col /></colgroup>
  <thead>
    <tr>
      <th><p><strong>STT</strong></p></th>
      <th><p><strong>Unit</strong></p></th>
      <th><p><strong>Sign</strong></p></th>
    </tr>
  </thead>
  <tbody>
""")
    for signer in data["signers"]:
        html_parts.append(f"""
    <tr>
      <td><p>{signer['stt']}</p></td>
      <td><p>{signer['unit']}</p></td>
      <td><p>{signer['sign']}</p></td>
    </tr>
""")
    html_parts.append("  </tbody>\n</table>\n<hr />\n")

    # =========================================================================
    # 1. SUMMARY OF TESTING PROCESS
    # =========================================================================
    html_parts.append('<h2>1. Summary of Testing Process</h2>\n')

    # -- 1.1 Testing Execution Time --
    html_parts.append(f"""
<h3>1.1. Testing Execution Time</h3>
<table data-layout="default">
  <colgroup><col /><col /><col /></colgroup>
  <thead>
    <tr>
      <th><p><strong>Type of Testing</strong></p></th>
      <th><p><strong>From Date</strong></p></th>
      <th><p><strong>To Date</strong></p></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><p>{data['testing_type']}</p></td>
      <td><p>{data['day_start']}</p></td>
      <td><p>{data['day_end']}</p></td>
    </tr>
  </tbody>
</table>
""")

    # -- 1.2 Test Participants --
    html_parts.append("""
<h3>1.2. Test Participants</h3>
<table data-layout="default">
  <colgroup><col /><col /><col /><col /><col /></colgroup>
  <thead>
    <tr>
      <th><p><strong>Full Name</strong></p></th>
      <th><p><strong>User ID</strong></p></th>
      <th><p><strong>Division</strong></p></th>
      <th><p><strong>Type of User</strong></p></th>
      <th><p><strong>Participate</strong></p></th>
    </tr>
  </thead>
  <tbody>
""")
    for p in data["participants"]:
        html_parts.append(f"""
    <tr>
      <td><p>{p['full_name']}</p></td>
      <td><p>{p['user_id']}</p></td>
      <td><p>{p['division']}</p></td>
      <td><p>{p['type_of_user']}</p></td>
      <td><p>{p['participate']}</p></td>
    </tr>
""")
    html_parts.append("  </tbody>\n</table>\n")

    # -- 1.3 Environment and Testing Tool --
    html_parts.append(f"""
<h3>1.3. Environment and Testing Tool</h3>
<table data-layout="default">
  <colgroup><col /><col /></colgroup>
  <tbody>
    <tr>
      <td><p><strong>AWS Account Name</strong></p></td>
      <td><p>{data['aws_account_name']}</p></td>
    </tr>
    <tr>
      <td><p><strong>ID</strong></p></td>
      <td><p>{data['aws_account_id']}</p></td>
    </tr>
    <tr>
      <td><p><strong>Detail Workload</strong></p></td>
      <td><p>{data['detail_workload']}</p></td>
    </tr>
  </tbody>
</table>
""")

    # -- 1.4 Purpose and Scope --
    html_parts.append(f"""
<h3>1.4. Purpose and Scope of Testing</h3>
<p><strong>Purpose:</strong> {data['purpose']}</p>
<hr />
""")

    # =========================================================================
    # 2. TEST RESULT
    # =========================================================================
    html_parts.append('<h2>2. Test Result</h2>\n')

    # -- 2.1 General Test Result --
    html_parts.append(f"""
<h3>2.1. General Test Result</h3>
<p>{data['environment']} report: <strong>{data['result_status']}</strong></p>
""")

    # -- 2.2 Summary Table of Test Results --
    html_parts.append('<h3>2.2. Summary Table of Test Results</h3>\n')
    html_parts.append(f'<p><strong>{data["environment"]} Report Result</strong></p>\n')

    # TFE Workspace result table
    html_parts.append("""
<p><strong>TFE Workspace Result</strong></p>
<table data-layout="default">
  <colgroup><col /><col /></colgroup>
  <thead>
    <tr>
      <th><p><strong>TFE Run Deploy Workspace</strong></p></th>
      <th><p><strong>Workspace Name</strong></p></th>
    </tr>
  </thead>
  <tbody>
""")
    for idx, ws in enumerate(data["workspaces_summary"], start=1):
        html_parts.append(f"""
    <tr>
      <td><p>TFE run deploy workspace {idx}</p></td>
      <td><p>{ws['workspace_name']}</p></td>
    </tr>
    <tr>
      <td><p>TFE run</p></td>
      <td><p><a href="{ws['tfe_run_url']}">{ws['tfe_run_url']}</a></p></td>
    </tr>
""")
    html_parts.append("  </tbody>\n</table>\n")

    # Verify resources table
    html_parts.append("""
<p><strong>Verify Resources Created</strong></p>
<table data-layout="default">
  <colgroup><col /><col /></colgroup>
  <thead>
    <tr>
      <th><p><strong>AWS Resource</strong></p></th>
      <th><p><strong>TFE Run Output</strong></p></th>
    </tr>
  </thead>
  <tbody>
""")
    for res in data["verify_resources"]:
        html_parts.append(f"""
    <tr>
      <td><p>{res['resource']}</p></td>
      <td><p>{res['output']}</p></td>
    </tr>
""")
    html_parts.append("  </tbody>\n</table>\n")

    # -- 2.3 Infrastructure Testing --
    html_parts.append('<h3>2.3. Infrastructure Testing</h3>\n')

    # A. TFE Rollout
    html_parts.append('<h4>A. TFE Rollout</h4>\n')
    for idx, ws in enumerate(data["rollout_workspaces"], start=1):
        html_parts.append(f"""
<p><strong>{idx}. {ws['workspace_name']}</strong></p>
<p>TFE run rollout: <a href="{ws['tfe_run_url']}">{ws['tfe_run_url']}</a></p>
<table data-layout="default">
  <colgroup><col /><col /></colgroup>
  <thead>
    <tr>
      <th><p><strong>Overview</strong></p></th>
      <th><p><strong>Resource Change</strong></p></th>
    </tr>
  </thead>
  <tbody>
""")
        for res in ws["resources"]:
            html_parts.append(f"""
    <tr>
      <td><p>{res['resource']}</p></td>
      <td><p>{res['change']}</p></td>
    </tr>
""")
        html_parts.append("  </tbody>\n</table>\n")

    # B. TFE Rollback
    html_parts.append('<h4>B. TFE Rollback</h4>\n')
    for idx, ws in enumerate(data["rollback_workspaces"], start=1):
        html_parts.append(f"""
<p><strong>{idx}. {ws['workspace_name']}</strong></p>
<p>TFE run rollback: <a href="{ws['tfe_run_url']}">{ws['tfe_run_url']}</a></p>
<table data-layout="default">
  <colgroup><col /><col /></colgroup>
  <thead>
    <tr>
      <th><p><strong>Overview</strong></p></th>
      <th><p><strong>Resource Change</strong></p></th>
    </tr>
  </thead>
  <tbody>
""")
        for res in ws["resources"]:
            html_parts.append(f"""
    <tr>
      <td><p>{res['resource']}</p></td>
      <td><p>{res['change']}</p></td>
    </tr>
""")
        html_parts.append("  </tbody>\n</table>\n")

    return "".join(html_parts)


# =============================================================================
# CONFLUENCE API CLIENT
# =============================================================================

def get_auth_header(email: str, api_token: str) -> dict:
    """Build Basic Auth header for Atlassian Cloud."""
    credentials = b64encode(f"{email}:{api_token}".encode()).decode()
    return {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def create_confluence_page(
    base_url: str,
    space_id: str,
    title: str,
    body_html: str,
    parent_id: str = "",
    status: str = "current",
) -> dict:
    """
    Create a Confluence page using REST API V2.

    Endpoint: POST /wiki/api/v2/pages
    Docs: https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-page/#api-pages-post

    Args:
        base_url:   Confluence base URL (e.g. https://your-domain.atlassian.net)
        space_id:   Numeric space ID (string)
        title:      Page title
        body_html:  Confluence storage-format XHTML
        parent_id:  (optional) Parent page ID to nest under
        status:     "current" (published) or "draft"

    Returns:
        JSON response from the API
    """
    url = f"{base_url}/wiki/api/v2/pages"
    headers = get_auth_header(CONFLUENCE_USER_EMAIL, CONFLUENCE_API_TOKEN)

    payload = {
        "spaceId": space_id,
        "status": status,
        "title": title,
        "body": {
            "representation": "storage",
            "value": body_html,
        },
    }

    if parent_id:
        payload["parentId"] = parent_id

    print(f"[INFO] Creating page: '{title}'")
    print(f"[INFO] Endpoint: POST {url}")
    print(f"[INFO] Space ID: {space_id}")
    if parent_id:
        print(f"[INFO] Parent ID: {parent_id}")

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code in (200, 201):
        result = response.json()
        page_id = result.get("id", "N/A")
        web_link = result.get("_links", {}).get("webui", "")
        full_link = f"{base_url}/wiki{web_link}" if web_link else "N/A"

        print(f"[SUCCESS] Page created successfully!")
        print(f"[SUCCESS] Page ID: {page_id}")
        print(f"[SUCCESS] URL: {full_link}")
        return result
    else:
        print(f"[ERROR] Failed to create page: {response.status_code}")
        print(f"[ERROR] Response: {response.text}")
        response.raise_for_status()


def list_spaces(base_url: str) -> list:
    """
    Helper: List available spaces to find your space ID.
    GET /wiki/api/v2/spaces
    """
    url = f"{base_url}/wiki/api/v2/spaces"
    headers = get_auth_header(CONFLUENCE_USER_EMAIL, CONFLUENCE_API_TOKEN)
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    spaces = response.json().get("results", [])
    print("\n[INFO] Available Spaces:")
    print(f"{'ID':<15} {'Key':<10} {'Name'}")
    print("-" * 50)
    for s in spaces:
        print(f"{s['id']:<15} {s.get('key', 'N/A'):<10} {s.get('name', 'N/A')}")
    return spaces


# =============================================================================
# MAIN
# =============================================================================

def main():
    # Validate configuration
    if "your-domain" in CONFLUENCE_BASE_URL or "your-api-token" in CONFLUENCE_API_TOKEN:
        print("=" * 60)
        print("  CONFIGURATION REQUIRED")
        print("=" * 60)
        print()
        print("Set these environment variables before running:")
        print()
        print("  export CONFLUENCE_BASE_URL='https://your-domain.atlassian.net'")
        print("  export CONFLUENCE_USER_EMAIL='you@example.com'")
        print("  export CONFLUENCE_API_TOKEN='your-api-token-here'")
        print("  export CONFLUENCE_SPACE_ID='123456789'")
        print("  export CONFLUENCE_PARENT_ID='987654321'  # optional")
        print()
        print("To find your Space ID, set the first 3 vars and run:")
        print("  python create_tfe_test_report.py --list-spaces")
        print()

        # Still generate the HTML for preview
        print("Generating HTML preview to 'tfe_report_preview.html'...")
        body_html = build_page_body(REPORT_DATA)
        preview_path = "tfe_report_preview.html"
        with open(preview_path, "w") as f:
            f.write(f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>TFE Test Report Preview</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; color: #172B4D; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
    th, td {{ border: 1px solid #DFE1E6; padding: 8px 12px; text-align: left; }}
    th {{ background-color: #F4F5F7; }}
    h1 {{ color: #0052CC; }}
    h2 {{ color: #172B4D; border-bottom: 2px solid #0052CC; padding-bottom: 6px; }}
    h3 {{ color: #344563; }}
    h4 {{ color: #505F79; }}
    hr {{ border: none; border-top: 1px solid #DFE1E6; margin: 24px 0; }}
    a {{ color: #0052CC; }}
    strong {{ color: #172B4D; }}
  </style>
</head>
<body>
{body_html}
</body>
</html>""")
        print(f"Preview saved to: {preview_path}")
        return

    # Handle --list-spaces flag
    if len(sys.argv) > 1 and sys.argv[1] == "--list-spaces":
        list_spaces(CONFLUENCE_BASE_URL)
        return

    # Build page body
    body_html = build_page_body(REPORT_DATA)

    # Create the page title with today's date
    today = date.today().strftime("%Y-%m-%d")
    page_title = f"TFE Test Report - {REPORT_DATA['itsm_request_id']} - {today}"

    # Create the page
    result = create_confluence_page(
        base_url=CONFLUENCE_BASE_URL,
        space_id=CONFLUENCE_SPACE_ID,
        title=page_title,
        body_html=body_html,
        parent_id=CONFLUENCE_PARENT_ID,
    )

    # Save response for debugging
    with open("confluence_response.json", "w") as f:
        json.dump(result, f, indent=2)
    print("[INFO] Full API response saved to confluence_response.json")


if __name__ == "__main__":
    main()
