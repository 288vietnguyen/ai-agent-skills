#!/usr/bin/env python3
"""
Poll and retrieve the final result of a Terraform run after apply.

Environment variables:
    TFE_URL   - Terraform Enterprise URL (e.g., https://app.terraform.io)
    TFE_TOKEN - Terraform Enterprise API token

Usage:
    python get_run_result.py --run-id <run_id> [--poll-interval <seconds>] [--timeout <seconds>]

Exit codes:
    0 - Run applied successfully
    1 - Run failed, was canceled, or timed out
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

# Terminal states where the run is no longer in progress
TERMINAL_STATES = {"applied", "errored", "discarded", "canceled", "force_canceled"}

# States indicating the apply is still in progress
IN_PROGRESS_STATES = {"confirmed", "apply_queued", "applying"}


def get_run(run_id: str, tfe_url: str, token: str) -> dict:
    """Fetch run details from Terraform Enterprise API."""
    url = f"{tfe_url}/api/v2/runs/{run_id}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/vnd.api+json")

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"ERROR: Failed to fetch run {run_id}: HTTP {e.code} - {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: Could not connect to {tfe_url}: {e.reason}", file=sys.stderr)
        sys.exit(1)


def poll_run_result(run_id: str, tfe_url: str, token: str, poll_interval: int, timeout: int) -> dict:
    """Poll the run until it reaches a terminal state or times out."""
    start_time = time.time()

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            print(f"ERROR: Timed out after {timeout}s waiting for run {run_id} to complete.", file=sys.stderr)
            sys.exit(1)

        run_data = get_run(run_id, tfe_url, token)
        attributes = run_data.get("data", {}).get("attributes", {})
        status = attributes.get("status", "")

        print(f"[{int(elapsed)}s] Run status: {status}")

        if status in TERMINAL_STATES:
            return run_data

        if status not in IN_PROGRESS_STATES:
            print(f"WARNING: Unexpected status '{status}', continuing to poll...", file=sys.stderr)

        time.sleep(poll_interval)


def format_result(run_data: dict) -> str:
    """Format the run result for output."""
    attributes = run_data.get("data", {}).get("attributes", {})
    run_id = run_data.get("data", {}).get("id", "unknown")
    status = attributes.get("status", "unknown")
    has_changes = attributes.get("has-changes", False)
    resource_additions = attributes.get("resource-additions", 0)
    resource_changes = attributes.get("resource-changes", 0)
    resource_destructions = attributes.get("resource-destructions", 0)

    result = {
        "run_id": run_id,
        "status": status,
        "has_changes": has_changes,
        "resource_additions": resource_additions,
        "resource_changes": resource_changes,
        "resource_destructions": resource_destructions,
    }

    return json.dumps(result, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Get Terraform run result")
    parser.add_argument("--run-id", required=True, help="Terraform run ID (e.g., run-xxxxx)")
    parser.add_argument("--tfe-url", default=None, help="TFE URL (overrides TFE_URL env var)")
    parser.add_argument("--token", default=None, help="TFE API token (overrides TFE_TOKEN env var)")
    parser.add_argument("--poll-interval", type=int, default=10, help="Seconds between status checks (default: 10)")
    parser.add_argument("--timeout", type=int, default=600, help="Max seconds to wait for completion (default: 600)")
    args = parser.parse_args()

    tfe_url = args.tfe_url or os.environ.get("TFE_URL")
    token = args.token or os.environ.get("TFE_TOKEN")

    if not tfe_url:
        print("ERROR: TFE_URL env var or --tfe-url flag is required.", file=sys.stderr)
        sys.exit(1)
    if not token:
        print("ERROR: TFE_TOKEN env var or --token flag is required.", file=sys.stderr)
        sys.exit(1)

    print(f"Polling run {args.run_id} for completion...")
    run_data = poll_run_result(args.run_id, tfe_url, token, args.poll_interval, args.timeout)

    status = run_data.get("data", {}).get("attributes", {}).get("status", "")
    result = format_result(run_data)
    print(f"\n--- Run Result ---\n{result}")

    if status != "applied":
        print(f"\nERROR: Run ended with status '{status}' (expected 'applied').", file=sys.stderr)
        sys.exit(1)

    print("\nSUCCESS: Run applied successfully.")


if __name__ == "__main__":
    main()
