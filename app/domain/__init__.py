"""Raft domain layer: the pure consensus logic and state models."""

from .election import (
    election_timeout_ms,
    handle_append_entries,
    handle_request_vote,
    has_quorum,
    start_election,
)
from .state import NodeRole, NodeState

__all__ = (
    "NodeRole",
    "NodeState",
    "election_timeout_ms",
    "handle_append_entries",
    "handle_request_vote",
    "has_quorum",
    "start_election",
)