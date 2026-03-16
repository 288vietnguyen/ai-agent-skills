# ai-agent-skills

## init-terraform-code

AI-powered Terraform code generation skill with long-term memory. Generates compliant Terraform code from a change request using Amazon Bedrock (Claude Opus 4.6), with Amazon MemoryDB (Redis VSS) for caching and reusing past execution contexts.

### Flow

```
Change Request
     │
     ▼
┌────────────────────────────────┐
│ Step 0: Memory Lookup          │
│ Embed request → search         │
│ MemoryDB for similar past runs │
└────────────┬───────────────────┘
             │
     ┌───────┴────────┐
     │                │
 CACHE HIT        CACHE MISS
(skip 1-3)       (full flow)
     │                │
     │    ┌───────────┴──────────────┐
     │    │ Step 1: Validate clean   │
     │    │ Step 2: Clone repo (VCS) │
     │    │ Step 3: Fetch standards  │
     │    └───────────┬──────────────┘
     │                │
     └───────┬────────┘
             ▼
┌────────────────────────────────┐
│ Step 4: Generate Terraform     │
│ code via Bedrock Claude Opus   │
│ (CREATE or MODIFY mode)        │
└────────────┬───────────────────┘
             ▼
┌────────────────────────────────┐
│ Step 5: Push to SCM            │
└────────────┬───────────────────┘
             ▼
┌────────────────────────────────┐
│ Step 6: Store execution in     │
│ MemoryDB for future reuse      │
└────────────────────────────────┘
```

### Key Features

- **Semantic memory** — Embeds change requests with Titan Embed Text V2 and stores execution contexts in Amazon MemoryDB (Redis VSS). Similar future requests skip validation, cloning, and standards fetching by reusing cached context.
- **CREATE / MODIFY modes** — Detects whether the request creates new resources or modifies existing ones. CREATE mode loads reference templates from `assets/terraform-template/`; MODIFY mode uses existing workspace code only.
- **Standards-driven** — Fetches organizational coding standards (`.md` files) from S3 and includes them in every Bedrock prompt.
- **Graceful degradation** — Works without MemoryDB. If `MEMORYDB_HOST` is not set or unreachable, the full flow runs with no errors.

### Tech Stack

| Component | Service |
|---|---|
| Code generation | Amazon Bedrock — Claude Opus 4.6 |
| Embeddings | Amazon Bedrock — Titan Embed Text V2 (1024-dim) |
| Long-term memory | Amazon MemoryDB (Redis VSS, HNSW index) |
| Standards storage | Amazon S3 |
| Infrastructure API | Terraform Enterprise REST API v2 |
| SCM | GitHub / GitLab (auto-detected from TFE VCS config) |

### Environment Variables

```bash
# Terraform Enterprise
TFE_URL="https://app.terraform.io"
TFE_TOKEN="your-api-token"

# AWS
AWS_REGION="ap-southeast-1"

# Standards (S3)
STANDARDS_PREFIX="standards/"
STANDARDS_FILES="structure.md,requirements.md,best_practices.md"

# Bedrock
BEDROCK_MODEL_ID="us.anthropic.claude-opus-4-6-20250610"

# MemoryDB (optional — enables memory/caching)
MEMORYDB_HOST="clustercfg.xxx.memorydb.ap-southeast-1.amazonaws.com"
MEMORYDB_PORT="6379"
MEMORY_SIMILARITY_THRESHOLD="0.85"
MEMORY_TTL_DAYS="90"
MEMORYDB_USERNAME="default"             # MemoryDB ACL username
MEMORYDB_PASSWORD="your-password"       # MemoryDB ACL password
```

### Project Structure

```
skills-md/terraform-skills/init-terraform-code/
├── SKILL.md
├── scripts/
│   ├── validate_clean_state.py
│   ├── clone_workspace_repo.py
│   ├── fetch_standards.py
│   ├── generate_terraform_code.py
│   ├── push_to_scm.py
│   └── memory/
│       ├── __init__.py
│       ├── embeddings.py      # Bedrock Titan Embed V2 wrapper
│       ├── models.py          # ExecutionContext dataclass
│       ├── redis_store.py     # MemoryDB VSS store
│       └── manager.py         # MemoryManager (find_similar + remember)
└── assets/
    └── terraform-template/
        ├── module-nonprod/
        │   └── s3/            # S3 module template
        └── regions/
            └── region-code/
                └── environment/  # Environment-level template
```
