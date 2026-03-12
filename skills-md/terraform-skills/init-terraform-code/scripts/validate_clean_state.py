#!/usr/bin/env python3
"""
Validate that a Terraform workspace is in a clean state (last run finished
with 0 resource changes) using the output from the plan-terraform-workspace skill.

Usage:
    python3 validate_clean_state.py --plan-result '<json>'

Exit codes:
    0 - Workspace is clean (0 resource changes)
    1 - Workspace has drift or last run is not finished
"""

import argparse
import json
import sys

TERMINAL_SUCCESS_STATES = {"planned", "planned_and_finished", "applied"}


def validate_plan_result(plan_result_json: str) -> bool:
    """Validate clean state from a plan-terraform-workspace skill output."""
    try:
        result = json.loads(plan_result_json)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid plan result JSON: {e}", file=sys.stderr)
        return False

    status = result.get("status", "")
    additions = result.get("resource_additions", -1)
    changes = result.get("resource_changes", -1)
    destructions = result.get("resource_destructions", -1)

    print(f"Plan result — status: {status}, additions: {additions}, changes: {changes}, destructions: {destructions}")

    if status not in TERMINAL_SUCCESS_STATES:
        print(f"ERROR: Last run status is '{status}', expected one of {TERMINAL_SUCCESS_STATES}.", file=sys.stderr)
        return False

    if additions != 0 or changes != 0 or destructions != 0:
        print(
            f"ERROR: Workspace has resource drift — "
            f"additions: {additions}, changes: {changes}, destructions: {destructions}. "
            f"Expected 0 changes.",
            file=sys.stderr,
        )
        return False

    print("PASS: Workspace is clean (0 resource changes).")
    return True


def main():
    parser = argparse.ArgumentParser(description="Validate Terraform workspace is in a clean state")
    parser.add_argument("--plan-result", required=True, help="JSON output from plan-terraform-workspace skill")
    args = parser.parse_args()

    if not validate_plan_result(args.plan_result):
        sys.exit(1)


if __name__ == "__main__":
    main()
