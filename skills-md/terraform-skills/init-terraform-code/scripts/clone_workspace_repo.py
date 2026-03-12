#!/usr/bin/env python3
"""
Retrieve VCS configuration from a Terraform workspace and clone the
source code repository.

Environment variables:
    TFE_URL    - Terraform Enterprise URL (e.g., https://app.terraform.io)
    TFE_TOKEN  - Terraform Enterprise API token
    SCM_DOMAIN - SCM domain (default: github.com, e.g., gitlab.example.com)

Usage:
    python3 clone_workspace_repo.py --workspace-id <workspace_id> --clone-dir ./workspace-repo

Exit codes:
    0 - Repository cloned successfully
    1 - Failed to retrieve VCS config or clone
"""

import argparse
import json
import os
import subprocess
import sys

import requests


def get_workspace(workspace_id: str, tfe_url: str, token: str) -> dict:
    """Fetch workspace details from Terraform Enterprise API."""
    url = f"{tfe_url}/api/v2/workspaces/{workspace_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/vnd.api+json",
    }

    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError:
        print(f"ERROR: Failed to fetch workspace {workspace_id}: HTTP {resp.status_code} - {resp.text}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Could not connect to {tfe_url}", file=sys.stderr)
        sys.exit(1)


def extract_vcs_info(workspace_data: dict) -> dict:
    """Extract VCS and workspace info from workspace API response."""
    data = workspace_data.get("data", {})
    attributes = data.get("attributes", {})
    vcs_repo = attributes.get("vcs-repo", {}) or {}

    return {
        "workspace_id": data.get("id", ""),
        "workspace_name": attributes.get("name", ""),
        "working_directory": attributes.get("working-directory", ""),
        "terraform_version": attributes.get("terraform-version", ""),
        "repo_identifier": vcs_repo.get("identifier", ""),
        "branch": vcs_repo.get("branch", ""),
        "oauth_token_id": vcs_repo.get("oauth-token-id", ""),
        "display_identifier": vcs_repo.get("display-identifier", ""),
    }


def clone_repo(repo_identifier: str, clone_dir: str, scm_domain: str, branch: str = "") -> bool:
    """Clone the repository to the specified directory."""
    repo_url = f"https://{scm_domain}/{repo_identifier}.git"

    cmd = ["git", "clone", "--depth", "1"]
    if branch:
        cmd.extend(["--branch", branch])
    cmd.extend([repo_url, clone_dir])

    try:
        print(f"Cloning {repo_identifier} into {clone_dir}...")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"Clone successful.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Git clone failed:\n{e.stderr.strip()}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Clone Terraform workspace VCS repository")
    parser.add_argument("--workspace-id", required=True, help="Terraform workspace ID (e.g., ws-xxxxx)")
    parser.add_argument("--clone-dir", required=True, help="Directory to clone the repository into")
    parser.add_argument("--scm-domain", default=None, help="SCM domain (overrides SCM_DOMAIN env var)")
    parser.add_argument("--tfe-url", default=None, help="TFE URL (overrides TFE_URL env var)")
    parser.add_argument("--token", default=None, help="TFE API token (overrides TFE_TOKEN env var)")
    args = parser.parse_args()

    tfe_url = args.tfe_url or os.environ.get("TFE_URL")
    token = args.token or os.environ.get("TFE_TOKEN")
    scm_domain = args.scm_domain or os.environ.get("SCM_DOMAIN", "github.com")

    if not tfe_url:
        print("ERROR: TFE_URL env var or --tfe-url flag is required.", file=sys.stderr)
        sys.exit(1)
    if not token:
        print("ERROR: TFE_TOKEN env var or --token flag is required.", file=sys.stderr)
        sys.exit(1)

    # Get workspace VCS info
    workspace_data = get_workspace(args.workspace_id, tfe_url, token)
    vcs_info = extract_vcs_info(workspace_data)

    repo_identifier = vcs_info["repo_identifier"]
    if not repo_identifier:
        print("ERROR: Workspace has no VCS configuration. Cannot clone.", file=sys.stderr)
        sys.exit(1)

    # Clone the repository
    if not clone_repo(repo_identifier, args.clone_dir, scm_domain, vcs_info["branch"]):
        sys.exit(1)

    # Output clone details
    result = {
        "repo_identifier": repo_identifier,
        "clone_dir": os.path.abspath(args.clone_dir),
        "working_dir": vcs_info["working_directory"],
        "default_branch": vcs_info["branch"],
        "workspace_name": vcs_info["workspace_name"],
        "terraform_version": vcs_info["terraform_version"],
    }
    print(json.dumps(result, indent=2))
    print("\nSUCCESS: Repository cloned.")


if __name__ == "__main__":
    main()
