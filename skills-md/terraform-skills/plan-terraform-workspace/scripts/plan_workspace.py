#!/usr/bin/env python3
"""
Create a Terraform plan run on a workspace using the TFE REST API.

Supports two plan types:
  - plan-only: creates a speculative plan (no apply possible)
  - plan-and-apply: creates a standard run that can be applied later

Environment variables:
    TFE_URL   - Terraform Enterprise URL (e.g., https://app.terraform.io)
    TFE_TOKEN - Terraform Enterprise API token

Usage:
    python3 plan_workspace.py --workspace-id <workspace_id> --plan-type <plan-only|plan-and-apply> [--message <message>]

Exit codes:
    0 - Plan run created successfully
    1 - Failed to create plan run
"""

import argparse
import json
import os
import sys

import requests

VALID_PLAN_TYPES = {"plan-only", "plan-and-apply"}


def create_run(workspace_id: str, tfe_url: str, token: str, plan_type: str, message: str = None) -> dict:
    """Create a new run (plan) on the workspace."""
    url = f"{tfe_url}/api/v2/runs"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/vnd.api+json",
    }

    is_plan_only = plan_type == "plan-only"

    payload = {
        "data": {
            "attributes": {
                "plan-only": is_plan_only,
                "message": message or f"Plan triggered via DSO AI agent ({plan_type})",
            },
            "type": "runs",
            "relationships": {
                "workspace": {
                    "data": {
                        "type": "workspaces",
                        "id": workspace_id,
                    }
                }
            },
        }
    }

    try:
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        run_data = resp.json()
        run_id = run_data.get("data", {}).get("id", "unknown")
        print(f"SUCCESS: Plan run created. Run ID: {run_id}, type: {plan_type}")
        return run_data
    except requests.exceptions.HTTPError:
        print(f"ERROR: Failed to create run: HTTP {resp.status_code} - {resp.text}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Could not connect to {tfe_url}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Plan a Terraform workspace")
    parser.add_argument("--workspace-id", required=True, help="Terraform workspace ID (e.g., ws-xxxxx)")
    parser.add_argument("--plan-type", required=True, choices=VALID_PLAN_TYPES, help="Plan type: plan-only or plan-and-apply")
    parser.add_argument("--message", default=None, help="Optional message for the run")
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

    run_data = create_run(args.workspace_id, tfe_url, token, args.plan_type, args.message)

    # Output run ID for downstream scripts
    run_id = run_data.get("data", {}).get("id", "")
    print(json.dumps({"run_id": run_id, "plan_type": args.plan_type}, indent=2))


if __name__ == "__main__":
    main()
