#!/usr/bin/env python3
"""
Validate that a Terraform run is in 'planned' state and has no errors.

Environment variables:
    TFE_URL   - Terraform Enterprise URL (e.g., https://app.terraform.io)
    TFE_TOKEN - Terraform Enterprise API token

Usage:
    python validate_run_state.py --run-id <run_id>

Exit codes:
    0 - Run is in 'planned' state with no errors
    1 - Run is not in 'planned' state or has errors
"""

import argparse
import json
import os
import sys

import requests


def get_run(run_id: str, tfe_url: str, token: str) -> dict:
    """Fetch run details from Terraform Enterprise API."""
    url = f"{tfe_url}/api/v2/runs/{run_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/vnd.api+json",
    }

    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError:
        print(f"ERROR: Failed to fetch run {run_id}: HTTP {resp.status_code} - {resp.text}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Could not connect to {tfe_url}", file=sys.stderr)
        sys.exit(1)


def validate_run_state(run_data: dict) -> bool:
    """Validate that the run is in 'planned' state with no errors."""
    attributes = run_data.get("data", {}).get("attributes", {})
    status = attributes.get("status", "")
    has_changes = attributes.get("has-changes", False)
    error_message = attributes.get("status-timestamps", {})

    print(f"Run status: {status}")
    print(f"Has changes: {has_changes}")

    if status == "errored":
        message = attributes.get("message", "No error message available")
        print(f"ERROR: Run has errored - {message}", file=sys.stderr)
        return False

    if status != "planned":
        print(
            f"ERROR: Run is not in 'planned' state. Current state: '{status}'",
            file=sys.stderr,
        )
        return False

    print("PASS: Run is in 'planned' state with no errors.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Validate Terraform run state")
    parser.add_argument("--run-id", required=True, help="Terraform run ID (e.g., run-xxxxx)")
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

    run_data = get_run(args.run_id, tfe_url, token)
    if not validate_run_state(run_data):
        sys.exit(1)

    # Output run data as JSON for downstream consumption
    print(json.dumps(run_data, indent=2))


if __name__ == "__main__":
    main()
