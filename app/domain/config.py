"""Domain models for the Raft cluster configuration.

These are pure data + validation; loading from YAML/CLI lives in the
infrastructure layer.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator


class NodeConfig(BaseModel):
    """A single cluster peer definition."""

    id: str
    host: str = "127.0.0.1"
    port: int = Field(ge=1, le=65535)

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


class RaftLimits(BaseModel):
    """Timing configuration. Values are in milliseconds unless noted."""

    election_timeout_min_ms: int = Field(default=150, ge=50)
    election_timeout_max_ms: int = Field(default=300, ge=50)
    heartbeat_interval_ms: int = Field(default=100, ge=10)
    rpc_timeout_ms: int = Field(default=100, ge=1)
    log_dir: str = "logs"


class ClusterConfig(BaseModel):
    """Static cluster configuration."""

    cluster_name: str = "raft-cluster"
    self_id: str = ""
    nodes: list[NodeConfig] = Field(min_length=1)
    limits: RaftLimits = RaftLimits()

    @field_validator("nodes")
    @classmethod
    def _unique_ids(cls, nodes: list[NodeConfig]) -> list[NodeConfig]:
        ids = [n.id for n in nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("node ids must be unique")
        return nodes

    @model_validator(mode="after")
    def _self_must_exist(self) -> "ClusterConfig":
        if not self.self_id:
            self.self_id = self.nodes[0].id
        if self.self_id not in {n.id for n in self.nodes}:
            raise ValueError(f"self_id '{self.self_id}' not present in nodes")
        return self

    @property
    def self_node(self) -> NodeConfig:
        return next(n for n in self.nodes if n.id == self.self_id)

    @property
    def peers(self) -> list[NodeConfig]:
        return [n for n in self.nodes if n.id != self.self_id]

    @property
    def quorum(self) -> int:
        """Minimum nodes to win an election / commit.

        With N nodes the majority is floor(N / 2) + 1, so it works for any N.
        """
        return len(self.nodes) // 2 + 1


def default_config_path() -> Path:
    return Path("configs/cluster.yaml")