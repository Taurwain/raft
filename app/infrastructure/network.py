"""HTTP RPC client (infrastructure implementation of the Transport port)."""

from __future__ import annotations

import httpx

from app.domain.config import NodeConfig
from app.domain.messages import (
    AppendEntriesRequest,
    AppendEntriesResponse,
    RequestVoteRequest,
    RequestVoteResponse,
)


class RpcClient:
    """Thin HTTP client that maps Raft RPC message types to peer endpoints."""

    def __init__(self, timeout_ms: int) -> None:
        self._timeout = timeout_ms / 1000.0

    def _url(self, target: NodeConfig, path: str) -> str:
        return f"http://{target.address}{path}"

    async def request_vote(
        self, target: NodeConfig, body: RequestVoteRequest
    ) -> RequestVoteResponse | None:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    self._url(target, "/raft/request_vote"),
                    json=body.model_dump(),
                )
                resp.raise_for_status()
                return RequestVoteResponse(**resp.json())
        except (httpx.HTTPError, ValueError):
            return None

    async def append_entries(
        self, target: NodeConfig, body: AppendEntriesRequest
    ) -> AppendEntriesResponse | None:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    self._url(target, "/raft/append_entries"),
                    json=body.model_dump(),
                )
                resp.raise_for_status()
                return AppendEntriesResponse(**resp.json())
        except (httpx.HTTPError, ValueError):
            return None