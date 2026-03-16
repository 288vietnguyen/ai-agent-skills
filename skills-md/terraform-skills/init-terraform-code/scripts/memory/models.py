#!/usr/bin/env python3
"""Data models for execution context storage and retrieval."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ExecutionContext:
    """Represents a complete execution context for a change request.

    Stored in MemoryDB after each successful skill execution and
    retrieved when a similar future request is detected.
    """

    change_request: str
    workspace_id: str = ""
    workspace_name: str = ""
    vcs_repo_url: str = ""
    vcs_branch: str = ""
    working_dir: str = ""
    standards: dict[str, str] = field(default_factory=dict)
    templates: dict[str, dict[str, str]] = field(default_factory=dict)
    generated_code: dict[str, str] = field(default_factory=dict)
    resource_types: list[str] = field(default_factory=list)
    execution_mode: str = ""  # "CREATE" or "MODIFY"
    executed_steps: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    similarity_score: float = 0.0  # populated on retrieval

    def to_redis_hash(self) -> dict[str, str]:
        """Serialize to a flat dict suitable for Redis HSET."""
        return {
            "change_request": self.change_request,
            "workspace_id": self.workspace_id,
            "workspace_name": self.workspace_name,
            "vcs_repo_url": self.vcs_repo_url,
            "vcs_branch": self.vcs_branch,
            "working_dir": self.working_dir,
            "standards_json": json.dumps(self.standards),
            "templates_json": json.dumps(self.templates),
            "generated_code_json": json.dumps(self.generated_code),
            "resource_types": ",".join(self.resource_types),
            "execution_mode": self.execution_mode,
            "executed_steps": json.dumps(self.executed_steps),
            "created_at": self.created_at,
        }

    @classmethod
    def from_redis_hash(cls, data: dict, score: float = 0.0) -> "ExecutionContext":
        """Deserialize from a Redis hash dict."""
        return cls(
            change_request=data.get("change_request", ""),
            workspace_id=data.get("workspace_id", ""),
            workspace_name=data.get("workspace_name", ""),
            vcs_repo_url=data.get("vcs_repo_url", ""),
            vcs_branch=data.get("vcs_branch", ""),
            working_dir=data.get("working_dir", ""),
            standards=json.loads(data.get("standards_json", "{}")),
            templates=json.loads(data.get("templates_json", "{}")),
            generated_code=json.loads(data.get("generated_code_json", "{}")),
            resource_types=[r for r in data.get("resource_types", "").split(",") if r],
            execution_mode=data.get("execution_mode", ""),
            executed_steps=json.loads(data.get("executed_steps", "[]")),
            created_at=data.get("created_at", ""),
            similarity_score=score,
        )
