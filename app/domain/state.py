"""Persistent state variables for a single Raft node."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .types import Role


class NodeRole(str, Enum):
    """The three Raft roles a node can take."""

    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"

    @property
    def value_literal(self) -> Role:
        return self.value  # type: ignore[return-value]


@dataclass
class PersistentState:
    """Variables that in a real implementation would be persisted to disk.

    A later stage will add durability for these fields and the log.
    """

    current_term: int = 0
    voted_for: str | None = None
    log: list = field(default_factory=list)

    def last_log_index(self) -> int:
        if not self.log:
            return 0
        return len(self.log)

    def last_log_term(self) -> int:
        if not self.log:
            return 0
        return self.log[-1].get("term", 0)


@dataclass
class VolatileState:
    """Volatile state on all servers."""

    leader_id: str | None = None
    commit_index: int = 0


@dataclass
class ElectionStats:
    """Bookkeeping attached to an election attempt."""

    votes_granted: set[str] = field(default_factory=set)
    term: int = 0

    def has_quorum(self, quorum: int) -> bool:
        return len(self.votes_granted) >= quorum


@dataclass
class NodeState:
    """The mutable state of a Raft node."""

    role: NodeRole = NodeRole.FOLLOWER
    persistent: PersistentState = field(default_factory=PersistentState)
    volatile: VolatileState = field(default_factory=VolatileState)
    election: ElectionStats = field(default_factory=ElectionStats)

    @property
    def current_term(self) -> int:
        return self.persistent.current_term

    @property
    def role_value(self) -> Role:
        return self.role.value  # type: ignore[return-value]