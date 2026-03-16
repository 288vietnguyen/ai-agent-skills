#!/usr/bin/env python3
"""Amazon MemoryDB (Redis) vector store for execution context memory.

Uses Redis Vector Search (VSS) with HNSW index for semantic similarity
matching of change requests.
"""

import struct
import sys
import uuid
from datetime import datetime, timezone

from redis.cluster import RedisCluster
from redis.commands.search.field import TextField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from redis.exceptions import ResponseError

from memory.embeddings import EMBEDDING_DIMENSIONS
from memory.models import ExecutionContext

INDEX_NAME = "dso-execution-idx"
KEY_PREFIX = "dso:execution:"
DEFAULT_TTL_DAYS = 90


class RedisMemoryStore:
    """Store and retrieve execution contexts in Amazon MemoryDB with vector search."""

    def __init__(self, host: str, port: int = 6379, ssl: bool = True,
                 username: str = "", password: str = "",
                 index_name: str = INDEX_NAME, ttl_days: int = DEFAULT_TTL_DAYS):
        self.index_name = index_name
        self.ttl_days = ttl_days

        kwargs = {
            "host": host,
            "port": port,
            "ssl": ssl,
            "ssl_cert_reqs": None,
            "decode_responses": False,  # VSS needs bytes for vectors
        }
        if username:
            kwargs["username"] = username
        if password:
            kwargs["password"] = password

        self.client = RedisCluster(**kwargs)

        self._ensure_index()

    def _ensure_index(self):
        """Create the vector search index if it does not exist."""
        try:
            self.client.ft(self.index_name).info()
        except ResponseError:
            # Index does not exist — create it
            schema = (
                VectorField(
                    "embedding",
                    "HNSW",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": EMBEDDING_DIMENSIONS,
                        "DISTANCE_METRIC": "COSINE",
                    },
                ),
                TextField("change_request"),
                TextField("workspace_id"),
                TextField("workspace_name"),
                TextField("execution_mode"),
                TextField("resource_types"),
                TextField("created_at"),
            )

            definition = IndexDefinition(
                prefix=[KEY_PREFIX],
                index_type=IndexType.HASH,
            )

            self.client.ft(self.index_name).create_index(
                fields=schema,
                definition=definition,
            )
            print(f"  Created MemoryDB vector index: {self.index_name}")

    @staticmethod
    def _vector_to_bytes(vector: list[float]) -> bytes:
        """Convert a list of floats to a binary blob for Redis VSS."""
        return struct.pack(f"{len(vector)}f", *vector)

    @staticmethod
    def _bytes_to_vector(data: bytes) -> list[float]:
        """Convert a binary blob back to a list of floats."""
        n = len(data) // 4  # 4 bytes per float32
        return list(struct.unpack(f"{n}f", data))

    def store(self, context: ExecutionContext, embedding: list[float]) -> str:
        """Store an execution context with its embedding vector.

        Args:
            context: The execution context to store.
            embedding: The embedding vector for the change request.

        Returns:
            The Redis key of the stored entry.
        """
        key = f"{KEY_PREFIX}{uuid.uuid4().hex}"
        data = context.to_redis_hash()

        # Convert string values to bytes for Redis (decode_responses=False)
        mapping = {k.encode(): v.encode() if isinstance(v, str) else v for k, v in data.items()}
        mapping[b"embedding"] = self._vector_to_bytes(embedding)

        self.client.hset(key.encode(), mapping=mapping)

        # Set TTL
        ttl_seconds = self.ttl_days * 86400
        self.client.expire(key.encode(), ttl_seconds)

        print(f"  Stored execution context: {key}")
        return key

    def search(self, query_embedding: list[float], top_k: int = 3,
               threshold: float = 0.85) -> list[ExecutionContext]:
        """Search for similar past executions using vector similarity.

        Args:
            query_embedding: The embedding vector of the current change request.
            top_k: Maximum number of results to return.
            threshold: Minimum cosine similarity score (0-1). Higher = more similar.

        Returns:
            List of ExecutionContext objects sorted by similarity (highest first).
        """
        query_blob = self._vector_to_bytes(query_embedding)

        # Redis VSS KNN query
        q = (
            Query(f"*=>[KNN {top_k} @embedding $query_vec AS score]")
            .sort_by("score")
            .return_fields(
                "score", "change_request", "workspace_id", "workspace_name",
                "vcs_repo_url", "vcs_branch", "working_dir",
                "standards_json", "templates_json",
                "generated_code_json", "resource_types", "execution_mode",
                "executed_steps", "created_at",
            )
            .dialect(2)
        )

        results = self.client.ft(self.index_name).search(
            q, query_params={"query_vec": query_blob}
        )

        contexts = []
        for doc in results.docs:
            # Redis VSS cosine distance: 0 = identical, 2 = opposite
            # Convert to similarity: 1 - (distance / 2)
            distance = float(doc.score)
            similarity = 1.0 - (distance / 2.0)

            if similarity < threshold:
                continue

            # Build dict from document fields, decoding bytes
            data = {}
            for field_name in (
                "change_request", "workspace_id", "workspace_name",
                "vcs_repo_url", "vcs_branch", "working_dir",
                "standards_json", "templates_json",
                "generated_code_json", "resource_types", "execution_mode",
                "executed_steps", "created_at",
            ):
                val = getattr(doc, field_name, b"")
                if isinstance(val, bytes):
                    val = val.decode()
                data[field_name] = val

            contexts.append(ExecutionContext.from_redis_hash(data, score=similarity))

        return contexts

    def delete_expired(self):
        """Delete entries older than TTL. Called periodically for cleanup.

        Note: Redis TTL handles this automatically via EXPIRE, but this
        method can be used for manual cleanup if needed.
        """
        cutoff = datetime.now(timezone.utc).isoformat()
        # Scan for keys and check created_at — only needed if TTL is not set
        count = 0
        for key in self.client.scan_iter(match=f"{KEY_PREFIX}*".encode()):
            ttl = self.client.ttl(key)
            if ttl == -1:  # No expiry set
                self.client.expire(key, self.ttl_days * 86400)
                count += 1

        if count:
            print(f"  Set TTL on {count} entries missing expiry.", file=sys.stderr)
