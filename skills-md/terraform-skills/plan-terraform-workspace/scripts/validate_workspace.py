#!/usr/bin/env python3
"""
Validate that a Terraform workspace is not locked and the last run is finished.

Environment variables:
    TFE_URL   - Terraform Enterprise URL (e.g., https://app.terraform.io)
    TFE_TOKEN - Terraform Enterprise API token

Usage:
    python3 validate_workspace.py --workspace-id <workspace_id>

Exit codes:
    0 - Workspace is unlocked and last run is finished
    1 - Workspace is locked or last run is still planning
"""

import argparse
import os
import sys
import time

import requests

MAX_RETRIES = 3
RETRY_INTERVAL = 300  # 5 minutes


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


def get_latest_run(workspace_id: str, tfe_url: str, token: str) -> dict | None:
    """Fetch the latest run for a workspace."""
    url = f"{tfe_url}/api/v2/workspaces/{workspace_id}/runs"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/vnd.api+json",
    }
    params = {"page[size]": 1}

    try:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        runs = data.get("data", [])
        return runs[0] if runs else None
    except requests.exceptions.HTTPError:
        print(f"ERROR: Failed to fetch runs for workspace {workspace_id}: HTTP {resp.status_code} - {resp.text}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Could not connect to {tfe_url}", file=sys.stderr)
        sys.exit(1)


def validate_workspace(workspace_id: str, tfe_url: str, token: str) -> bool:
    """Validate workspace is unlocked and last run is finished."""
    workspace_data = get_workspace(workspace_id, tfe_url, token)
    attributes = workspace_data.get("data", {}).get("attributes", {})
    locked = attributes.get("locked", False)

    if locked:
        locked_by = workspace_data.get("data", {}).get("relationships", {}).get("locked-by", {}).get("data", {})
        locked_by_id = locked_by.get("id", "unknown")
        locked_by_type = locked_by.get("type", "unknown")
        print(
            f"ERROR: Workspace is locked by {locked_by_type} '{locked_by_id}'. "
            f"Unlock the workspace before planning.",
            file=sys.stderr,
        )
        return False

    print("Workspace is unlocked.")

    # Check last run status with retry logic
    for attempt in range(1, MAX_RETRIES + 1):
        latest_run = get_latest_run(workspace_id, tfe_url, token)

        if latest_run is None:
            print("No previous runs found. Workspace is ready for planning.")
            return True

        run_id = latest_run.get("id", "unknown")
        run_status = latest_run.get("attributes", {}).get("status", "")
        print(f"Latest run: {run_id}, status: {run_status}")

        in_progress_states = {"pending", "plan_queued", "planning", "cost_estimating", "policy_checking"}
        if run_status not in in_progress_states:
            print("PASS: Last run is finished. Workspace is ready for planning.")
            return True

        if attempt < MAX_RETRIES:
            print(
                f"Last run is still in progress (status: '{run_status}'). "
                f"Retry {attempt}/{MAX_RETRIES}, waiting {RETRY_INTERVAL}s..."
            )
            time.sleep(RETRY_INTERVAL)
        else:
            print(
                f"ERROR: Last run '{run_id}' is still in progress (status: '{run_status}') "
                f"after {MAX_RETRIES} retries.",
                file=sys.stderr,
            )
            return False

    return False


def main():
    parser = argparse.ArgumentParser(description="Validate Terraform workspace for planning")
    parser.add_argument("--workspace-id", required=True, help="Terraform workspace ID (e.g., ws-xxxxx)")
    parser.add_argument("--tfe-url", default=None, help="TFE URL (overrides TFE_URL env var)")
    parser.add_argument("--token", default=None, help="TFE API token (overrides TFE_TOKEN env var)")
    args = parser.parse_args()

    tfe_url = args.tfe_url or os.environ.get("TFE_URL")
    token = args.token or os.environ.get("TFE_TOKEN")

    if not tfe_url:
        print("ERROR: TFE_URL env var or --tfe-url flag is required.", file=sys.stderr)
        sys.exit(1)
    if not token:
        print("ERROR: TFE_TOKEN env var or --token flag is required.", file=sys.stderr)
        sys.exit(1)

    if not validate_workspace(args.workspace_id, tfe_url, token):
        sys.exit(1)


if __name__ == "__main__":
    main()
