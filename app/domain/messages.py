"""Raft RPC and status message models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RequestVoteRequest(BaseModel):
    term: int
    candidate_id: str
    last_log_index: int = 0
    last_log_term: int = 0


class RequestVoteResponse(BaseModel):
    term: int
    vote_granted: bool


class AppendEntriesRequest(BaseModel):
    term: int
    leader_id: str
    prev_log_index: int = 0
    prev_log_term: int = 0
    entries: list = Field(default_factory=list)
    leader_commit: int = 0


class AppendEntriesResponse(BaseModel):
    term: int
    success: bool


class StatusResponse(BaseModel):
    node_id: str
    role: str
    current_term: int
    leader_id: str | None
    voted_for: str | None
    votes_granted: list[str]
    vote_term: int
    last_log_index: int
    last_log_term: int
    commit_index: int