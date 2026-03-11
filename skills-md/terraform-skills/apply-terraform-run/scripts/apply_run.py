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
import json
import os
import sys
import urllib.request
import urllib.error


def apply_run(run_id: str, tfe_url: str, token: str, comment: str = None) -> bool:
    """Send apply action to Terraform Enterprise API."""
    url = f"{tfe_url}/api/v2/runs/{run_id}/actions/apply"

    payload = {}
    if comment:
        payload["comment"] = comment

    data = json.dumps(payload).encode("utf-8") if payload else None

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/vnd.api+json")

    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status == 202:
                print(f"SUCCESS: Apply request for run {run_id} has been queued.")
                return True
            print(f"Unexpected response status: {resp.status}")
            return False
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        if e.code == 409:
            print(
                f"ERROR: Run {run_id} is not in a state that allows apply. "
                f"The run must be in 'planned' state. Response: {body}",
                file=sys.stderr,
            )
        else:
            print(f"ERROR: Failed to apply run {run_id}: HTTP {e.code} - {body}", file=sys.stderr)
        return False
    except urllib.error.URLError as e:
        print(f"ERROR: Could not connect to {tfe_url}: {e.reason}", file=sys.stderr)
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
