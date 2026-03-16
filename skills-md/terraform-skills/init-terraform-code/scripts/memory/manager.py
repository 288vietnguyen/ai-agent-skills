#!/usr/bin/env python3
"""MemoryManager orchestrates embedding generation and Redis store operations.

Provides a simple interface for the main skill flow:
  - find_similar(): check if a similar request was executed before
  - remember(): store the current execution for future reuse
"""

import sys

from memory.embeddings import BedrockEmbeddings
from memory.models import ExecutionContext
from memory.redis_store import RedisMemoryStore

DEFAULT_THRESHOLD = 0.85
DEFAULT_TOP_K = 3


class MemoryManager:
    """High-level memory interface for the init-terraform-code skill."""

    def __init__(self, embeddings: BedrockEmbeddings, store: RedisMemoryStore,
                 threshold: float = DEFAULT_THRESHOLD):
        self.embeddings = embeddings
        self.store = store
        self.threshold = threshold

    def find_similar(self, change_request: str) -> ExecutionContext | None:
        """Search for a similar past execution.

        Args:
            change_request: The current change request text.

        Returns:
            The most similar ExecutionContext if above threshold, else None.
            Returns None on any error (graceful degradation).
        """
        try:
            print("  Searching memory for similar past executions...")
            embedding = self.embeddings.embed(change_request)
            results = self.store.search(
                query_embedding=embedding,
                top_k=DEFAULT_TOP_K,
                threshold=self.threshold,
            )

            if results:
                best = results[0]
                print(f"  MEMORY HIT: similarity={best.similarity_score:.3f}")
                print(f"    Previous request: \"{best.change_request}\"")
                print(f"    Workspace: {best.workspace_name} ({best.workspace_id})")
                print(f"    Mode: {best.execution_mode}")
                return best

            print("  No similar past execution found.")
            return None

        except Exception as e:
            print(f"  WARNING: Memory lookup failed: {e}", file=sys.stderr)
            print("  Proceeding without memory (full flow).", file=sys.stderr)
            return None

    def remember(self, context: ExecutionContext) -> bool:
        """Store an execution context in memory for future reuse.

        Args:
            context: The execution context to store.

        Returns:
            True if stored successfully, False on error.
        """
        try:
            print("  Storing execution context in memory...")
            embedding = self.embeddings.embed(context.change_request)
            self.store.store(context, embedding)
            print("  Execution context memorized successfully.")
            return True

        except Exception as e:
            print(f"  WARNING: Failed to store in memory: {e}", file=sys.stderr)
            print("  Execution completed but not memorized.", file=sys.stderr)
            return False
