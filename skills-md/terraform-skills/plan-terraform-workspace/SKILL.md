---
name: plan-terraform-workspace
description: Plan a Terraform workspace via the TFE REST API. Use when a Terraform workspace needs a new plan. Supports plan-only (speculative) and plan-and-apply types. Validates workspace lock state, creates a plan run, and returns results including all changed resources.
compatibility: Requires python3 and the requests package. Requires network access to Terraform Enterprise.
metadata:
  author: dso-ai
  version: "1.0"
---

# Plan Terraform Workspace

## When to use this skill
Use this skill when you need to create a Terraform plan on a workspace. Supports two plan types:
- **plan-only** — speculative plan, cannot be applied afterward
- **plan-and-apply** — standard run that can be applied later

## Required Inputs

### Environment Variables
Set these before running the scripts:
```bash
export TFE_URL="https://app.terraform.io"     # Terraform Enterprise base URL
export TFE_TOKEN="your-user-or-team-token"     # API token (org tokens NOT supported)
```

### Script Arguments
- `--workspace-id` (required) - The Terraform workspace ID (e.g., `ws-CZcmD7eagjhyX0vN`)
- `--plan-type` (required) - `plan-only` or `plan-and-apply`
- `--tfe-url` (optional) - Overrides `TFE_URL` env var
- `--token` (optional) - Overrides `TFE_TOKEN` env var

## Flow

### Step 1: Validate Workspace
Confirm the workspace is not locked and the last run is finished.

```bash
python3 scripts/validate_workspace.py --workspace-id "$WORKSPACE_ID"
```

**Validates:**
- Workspace is **not locked** — if locked, aborts with lock owner details
- Last run is **not in progress** — if the last run is still planning, retries up to 3 times with a 5-minute wait between each retry

**Exit code 0** = pass, **exit code 1** = fail (abort the skill).

---

### Step 2: Plan the Workspace
Create a new plan run on the workspace.

```bash
python3 scripts/plan_workspace.py --workspace-id "$WORKSPACE_ID" --plan-type "plan-and-apply"
```

Or for a speculative plan:
```bash
python3 scripts/plan_workspace.py --workspace-id "$WORKSPACE_ID" --plan-type "plan-only"
```

**API call:** `POST /api/v2/runs`

**Output:** JSON with `run_id` and `plan_type` for use in Step 3.

---

### Step 3: Get Plan Result
Poll the run status until the plan completes, then retrieve the result with all changed resources.

```bash
python3 scripts/get_plan_result.py --run-id "$RUN_ID" --poll-interval 10 --timeout 600
```

**Polls until status is one of:** `planned`, `planned_and_finished`, `errored`, `discarded`, `canceled`, `force_canceled`

**Output:** JSON summary including:
- Run status and plan type
- Resource additions, changes, and destructions counts
- List of all changed resources with address, type, name, provider, and actions

**Exit code 0** = plan completed successfully, **exit code 1** = plan failed.

---

## Error Handling
| Scenario | Behavior |
|---|---|
| Workspace is locked | Step 1 aborts with lock owner details |
| Last run still planning | Step 1 retries 3 times (5 min intervals), then aborts |
| Invalid plan type | Step 2 rejects with argparse error |
| Plan times out | Step 3 exits after timeout (default 600s) |
| Network/auth errors | All scripts exit with clear error messages |

## API Reference
- [Terraform Cloud Runs API](https://developer.hashicorp.com/terraform/cloud-docs/api-docs/run)
- [Terraform Cloud Plans API](https://developer.hashicorp.com/terraform/cloud-docs/api-docs/plans)
- Create run endpoint: `POST /api/v2/runs`
- Get run endpoint: `GET /api/v2/runs/:run_id`
- Get plan JSON: `GET /api/v2/plans/:plan_id/json-output`
- List workspace runs: `GET /api/v2/workspaces/:workspace_id/runs`
