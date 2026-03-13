---
name: init-terraform-code
description: Initialize new Terraform change request code. Validates workspace is clean using plan-terraform-workspace output, clones the workspace repo, fetches coding standards from S3, sends a prompt to Amazon Bedrock (Claude Opus 4.6) with all context to generate compliant Terraform code, then commits and pushes to SCM.
compatibility: Requires python3, requests, boto3, and git. Requires network access to Terraform Enterprise, AWS S3, Amazon Bedrock, and SCM (e.g., GitHub, GitLab).
metadata:
  author: dso-ai
  version: "2.0"
---

# Init Terraform Code

## When to use this skill
Use this skill when you need to initialize new Terraform code for a change request. This skill ensures the workspace is in a clean state, fetches organizational standards, generates compliant code, and pushes it to the workspace SCM repository.

## Required Inputs

### Environment Variables
Set these before running the scripts:
```bash
export TFE_URL="https://app.terraform.io"     # Terraform Enterprise base URL
export TFE_TOKEN="your-user-or-team-token"     # API token (org tokens NOT supported)
export AWS_REGION="ap-southeast-1"             # AWS region for S3 and Bedrock
export STANDARDS_PREFIX="standards/"           # S3 key prefix for standards files
export STANDARDS_FILES="structure.md,requirements.md,best_practices.md"  # Comma-separated .md files to fetch
export BEDROCK_MODEL_ID="us.anthropic.claude-opus-4-6-20250610"  # (optional) Bedrock model override
```

### Script Arguments
- `--workspace-id` (required) - The Terraform workspace ID (e.g., `ws-CZcmD7eagjhyX0vN`)
- `--plan-result` (required) - JSON output from the `plan-terraform-workspace` skill
- `--standards-bucket` (required) - S3 bucket name containing Terraform standards
- `--change-request` (required) - Description of the change request to implement
- `--branch` (required) - Branch name for the change request
- `--tfe-url` (optional) - Overrides `TFE_URL` env var
- `--token` (optional) - Overrides `TFE_TOKEN` env var

## Flow

### Step 1: Validate Clean State
Verify the workspace is clean using the output from the `plan-terraform-workspace` skill. The plan result must show 0 resource changes (no drift).

```bash
python3 scripts/validate_clean_state.py --plan-result "$PLAN_RESULT_JSON"
```

**Validates:**
- Last run status is a terminal success state (`planned`, `planned_and_finished`, `applied`)
- Resource changes count is **0** (additions = 0, changes = 0, destructions = 0)

**Exit code 0** = pass (workspace is clean), **exit code 1** = fail (abort the skill).

---

### Step 2: Clone Workspace Repository
Retrieve VCS configuration from the workspace and clone the source code repository. The SCM domain is auto-detected from the workspace VCS config.

```bash
python3 scripts/clone_workspace_repo.py --workspace-id "$WORKSPACE_ID" --clone-dir "./workspace-repo"
```

**Actions:**
1. Fetches workspace VCS config via `GET /api/v2/workspaces/{workspace_id}`
2. Uses `repository-http-url` from `data.vcs-repo` as the clone URL
3. Clones the repository to the specified directory

**Output:** JSON with clone details:
- `repo_identifier` — SCM repository (e.g., `org/repo`)
- `clone_dir` — Local path to the cloned repo
- `working_dir` — Terraform working directory within the repo
- `default_branch` — Repository default branch

**Exit code 0** = cloned successfully, **exit code 1** = failed.

---

### Step 3: Fetch Standards from S3
Download Terraform standards (`.md` files) from an S3 bucket. The prefix and file list are configured via environment variables.

```bash
python3 scripts/fetch_standards.py --bucket "$STANDARDS_BUCKET" --output-dir "./standards"
```

**Configuration (env vars):**
- `STANDARDS_PREFIX` — S3 key prefix (default: `standards/`)
- `STANDARDS_FILES` — Comma-separated list of `.md` filenames to download (e.g., `structure.md,requirements.md,best_practices.md`)

Both can be overridden via `--prefix` and `--files` CLI arguments.

**Example files:**
- `structure.md` — Required file/directory structure for Terraform projects
- `requirements.md` — Coding requirements and constraints
- `best_practices.md` — Best practices and naming conventions

**Output:** JSON listing all downloaded standard files with their local paths.

**Exit code 0** = standards fetched, **exit code 1** = failed.

---

### Step 4: Generate Terraform Code via Amazon Bedrock
Send a prompt to Amazon Bedrock (Claude Opus 4.6) with full context to generate compliant Terraform code. The script auto-detects whether this is a **CREATE** or **MODIFY** request.

```bash
python3 scripts/generate_terraform_code.py \
  --change-request "$CHANGE_REQUEST" \
  --standards-dir "./standards" \
  --workspace-dir "./workspace-repo/$WORKING_DIR" \
  --output-dir "./generated"
```

**Two modes:**

- **CREATE mode** — Triggered when the change request contains creation keywords (`create`, `add`, `new`, `provision`, `deploy`, `setup`, `set up`, `init`) **and** a known resource type keyword (e.g., `s3`). The prompt includes resource templates from the `assets/terraform-template/` folder as reference patterns.
- **MODIFY mode** — When no new resource creation is detected. The prompt includes only existing workspace code and standards.

**Resource template structure** (`assets/terraform-template/`):
```
assets/terraform-template/
├── module-nonprod/
│   └── s3/                    # S3 module template
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       ├── data.tf
│       └── context.tf
└── regions/
    └── region-code/
        └── environment/       # Environment-level template
            ├── locals.tf
            ├── main.tf
            ├── provider.tf
            └── data.tf
```

**Prompt sent to Bedrock includes:**
- **Change request** — what needs to be implemented
- **All standards `.md` files** — fetched from S3 in Step 3
- **Resource templates** (CREATE mode only) — matching templates from assets folder
- **Existing code** — all `.tf` files from the cloned workspace for context

**Actions:**
1. Loads all `.md` standard files from Step 3 output directory
2. Reads all existing `.tf` files from the cloned workspace (Step 2)
3. Detects resource types from the change request keywords
4. Loads matching templates from `assets/terraform-template/` (CREATE mode)
5. Builds a structured prompt with all context
6. Invokes Amazon Bedrock `claude-opus-4-6` to generate Terraform code
7. Parses the response into individual `.tf` files
8. Validates generated files against the required structure

**Optional arguments:**
- `--assets-dir` — Override default assets/terraform-template path
- `--model-id` — Override Bedrock model ID
- `--region` — Override AWS region

**Model:** `us.anthropic.claude-opus-4-6-20250610` (configurable via `--model-id` or `BEDROCK_MODEL_ID` env var)

**Output:** Generated Terraform files in the output directory, following the organizational standard structure.

**Exit code 0** = code generated successfully, **exit code 1** = generation failed.

---

### Step 5: Update, Commit, and Push to SCM
Copy generated code into the cloned workspace repo, commit, and push to a change request branch.

```bash
python3 scripts/push_to_scm.py \
  --repo-dir "./workspace-repo" \
  --source-dir "./generated" \
  --working-dir "$WORKING_DIR" \
  --branch "change-request/$CR_ID" \
  --commit-message "Init Terraform code for change request $CR_ID"
```

**Actions:**
1. Copies generated Terraform files into the workspace working directory
2. Creates a new change request branch
3. Stages and commits all changes
4. Pushes the branch to the remote

**Exit code 0** = pushed successfully, **exit code 1** = push failed.

---

## Error Handling
| Scenario | Behavior |
|---|---|
| Workspace has resource drift | Step 1 fails — workspace must be clean (0 changes) |
| Last run still in progress | Step 1 fails — run plan-terraform-workspace first |
| Invalid plan result JSON | Step 1 fails with parse error |
| Workspace has no VCS config | Step 2 fails — workspace must have VCS configured |
| Git clone fails | Step 2 exits with auth/network error details |
| S3 bucket not accessible | Step 3 fails with AWS error details |
| Standards files missing | Step 3 fails listing expected files |
| Bedrock credentials missing | Step 4 fails with AWS credentials error |
| Bedrock invocation fails | Step 4 exits with Bedrock API error details |
| Model response unparseable | Step 4 fails — cannot extract code blocks from response |
| Generated code missing required files | Step 4 warns with list of missing files |
| Branch already exists | Step 5 exits with conflict error |
| Git push fails | Step 5 exits with clear error message |
| Network/auth errors | All scripts exit with clear error messages |

## API Reference
- [Terraform Cloud Workspaces API](https://developer.hashicorp.com/terraform/cloud-docs/api-docs/workspaces)
- [Terraform Cloud Runs API](https://developer.hashicorp.com/terraform/cloud-docs/api-docs/run)
- [AWS S3 API](https://docs.aws.amazon.com/AmazonS3/latest/API/Welcome.html)
- [Amazon Bedrock InvokeModel API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeModel.html)
- Get workspace endpoint: `GET /api/v2/workspaces/:workspace_id`
- List workspace runs: `GET /api/v2/workspaces/:workspace_id/runs`
