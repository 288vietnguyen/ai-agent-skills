# Apply Terraform Run

## Description
This skill applies a Terraform run using the Terraform Enterprise (TFE) REST API. It validates the run state, confirms it is a plan-and-apply operation, triggers the apply, and polls for the final result.

## Required Inputs

### Environment Variables
Set these before running the scripts:
```bash
export TFE_URL="https://app.terraform.io"     # Terraform Enterprise base URL
export TFE_TOKEN="your-user-or-team-token"     # API token (org tokens NOT supported)
```

### Script Arguments
- `--run-id` (required) - The Terraform run ID (e.g., `run-CZcmD7eagjhyX0vN`)
- `--tfe-url` (optional) - Overrides `TFE_URL` env var
- `--token` (optional) - Overrides `TFE_TOKEN` env var

## Flow

### Step 1: Validate Run State
Confirm the run is in `planned` state with no errors.

```bash
python3 scripts/validate_run_state.py --run-id "$RUN_ID"
```

**Validates:**
- Run status is `planned` (not `errored`, `discarded`, etc.)
- No error messages present on the run

**Exit code 0** = pass, **exit code 1** = fail (abort the skill).

---

### Step 2: Validate Plan and Apply
Confirm the run is a standard plan-and-apply operation (not plan-only or destroy).

```bash
python3 scripts/validate_plan_and_apply.py --run-id "$RUN_ID"
```

**Validates:**
- `plan-only` is `false`
- `is-destroy` is `false`

**Exit code 0** = pass, **exit code 1** = fail (abort the skill).

---

### Step 3: Apply the Run
Send the apply action to the TFE REST API.

```bash
python3 scripts/apply_run.py --run-id "$RUN_ID" --comment "Applied via DSO AI agent"
```

**API call:** `POST /api/v2/runs/{run_id}/actions/apply`

**Expected response:** HTTP 202 (apply queued successfully).

---

### Step 4: Get Run Result
Poll the run status until it reaches a terminal state and report the outcome.

```bash
python3 scripts/get_run_result.py --run-id "$RUN_ID" --poll-interval 10 --timeout 600
```

**Polls until status is one of:** `applied`, `errored`, `discarded`, `canceled`, `force_canceled`

**Output:** JSON summary with run status, resource additions/changes/destructions.

**Exit code 0** = `applied` successfully, **exit code 1** = any other terminal state.

---

## Error Handling
| Scenario | Behavior |
|---|---|
| Run not in `planned` state | Step 1 fails with descriptive error |
| Run is plan-only or destroy | Step 2 fails with descriptive error |
| HTTP 409 on apply | Run was not paused for confirmation |
| Apply times out | Step 4 exits after timeout (default 600s) |
| Network/auth errors | All scripts exit with clear error messages |

## API Reference
- [Terraform Cloud Runs API](https://developer.hashicorp.com/terraform/cloud-docs/api-docs/run)
- Apply endpoint: `POST /api/v2/runs/:run_id/actions/apply`
- Get run endpoint: `GET /api/v2/runs/:run_id`
