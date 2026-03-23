---
name: terraform-report
description: Generate TFE Test Plan and Test Report PDFs from Terraform Enterprise run data. Collects workspace run details (rollout/rollback), resource changes, and produces two formatted PDFs following the standard TFE templates.
compatibility: Requires python3, requests, and reportlab packages. Requires network access to Terraform Enterprise.
metadata:
  author: dso-ai
  version: "1.1"
---

# Terraform Report

## When to use this skill
Use this skill when a user wants to generate TFE Test Plan and Test Report PDFs. The skill produces **two PDF files** from the same input data:
1. **TFE Test Plan** — scope of testing, preparation, test approach with use cases, timeline
2. **TFE Test Report** — test execution summary, results, rollout/rollback details

## Required Inputs

### Environment Variables
Set these before running the scripts:
```bash
export TFE_URL="https://app.terraform.io"     # Terraform Enterprise base URL
export TFE_TOKEN="your-user-or-team-token"     # API token
```

### Request Inputs (from user)
| Input | Description |
|---|---|
| Request ID | ITSM request ID (e.g., "CHG0012345") |
| Request Change | Change request description (e.g., "Create S3 bucket with versioning") |
| TFE run for Rollout | Run ID(s) for rollout (e.g., "run-abc123") |
| TFE run for Rollback | Run ID(s) for rollback (e.g., "run-def456") |

### Script Arguments

**Step 1 — collect_report_data.py:**

| Argument | Required | Description |
|---|---|---|
| `--action-change` | Yes | Change request description |
| `--itsm-id` | Yes | ITSM request ID |
| `--aws-account-name` | Yes | AWS account name |
| `--aws-account-id` | Yes | AWS account ID |
| `--environment` | Yes | Environment name (e.g., nonprod, prod) |
| `--detail-workload` | Yes | Detail of workload for this request |
| `--workspace-name` | Yes | TFE workspace name |
| `--rollout-run-id` | Yes | TFE run ID for rollout |
| `--rollback-run-id` | Yes | TFE run ID for rollback |
| `--day-start` | No | Testing start date (default: today) |
| `--day-end` | No | Testing end date (default: today) |
| `--output` | No | Output JSON file path (default: report_data.json) |

**Step 2 — generate_report_pdf.py:**

| Argument | Required | Description |
|---|---|---|
| `--input` | Yes | Input JSON file from Step 1 |
| `--output-plan` | No | Output Test Plan PDF path (default: TFE_Test_Plan.pdf) |
| `--output-report` | No | Output Test Report PDF path (default: TFE_Test_Report.pdf) |

## Flow

### Step 1: Collect Report Data
Fetch run details and resource changes from TFE API for the workspace.

```bash
python3 scripts/collect_report_data.py \
    --action-change "Create S3 bucket with versioning" \
    --itsm-id "CHG0012345" \
    --aws-account-name "aws-demo-account" \
    --aws-account-id "123456789012" \
    --environment "nonprod" \
    --detail-workload "Deploy S3 bucket for data storage" \
    --workspace-name "ws-demo-nonprod" \
    --rollout-run-id "run-abc123" \
    --rollback-run-id "run-def456" \
    --output report_data.json
```

**What it does:**
- Fetches run details from TFE API (`GET /api/v2/runs/{run_id}`)
- Fetches plan JSON output (`GET /api/v2/plans/{plan_id}/json-output`)
- Extracts resource changes (created/changed/deleted) per workspace
- Extracts resource attributes for Test Plan use cases
- Derives test objectives (e.g., "Create New S3 Bucket", "Update Ec2 Instance")
- Determines overall test result (Accepted if all rollout runs succeeded)
- Saves consolidated data as JSON

**Exit code 0** = success, **exit code 1** = failure.

---

### Step 2: Generate PDFs
Generate both TFE Test Plan and Test Report PDFs from the collected data.

```bash
python3 scripts/generate_report_pdf.py \
    --input report_data.json \
    --output-plan TFE_Test_Plan.pdf \
    --output-report TFE_Test_Report.pdf
```

**What it does:**
- Reads the JSON data from Step 1
- Generates **two PDFs**:
  - **TFE Test Plan PDF** — cover page, scope, preparation, test approach table, timeline
  - **TFE Test Report PDF** — cover page, testing summary, test results with rollout/rollback

**Exit code 0** = success, **exit code 1** = failure.

---

## Template Structures

### TFE Test Plan

**Page 1 — Cover Page**
- **Title:** TFE Test Plan
- **Request Description:** from `--action-change`
- **ID:** ITSM - from `--itsm-id`
- **Sign-off table:** STT | Unit | Sign (DevSecOps, IT PM/DL, SOS, IT QE)

**Page 2+ — Plan Content**
- **1. Scope of Testing** — List of resource changes (Create New, Update, Delete)
- **2. Test Preparation** — AWS Account ID, Environment, TFE Workspace name
- **3. Test Approach** — Table: STT (UC1, UC2...) | Test Objective | Objective Attributes | Actual Result
- **4. Timeline** — System Testing from/to dates

### TFE Test Report

**Page 1 — Cover Page**
- **Title:** TFE Test Report
- **Request Description:** from `--action-change`
- **ID:** ITSM - from `--itsm-id`
- **Sign-off table:** STT | Unit | Sign (DevSecOps, IT PM/DL, SOS, IT QE)

**Page 2 — Summary of Testing Process**
- **1.1** Testing execution time (System Testing dates)
- **1.2** Test Participants (DSO System User, OAT)
- **1.3** Environment and Testing Tool (AWS Account details, workload)
- **1.4** Purpose and scope (Testing deploy infrastructure by Terraform)

**Pages 3+ — Test Result**
- **2.1** General Test result (Accepted / Not Accepted)
- **2.2** Summary table (TFE workspace results, verified resources)
- **2.3** Infrastructure Testing
  - **A. TFE Rollout** — Per workspace: run URL, resource overview table
  - **B. TFE Rollback** — Per workspace: run URL, resource overview table

---

## Error Handling

| Scenario | Behavior |
|---|---|
| TFE API unreachable | Step 1 prints error and exits with code 1 |
| Invalid run ID | Step 1 prints warning and continues with empty data |
| Missing input JSON | Step 2 exits with clear error message |
| Invalid JSON format | Step 2 exits with parsing error details |
| PDF generation fails | Step 2 exits with error details |

## API Reference
- [Terraform Cloud Runs API](https://developer.hashicorp.com/terraform/cloud-docs/api-docs/run)
- [Terraform Cloud Plans API](https://developer.hashicorp.com/terraform/cloud-docs/api-docs/plans)
- Get run: `GET /api/v2/runs/:run_id`
- Get plan JSON: `GET /api/v2/plans/:plan_id/json-output`
