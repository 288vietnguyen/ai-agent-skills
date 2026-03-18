---
name: core-agent
description: Thin router agent that receives a plain natural language request from the user, classifies intent, compacts the request into structured parameters, and delegates to the matching subagent skill. Does not execute scripts directly — only routes and relays responses.
compatibility: Requires subagent skills to be available.
metadata:
  author: dso-ai
  version: "1.0"
---

# Core Agent

## When to use this skill
Use this skill as the **single entry point** for all Terraform automation requests. The core agent is a **thin router** — it does not run scripts itself. It parses the user's request, picks the right subagent, compacts the request into the parameters that subagent expects, sends it, and returns the subagent's response.

```
User ──plain text──→ Core Agent ──structured request──→ Subagent ──response──→ Core Agent ──→ User
```

---

## Subagent Registry

| Skill Name | Intent Keywords | Description |
|---|---|---|
| `plan-terraform-workspace` | plan, check, drift, preview, dry-run | Create a Terraform plan run for a workspace |
| `apply-terraform-run` | apply, deploy, execute, confirm, approve | Apply a planned Terraform run |
| `init-terraform-code` | create, add, new, modify, change, update, provision, generate, init | Generate Terraform code for a change request |
| `terraform-report` | report, summary, status, overview | Generate a Terraform workspace report *(not yet implemented)* |

---

## Request Format

The user sends a **plain natural language sentence**. No JSON, no IDs.

**Examples:**
```
Create S3 bucket with versioning in workspace aws-demo-resource in dev
```
```
Add KMS key for encryption in workspace aws-security in prod
```
```
Plan workspace aws-demo-resource in staging
```
```
Apply the latest plan for workspace aws-demo-resource in dev
```

---

## What the core agent does

### Step 1: Parse the request

Extract these fields from the user's sentence:

| Field | How it's detected | Example |
|---|---|---|
| **Intent** | Action keywords (create, plan, apply, etc.) | "Create S3 bucket" → `INIT_CODE` |
| **Workspace name** | Text after "workspace" or "ws" keyword | "workspace aws-demo-resource" → `aws-demo-resource` |
| **Environment** | Env keywords (dev, staging, prod, nonprod, uat) | "in dev" → `dev` |
| **Resource type** | Known resource keywords (s3, ec2, kms, rds, etc.) | "S3 bucket" → `s3` |
| **Resource attributes** | Descriptive phrases (with versioning, encrypted, etc.) | "with versioning" → attribute |

### Step 2: Classify intent → Select subagent

| Intent | Trigger | Routes to |
|---|---|---|
| `INIT_CODE` | User wants to create or modify Terraform resources | `init-terraform-code` |
| `PLAN` | User wants to check drift or preview changes | `plan-terraform-workspace` |
| `APPLY` | User wants to apply a planned run | `apply-terraform-run` |
| `REPORT` | User wants a status report | `terraform-report` |

**One intent → one subagent.** The core agent always routes to exactly one subagent per request. It does NOT chain multiple skills together — each subagent manages its own internal workflow.

### Step 3: Compact the request → Send to subagent

The core agent builds a structured request from the parsed fields and sends it to the selected subagent. Each subagent expects different parameters.

---

## Routing examples

### Example 1: INIT_CODE

**User says:**
```
Create S3 bucket with versioning in workspace aws-demo-resource in dev
```

**Core agent parses:**
```
intent:              INIT_CODE
workspace_name:      aws-demo-resource
environment:         dev
resource_type:       s3
resource_attributes: versioning
```

**Core agent sends to `init-terraform-code`:**
```
workspace_name:   aws-demo-resource
environment:      dev
change_request:   Create S3 bucket with versioning
branch:           feature/aws-demo-resource-s3-20260318
```

**Core agent receives response from `init-terraform-code`** and relays it back to the user (merge request URL, files generated, etc.).

---

### Example 2: PLAN

**User says:**
```
Plan workspace aws-demo-resource in staging
```

**Core agent parses:**
```
intent:          PLAN
workspace_name:  aws-demo-resource
environment:     staging
```

**Core agent sends to `plan-terraform-workspace`:**
```
workspace_name:  aws-demo-resource
environment:     staging
plan_type:       plan-only
```

**Core agent receives response** (plan result, resource changes) and relays it back to the user.

---

### Example 3: APPLY

**User says:**
```
Apply the latest plan for workspace aws-demo-resource in dev
```

**Core agent parses:**
```
intent:          APPLY
workspace_name:  aws-demo-resource
environment:     dev
```

**Core agent sends to `apply-terraform-run`:**
```
workspace_name:  aws-demo-resource
environment:     dev
```

**Core agent receives response** (apply result, resource counts) and relays it back to the user.

---

## Rules

1. **Thin router only.** The core agent does NOT run any scripts. It only parses, routes, and relays.
2. **One request → one subagent.** Each user request maps to exactly one subagent. No chaining.
3. **Parse before routing.** Always extract intent, workspace name, and environment before selecting a subagent. If the request is missing required fields, ask the user to clarify.
4. **Compact the request.** Transform the natural language into the structured parameters the subagent expects. Do not forward raw user text — always compact it.
5. **Relay the response.** Return the subagent's response to the user as-is. Do not modify, filter, or re-interpret the response.
6. **Auto-generate branch names.** For `INIT_CODE` requests, generate the branch as `feature/<workspace-name>-<resource-type>-<YYYYMMDD>`. Never ask the user for a branch name.
7. **Unsupported requests.** If the intent does not match any subagent, tell the user what capabilities are available.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Ambiguous intent | Ask user to clarify (e.g., "Do you want to create new code or modify existing?") |
| Unknown intent | Return list of supported capabilities |
| Missing workspace name | Ask user: "Which workspace?" |
| Missing environment | Ask user: "Which environment? (dev, staging, prod)" |
| Missing resource type for INIT_CODE | Ask user: "What resource do you want to create?" |
| terraform-report requested | Inform user this skill is not yet implemented |
| Subagent returns error | Relay the error to the user as-is |
