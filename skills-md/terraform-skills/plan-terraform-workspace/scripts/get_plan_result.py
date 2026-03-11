#!/usr/bin/env python3
"""
Poll a Terraform run until planning is complete, then retrieve the plan result
including all changed resources.

Environment variables:
    TFE_URL   - Terraform Enterprise URL (e.g., https://app.terraform.io)
    TFE_TOKEN - Terraform Enterprise API token

Usage:
    python3 get_plan_result.py --run-id <run_id> [--poll-interval <seconds>] [--timeout <seconds>]

Exit codes:
    0 - Plan completed successfully
    1 - Plan failed, was canceled, or timed out
"""

import argparse
import json
import os
import sys
import time

import requests

# States where the plan is still in progress
IN_PROGRESS_STATES = {"pending", "plan_queued", "planning", "cost_estimating", "policy_checking"}

# States where the plan has finished (success or failure)
PLAN_FINISHED_STATES = {
    "planned", "planned_and_finished",
    "cost_estimated", "policy_checked", "policy_override", "policy_soft_failed",
    "errored", "discarded", "canceled", "force_canceled",
}


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


def get_plan_json(plan_id: str, tfe_url: str, token: str) -> dict:
    """Fetch the JSON plan output to get detailed resource changes."""
    url = f"{tfe_url}/api/v2/plans/{plan_id}/json-output"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError:
        print(f"WARNING: Could not fetch plan JSON output: HTTP {resp.status_code}", file=sys.stderr)
        return {}
    except requests.exceptions.ConnectionError:
        print(f"WARNING: Could not connect to {tfe_url} for plan JSON", file=sys.stderr)
        return {}


def poll_plan(run_id: str, tfe_url: str, token: str, poll_interval: int, timeout: int) -> dict:
    """Poll the run until planning is complete or times out."""
    start_time = time.time()

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            print(f"ERROR: Timed out after {timeout}s waiting for plan to complete.", file=sys.stderr)
            sys.exit(1)

        run_data = get_run(run_id, tfe_url, token)
        attributes = run_data.get("data", {}).get("attributes", {})
        status = attributes.get("status", "")

        print(f"[{int(elapsed)}s] Run status: {status}")

        if status in PLAN_FINISHED_STATES:
            return run_data

        if status not in IN_PROGRESS_STATES:
            print(f"WARNING: Unexpected status '{status}', continuing to poll...", file=sys.stderr)

        time.sleep(poll_interval)


def extract_resource_changes(plan_json: dict) -> list:
    """Extract resource changes from the plan JSON output."""
    changes = []
    for rc in plan_json.get("resource_changes", []):
        change = rc.get("change", {})
        actions = change.get("actions", [])

        # Skip no-op resources
        if actions == ["no-op"] or actions == ["read"]:
            continue

        changes.append({
            "address": rc.get("address", ""),
            "type": rc.get("type", ""),
            "name": rc.get("name", ""),
            "provider": rc.get("provider_name", ""),
            "actions": actions,
        })

    return changes


def format_result(run_data: dict, resource_changes: list) -> str:
    """Format the plan result for output."""
    attributes = run_data.get("data", {}).get("attributes", {})
    run_id = run_data.get("data", {}).get("id", "unknown")
    status = attributes.get("status", "unknown")
    is_plan_only = attributes.get("plan-only", False)

    result = {
        "run_id": run_id,
        "status": status,
        "plan_type": "plan-only" if is_plan_only else "plan-and-apply",
        "resource_additions": attributes.get("resource-additions", 0),
        "resource_changes": attributes.get("resource-changes", 0),
        "resource_destructions": attributes.get("resource-destructions", 0),
        "changed_resources": resource_changes,
    }

    return json.dumps(result, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Get Terraform plan result")
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

    print(f"Polling run {args.run_id} for plan completion...")
    run_data = poll_plan(args.run_id, tfe_url, token, args.poll_interval, args.timeout)

    status = run_data.get("data", {}).get("attributes", {}).get("status", "")

    # Fetch detailed resource changes from plan JSON output
    plan_id = run_data.get("data", {}).get("relationships", {}).get("plan", {}).get("data", {}).get("id", "")
    resource_changes = []
    if plan_id:
        plan_json = get_plan_json(plan_id, tfe_url, token)
        resource_changes = extract_resource_changes(plan_json)

    result = format_result(run_data, resource_changes)
    print(f"\n--- Plan Result ---\n{result}")

    error_states = {"errored", "discarded", "canceled", "force_canceled"}
    if status in error_states:
        print(f"\nERROR: Plan ended with status '{status}'.", file=sys.stderr)
        sys.exit(1)

    print("\nSUCCESS: Plan completed successfully.")


if __name__ == "__main__":
    main()
