#!/usr/bin/env python3
"""
Validate that a Terraform run is of type 'plan and apply' (not plan-only or destroy).

Environment variables:
    TFE_URL   - Terraform Enterprise URL (e.g., https://app.terraform.io)
    TFE_TOKEN - Terraform Enterprise API token

Usage:
    python validate_plan_and_apply.py --run-id <run_id>

Exit codes:
    0 - Run is a plan-and-apply run
    1 - Run is not a plan-and-apply run
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


def validate_plan_and_apply(run_data: dict) -> bool:
    """Validate that the run is a plan-and-apply operation."""
    attributes = run_data.get("data", {}).get("attributes", {})
    is_plan_only = attributes.get("plan-only", False)
    is_destroy = attributes.get("is-destroy", False)

    print(f"Plan only: {is_plan_only}")
    print(f"Is destroy: {is_destroy}")

    if is_plan_only:
        print(
            "ERROR: Run is plan-only. Cannot apply a plan-only run.",
            file=sys.stderr,
        )
        return False

    if is_destroy:
        print(
            "ERROR: Run is a destroy plan. This skill only supports plan-and-apply runs.",
            file=sys.stderr,
        )
        return False

    print("PASS: Run is a valid plan-and-apply run.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Validate Terraform run is plan-and-apply")
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
    if not validate_plan_and_apply(run_data):
        sys.exit(1)


if __name__ == "__main__":
    main()
