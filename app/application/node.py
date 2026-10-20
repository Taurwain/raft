"""The asynchronous Raft node: state machine, election and heartbeat tasks."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from app.domain.config import ClusterConfig, NodeConfig
from app.domain.election import (
    election_timeout_ms,
    handle_append_entries,
    handle_request_vote,
    has_quorum,
    start_election,
)
from app.domain.messages import (
    AppendEntriesRequest,
    RequestVoteRequest,
    StatusResponse,
)
from app.domain.state import NodeRole, NodeState

from .ports import Logger, Transport


class Node:
    """A single Raft node running in an asyncio context."""

    def __init__(self, config: ClusterConfig, transport: Transport, logger: Logger) -> None:
        self.config = config
        self.self_id = config.self_id
        self.state = NodeState()
        self._transport = transport
        self._logger = logger
        self._election_reset = asyncio.Event()
        self._election_win = asyncio.Event()
        self._shutting_down = False

        self._election_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the election and heartbeat tasks."""
        self._election_task = asyncio.create_task(self._election_loop(), name="election")
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(), name="heartbeat")
        self._logger.info("node started", node_id=self.self_id, role="follower", term=0)

    async def stop(self) -> None:
        self._shutting_down = True
        for task in (self._election_task, self._heartbeat_task):
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    def handle_request_vote(self, req: RequestVoteRequest):
        """Handle an incoming RequestVote, resetting the timer if granted."""
        resp = handle_request_vote(self.state, req)
        if resp.vote_granted:
            self._reset_election_timer()
        self._log_role_change(
            "request_vote",
            term=resp.term,
            granted=resp.vote_granted,
            candidate=req.candidate_id,
        )
        return resp

    async def handle_append_entries(self, req: AppendEntriesRequest):
        """Handle an incoming AppendEntries heartbeat, resetting the timer."""
        resp = handle_append_entries(self.state, req)
        if resp.success:
            self._reset_election_timer()
        self._log_role_change(
            "append_entries",
            term=resp.term,
            granted=resp.success,
            leader=req.leader_id,
        )
        return resp

    async def _election_loop(self) -> None:
        """Wait for a randomized election timeout; run an election when it fires."""
        while not self._shutting_down:
            timeout = election_timeout_ms(self.config) / 1000.0
            try:
                await asyncio.wait_for(self._election_reset.wait(), timeout=timeout)
                self._election_reset.clear()
                continue
            except asyncio.TimeoutError:
                pass

            if self.state.role is NodeRole.LEADER:
                continue
            await self._run_election()

    async def _run_election(self) -> None:
        """Become candidate, gather votes from peers, become leader on quorum."""
        start_election(self.state, self.self_id)
        term = self.state.current_term
        self._logger.info("starting election", role="candidate", term=term, peer_count=len(self.config.peers))
        self._election_win = asyncio.Event()

        tasks = [
            asyncio.create_task(self._request_vote(peer, term), name=f"vote-{peer.id}")
            for peer in self.config.peers
        ]
        timeout = election_timeout_ms(self.config) / 1000.0
        try:
            await asyncio.wait_for(self._election_win.wait(), timeout=timeout)
            if has_quorum(self.state, self.config):
                self._become_leader()
        except asyncio.TimeoutError:
            self._logger.info("election timeout, no quorum", role="candidate", term=term)
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _request_vote(self, peer: NodeConfig, term: int) -> None:
        """Ask a single peer for its vote in the current term."""
        req = RequestVoteRequest(
            term=term,
            candidate_id=self.self_id,
            last_log_index=self.state.persistent.last_log_index(),
            last_log_term=self.state.persistent.last_log_term(),
        )
        resp = await self._transport.request_vote(peer, req)
        if resp is None:
            self._logger.warning("vote request failed", peer=peer.id, term=term)
            return
        if resp.term > self.state.current_term:
            self._step_down(resp.term)
            self._election_win.set()
            return
        if resp.vote_granted and self.state.role is NodeRole.CANDIDATE:
            self.state.election.votes_granted.add(peer.id)
            self._logger.info("vote granted", peer=peer.id, term=term, votes=len(self.state.election.votes_granted))
            if has_quorum(self.state, self.config):
                self._election_win.set()

    async def _heartbeat_loop(self) -> None:
        """If leader, periodically send empty AppendEntries to keep authority."""
        interval = self.config.limits.heartbeat_interval_ms / 1000.0
        while not self._shutting_down:
            if self.state.role is NodeRole.LEADER:
                self._send_heartbeat()
            await asyncio.sleep(interval)

    def _send_heartbeat(self) -> None:
        term = self.state.current_term
        for peer in self.config.peers:
            asyncio.create_task(self._heartbeat_to(peer, term), name=f"hb-{peer.id}")

    async def _heartbeat_to(self, peer: NodeConfig, term: int) -> None:
        req = AppendEntriesRequest(
            term=term,
            leader_id=self.self_id,
            prev_log_index=self.state.persistent.last_log_index(),
            prev_log_term=self.state.persistent.last_log_term(),
            entries=[],
            leader_commit=self.state.volatile.commit_index,
        )
        resp = await self._transport.append_entries(peer, req)
        if resp is None:
            return
        if resp.term > self.state.current_term:
            self._step_down(resp.term)

    def _become_leader(self) -> None:
        self.state.role = NodeRole.LEADER
        self.state.volatile.leader_id = self.self_id
        self._logger.info("became leader", role="leader", term=self.state.current_term)
        self._send_heartbeat()

    def _step_down(self, term: int | None = None) -> None:
        """Return to follower, optionally adopting a newer term."""
        if term is not None and term > self.state.current_term:
            self.state.persistent.current_term = term
        was = self.state.role.value
        self.state.role = NodeRole.FOLLOWER
        if self.state.role.value != was:
            self._log_role_change("step_down", term=self.state.current_term, granted=True)

    def _reset_election_timer(self) -> None:
        self._election_reset.set()

    def _log_role_change(self, kind: str, *, term: int, granted: bool, **extra) -> None:
        current = self.state.role.value
        self._logger.info(
            f"{kind} → {current}",
            role=current,
            term=term,
            granted=granted,
            **extra,
        )

    def status(self) -> StatusResponse:
        s = self.state
        return StatusResponse(
            node_id=self.self_id,
            role=s.role.value,
            current_term=s.current_term,
            leader_id=s.volatile.leader_id,
            voted_for=s.persistent.voted_for,
            votes_granted=sorted(s.election.votes_granted),
            vote_term=s.election.term,
            last_log_index=s.persistent.last_log_index(),
            last_log_term=s.persistent.last_log_term(),
            commit_index=s.volatile.commit_index,
        )

    def leader(self) -> dict:
        return {"leader_id": self.state.volatile.leader_id}

    def vote(self) -> dict:
        return {
            "vote_term": self.state.persistent.current_term,
            "voted_for": self.state.persistent.voted_for,
        }

    def force_role(self, role: str) -> StatusResponse:
        """Test helper: force a role change (mainly to degrade a leader)."""
        r = role.lower()
        if r == "follower":
            self.state.role = NodeRole.FOLLOWER
            self._logger.info("forced role", role="follower", term=self.state.current_term)
        elif r == "candidate":
            self.state.role = NodeRole.CANDIDATE
            self._logger.info("forced role", role="candidate", term=self.state.current_term)
        elif r == "leader":
            self.state.role = NodeRole.LEADER
            self.state.volatile.leader_id = self.self_id
            self._send_heartbeat()
            self._logger.info("forced role", role="leader", term=self.state.current_term)
        else:
            raise ValueError(f"unknown role: {role}")
        return self.status()