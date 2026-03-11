#!/usr/bin/env python3
"""
Apply a Terraform run using the Terraform Enterprise REST API.

Environment variables:
    TFE_URL   - Terraform Enterprise URL (e.g., https://app.terraform.io)
    TFE_TOKEN - Terraform Enterprise API token

Usage:
    python apply_run.py --run-id <run_id> [--comment <comment>]

Exit codes:
    0 - Apply request was successfully queued (HTTP 202)
    1 - Apply request failed
"""

import argparse
import os
import sys

import requests


def apply_run(run_id: str, tfe_url: str, token: str, comment: str = None) -> bool:
    """Send apply action to Terraform Enterprise API."""
    url = f"{tfe_url}/api/v2/runs/{run_id}/actions/apply"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/vnd.api+json",
    }

    payload = {}
    if comment:
        payload["comment"] = comment

    try:
        resp = requests.post(url, headers=headers, json=payload if payload else None)
        if resp.status_code == 202:
            print(f"SUCCESS: Apply request for run {run_id} has been queued.")
            return True
        if resp.status_code == 409:
            print(
                f"ERROR: Run {run_id} is not in a state that allows apply. "
                f"The run must be in 'planned' state. Response: {resp.text}",
                file=sys.stderr,
            )
        else:
            print(f"ERROR: Failed to apply run {run_id}: HTTP {resp.status_code} - {resp.text}", file=sys.stderr)
        return False
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Could not connect to {tfe_url}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Apply a Terraform run")
    parser.add_argument("--run-id", required=True, help="Terraform run ID (e.g., run-xxxxx)")
    parser.add_argument("--tfe-url", default=None, help="TFE URL (overrides TFE_URL env var)")
    parser.add_argument("--token", default=None, help="TFE API token (overrides TFE_TOKEN env var)")
    parser.add_argument("--comment", default=None, help="Optional comment for the apply action")
    args = parser.parse_args()

    tfe_url = args.tfe_url or os.environ.get("TFE_URL")
    token = args.token or os.environ.get("TFE_TOKEN")

    if not tfe_url:
        print("ERROR: TFE_URL env var or --tfe-url flag is required.", file=sys.stderr)
        sys.exit(1)
    if not token:
        print("ERROR: TFE_TOKEN env var or --token flag is required.", file=sys.stderr)
        sys.exit(1)

    if not apply_run(args.run_id, tfe_url, token, args.comment):
        sys.exit(1)


if __name__ == "__main__":
    main()
