#!/usr/bin/env python3
"""
Collect data from TFE API for generating TFE Test Plan and Test Report PDFs.

Fetches run details, plan JSON outputs, and resource changes for each workspace
run (rollout and rollback), then outputs a consolidated JSON file.

Environment variables:
    TFE_URL   - Terraform Enterprise URL (e.g., https://app.terraform.io)
    TFE_TOKEN - Terraform Enterprise API token

Usage:
    python3 collect_report_data.py \
        --action-change "Create S3 bucket with versioning" \
        --itsm-id "CHG0012345" \
        --aws-account-name "aws-demo-account" \
        --aws-account-id "123456789012" \
        --environment "nonprod" \
        --detail-workload "Deploy S3 bucket for data storage" \
        --workspace "ws-name-1:run-rollout-id-1:run-rollback-id-1" \
        --workspace "ws-name-2:run-rollout-id-2:run-rollback-id-2" \
        --output report_data.json

Exit codes:
    0 - Data collected successfully
    1 - Failed to collect data
"""

import argparse
import json
import os
import sys
from datetime import datetime

import requests


def get_headers(token: str) -> dict:
    """Return standard TFE API headers."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/vnd.api+json",
    }


def get_run(run_id: str, tfe_url: str, token: str) -> dict:
    """Fetch run details from Terraform Enterprise API."""
    url = f"{tfe_url}/api/v2/runs/{run_id}"
    try:
        resp = requests.get(url, headers=get_headers(token))
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError:
        print(f"ERROR: Failed to fetch run {run_id}: HTTP {resp.status_code} - {resp.text}", file=sys.stderr)
        return {}
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Could not connect to {tfe_url}", file=sys.stderr)
        return {}


def get_plan_json(plan_id: str, tfe_url: str, token: str) -> dict:
    """Fetch the JSON plan output to get detailed resource changes."""
    url = f"{tfe_url}/api/v2/plans/{plan_id}/json-output"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
        print(f"WARNING: Could not fetch plan JSON for plan {plan_id}", file=sys.stderr)
        return {}


def extract_resource_attributes(change: dict) -> list:
    """Extract key attribute names from the planned resource values."""
    after = change.get("after", {})
    if not after or not isinstance(after, dict):
        return []
    # Filter out internal/computed attributes
    skip_keys = {"id", "arn", "tags_all", "owner_id", "self"}
    return [k for k in after.keys() if k not in skip_keys and not k.startswith("_")]


def derive_test_objective(actions: list, resource_type: str) -> str:
    """Derive a human-readable test objective from actions and resource type."""
    # Map resource type to friendly name (e.g., aws_s3_bucket -> S3 Bucket)
    parts = resource_type.split("_")
    if parts[0] == "aws" and len(parts) > 1:
        friendly = " ".join(p.capitalize() for p in parts[1:])
    else:
        friendly = resource_type

    action_label_map = {
        "create": "Create New",
        "update": "Update",
        "delete": "Delete",
        "create-then-delete": "Replace",
        "delete-then-create": "Replace",
    }
    primary_action = actions[0] if actions else "create"
    label = action_label_map.get(primary_action, primary_action.capitalize())

    return f"{label} {friendly}"


def extract_resource_changes(plan_json: dict) -> list:
    """Extract resource changes from the plan JSON output."""
    changes = []
    for rc in plan_json.get("resource_changes", []):
        change = rc.get("change", {})
        actions = change.get("actions", [])

        if actions == ["no-op"] or actions == ["read"]:
            continue

        # Determine AWS service type from resource type
        resource_type = rc.get("type", "")
        aws_service = resource_type.split("_")[1].upper() if resource_type.startswith("aws_") else resource_type

        # Format action as created/changed/deleted
        action_map = {
            "create": "created",
            "update": "changed",
            "delete": "deleted",
            "create-then-delete": "replaced (create then delete)",
            "delete-then-create": "replaced (delete then create)",
        }
        action_str = ", ".join(action_map.get(a, a) for a in actions)

        # Extract attributes and test objective for Test Plan
        attributes = extract_resource_attributes(change)
        test_objective = derive_test_objective(actions, resource_type)

        changes.append({
            "address": rc.get("address", ""),
            "type": resource_type,
            "aws_service": f"AWS {aws_service}",
            "name": rc.get("name", ""),
            "provider": rc.get("provider_name", ""),
            "actions": actions,
            "action_summary": action_str,
            "test_objective": test_objective,
            "attributes": attributes,
        })

    return changes


def get_run_url(tfe_url: str, run_id: str) -> str:
    """Build the TFE run URL for linking in the report."""
    return f"{tfe_url}/app/runs/{run_id}"


def determine_result(rollout_status: str) -> str:
    """Determine overall test result: Accepted or Not Accepted."""
    if rollout_status in ("applied", "planned_and_finished", "planned"):
        return "Accepted"
    return "Not Accepted"


def collect_run_data(run_id: str, tfe_url: str, token: str, run_type: str) -> dict:
    """Collect run details and resource changes for a single run."""
    run_data = get_run(run_id, tfe_url, token)
    if not run_data:
        return {
            "run_id": run_id,
            "run_url": get_run_url(tfe_url, run_id),
            "status": "unknown",
            "resource_changes": [],
        }

    attributes = run_data.get("data", {}).get("attributes", {})
    status = attributes.get("status", "unknown")

    # Get plan JSON for resource changes
    plan_id = (
        run_data.get("data", {})
        .get("relationships", {})
        .get("plan", {})
        .get("data", {})
        .get("id", "")
    )

    resource_changes = []
    if plan_id:
        plan_json = get_plan_json(plan_id, tfe_url, token)
        resource_changes = extract_resource_changes(plan_json)

    return {
        "run_id": run_id,
        "run_url": get_run_url(tfe_url, run_id),
        "status": status,
        "resource_additions": attributes.get("resource-additions", 0),
        "resource_changes_count": attributes.get("resource-changes", 0),
        "resource_destructions": attributes.get("resource-destructions", 0),
        "resource_changes": resource_changes,
    }


def main():
    parser = argparse.ArgumentParser(description="Collect TFE report data")
    parser.add_argument("--action-change", required=True, help="Change request description")
    parser.add_argument("--itsm-id", required=True, help="ITSM request ID")
    parser.add_argument("--aws-account-name", required=True, help="AWS account name")
    parser.add_argument("--aws-account-id", required=True, help="AWS account ID")
    parser.add_argument("--environment", required=True, help="Environment (e.g., nonprod, prod)")
    parser.add_argument("--detail-workload", required=True, help="Detail of workload for this request")
    parser.add_argument("--workspace-name", required=True, help="TFE workspace name")
    parser.add_argument("--rollout-run-id", required=True, help="TFE run ID for rollout")
    parser.add_argument("--rollback-run-id", required=True, help="TFE run ID for rollback")
    parser.add_argument("--day-start", default=None, help="Testing start date (default: today)")
    parser.add_argument("--day-end", default=None, help="Testing end date (default: today)")
    parser.add_argument("--output", default="report_data.json", help="Output JSON file path")
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

    today = datetime.now().strftime("%Y-%m-%d")

    # Collect data for the workspace
    print(f"Collecting data for workspace: {args.workspace_name}")
    print(f"  Fetching rollout run: {args.rollout_run_id}")
    rollout_data = collect_run_data(args.rollout_run_id, tfe_url, token, "rollout")
    print(f"  Fetching rollback run: {args.rollback_run_id}")
    rollback_data = collect_run_data(args.rollback_run_id, tfe_url, token, "rollback")

    workspace = {
        "name": args.workspace_name,
        "rollout": rollout_data,
        "rollback": rollback_data,
    }

    test_result = determine_result(rollout_data.get("status", ""))

    report_data = {
        "action_change": args.action_change,
        "itsm_request_id": args.itsm_id,
        "day_start": args.day_start or today,
        "day_end": args.day_end or today,
        "aws_account_name": args.aws_account_name,
        "aws_account_id": args.aws_account_id,
        "environment": args.environment,
        "detail_workload": args.detail_workload,
        "test_result": test_result,
        "workspaces": [workspace],
    }

    with open(args.output, "w") as f:
        json.dump(report_data, f, indent=2)

    print(f"\nSUCCESS: Report data collected and saved to {args.output}")
    print(f"Test result: {test_result}")


if __name__ == "__main__":
    main()
