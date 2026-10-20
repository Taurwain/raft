"""Pure election and RPC-handling logic for a Raft node.

The asynchronous orchestration lives in the application layer; this module
contains the decision rules from the Raft paper so they can be unit-tested in
isolation.
"""

from __future__ import annotations

import random

from .config import ClusterConfig
from .messages import (
    AppendEntriesRequest,
    AppendEntriesResponse,
    RequestVoteRequest,
    RequestVoteResponse,
)
from .state import ElectionStats, NodeRole, NodeState


def election_timeout_ms(config: ClusterConfig) -> int:
    """Return a randomized election timeout within the configured range."""
    limits = config.limits
    return random.randint(
        limits.election_timeout_min_ms,
        limits.election_timeout_max_ms,
    )


def start_election(state: NodeState, self_id: str) -> None:
    """Transition to candidate and prepare a fresh vote tally."""
    state.persistent.current_term += 1
    state.persistent.voted_for = self_id
    state.role = NodeRole.CANDIDATE
    state.volatile.leader_id = None
    state.election = ElectionStats(term=state.persistent.current_term)
    state.election.votes_granted.add(self_id)


def has_quorum(state: NodeState, config: ClusterConfig) -> bool:
    """True if the current election tally reaches a majority."""
    return state.election.has_quorum(config.quorum)


def is_up_to_date(last_log_term: int, last_log_index: int, state: NodeState) -> bool:
    """Raft up-to-date rule: receiver's log is at least as current as the candidate."""
    own_term = state.persistent.last_log_term()
    own_index = state.persistent.last_log_index()
    if last_log_term != own_term:
        return last_log_term > own_term
    return last_log_index >= own_index


def handle_request_vote(
    state: NodeState,
    req: RequestVoteRequest,
) -> RequestVoteResponse:
    """Grant a vote per the paper, or reject it."""
    if req.term < state.persistent.current_term:
        return RequestVoteResponse(term=state.persistent.current_term, vote_granted=False)
    if req.term > state.persistent.current_term:
        _adopt_new_term(state, req.term)

    can_grant = (
        state.persistent.voted_for is None
        or state.persistent.voted_for == req.candidate_id
    )
    if can_grant and is_up_to_date(req.last_log_term, req.last_log_index, state):
        state.persistent.voted_for = req.candidate_id
        return RequestVoteResponse(term=state.persistent.current_term, vote_granted=True)
    return RequestVoteResponse(term=state.persistent.current_term, vote_granted=False)


def handle_append_entries(
    state: NodeState,
    req: AppendEntriesRequest,
) -> AppendEntriesResponse:
    """Reject stale leaders / terms, or accept the heartbeat from a current leader."""
    if req.term < state.persistent.current_term:
        return AppendEntriesResponse(term=state.persistent.current_term, success=False)

    if req.term > state.persistent.current_term:
        _adopt_new_term(state, req.term)
    state.role = NodeRole.FOLLOWER
    state.volatile.leader_id = req.leader_id
    if req.leader_commit > state.volatile.commit_index:
        state.volatile.commit_index = req.leader_commit
    return AppendEntriesResponse(term=state.persistent.current_term, success=True)


def _adopt_new_term(state: NodeState, new_term: int) -> None:
    """Enter a newer term as a follower, resetting the per-term vote.

    Per Raft, ``votedFor`` belongs to a term: advancing to a higher term must
    clear it so future votes for the new term can be granted. Without this, a
    node that once voted (or self-voted as a candidate) would leave a stale,
    non-null ``voted_for`` and deny every candidate indefinitely, preventing a
    leader from ever being elected after a split vote.
    """
    state.persistent.current_term = new_term
    state.persistent.voted_for = None
    state.role = NodeRole.FOLLOWER
    state.election = ElectionStats(term=new_term)