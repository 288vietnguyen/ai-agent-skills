#!/usr/bin/env python3
"""Check MemoryDB for similar past executions before running the full flow.

This script runs FIRST (Step 0) and outputs JSON indicating whether
a cache hit was found. On a cache hit, the caller should skip Steps 1-3
and pass the cached context directly to generate_terraform_code.py.

Environment variables:
    AWS_REGION                  - AWS region for Bedrock embeddings
    MEMORYDB_HOST               - Redis/MemoryDB endpoint (required)
    MEMORYDB_PORT               - Redis port (default: 6379)
    MEMORYDB_USERNAME           - Redis username (optional)
    MEMORYDB_PASSWORD           - Redis password (optional)
    MEMORY_SIMILARITY_THRESHOLD - Cosine similarity threshold (default: 0.85)

Usage:
    python3 check_memory.py --change-request "Create an S3 bucket for logs"

Output (JSON to stdout):
    {
        "cache_hit": true,
        "similarity_score": 0.92,
        "cached_context": { ... ExecutionContext fields ... },
        "skip_steps": ["validate", "clone", "fetch"]
    }

    OR on cache miss / memory unavailable:
    {
        "cache_hit": false,
        "reason": "no similar past execution found"
    }

Exit codes:
    0 - Always (cache hit or miss). The caller reads JSON output to decide.
    1 - Only on argument errors.
"""

import argparse
import json
import os
import sys
import time


def _init_memory(region: str):
    """Initialize MemoryManager with retry."""
    redis_host = os.environ.get("MEMORYDB_HOST", "")
    if not redis_host:
        return None

    redis_port = int(os.environ.get("MEMORYDB_PORT", "6379"))
    redis_username = os.environ.get("MEMORYDB_USERNAME", "")
    redis_password = os.environ.get("MEMORYDB_PASSWORD", "")
    threshold = float(os.environ.get("MEMORY_SIMILARITY_THRESHOLD", "0.85"))
    ttl_days = int(os.environ.get("MEMORY_TTL_DAYS", "90"))

    from memory.embeddings import BedrockEmbeddings
    from memory.redis_store import RedisMemoryStore
    from memory.manager import MemoryManager

    for attempt in range(1, 3):
        try:
            embeddings = BedrockEmbeddings(region=region)
            store = RedisMemoryStore(
                host=redis_host, port=redis_port,
                username=redis_username, password=redis_password,
                ttl_days=ttl_days,
            )
            store.client.ping()
            manager = MemoryManager(embeddings=embeddings, store=store, threshold=threshold)
            print(f"  Memory connected: {redis_host}:{redis_port}", file=sys.stderr)
            return manager
        except Exception as e:
            print(f"  WARNING: Memory init attempt {attempt}/2 failed: {e}", file=sys.stderr)
            if attempt < 2:
                time.sleep(2)

    return None


def main():
    parser = argparse.ArgumentParser(description="Check memory for similar past executions")
    parser.add_argument("--change-request", required=True, help="Description of the change request")
    parser.add_argument("--region", default=None, help="AWS region (overrides AWS_REGION)")
    args = parser.parse_args()

    region = args.region or os.environ.get("AWS_REGION", "ap-southeast-1")

    print("\n=== Step 0: Memory Lookup ===", file=sys.stderr)

    memory = _init_memory(region)
    if not memory:
        result = {"cache_hit": False, "reason": "memory not available"}
        print(json.dumps(result))
        print("  Memory not available — run full flow.", file=sys.stderr)
        return

    print("  Searching for similar past executions...", file=sys.stderr)
    cached_context = memory.find_similar(args.change_request)

    if cached_context:
        print(f"  CACHE HIT (similarity={cached_context.similarity_score:.3f})", file=sys.stderr)
        print(f"  Previous request: \"{cached_context.change_request}\"", file=sys.stderr)
        result = {
            "cache_hit": True,
            "similarity_score": cached_context.similarity_score,
            "skip_steps": ["validate", "clone", "fetch"],
            "cached_context": {
                "change_request": cached_context.change_request,
                "workspace_id": cached_context.workspace_id,
                "workspace_name": cached_context.workspace_name,
                "vcs_repo_url": cached_context.vcs_repo_url,
                "vcs_branch": cached_context.vcs_branch,
                "working_dir": cached_context.working_dir,
                "standards": cached_context.standards,
                "templates": cached_context.templates,
                "generated_code": cached_context.generated_code,
                "resource_types": cached_context.resource_types,
                "execution_mode": cached_context.execution_mode,
            },
        }
    else:
        print("  No similar past execution found — run full flow.", file=sys.stderr)
        result = {"cache_hit": False, "reason": "no similar past execution found"}

    print(json.dumps(result))


if __name__ == "__main__":
    main()
