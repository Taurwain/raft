"""Ports (interfaces) that the application depends on.

The application layer defines these contracts; the infrastructure layer
provides concrete implementations (e.g. HTTP transport, structured logger).
"""

from __future__ import annotations

from typing import Protocol

from app.domain.config import NodeConfig
from app.domain.messages import (
    AppendEntriesRequest,
    AppendEntriesResponse,
    RequestVoteRequest,
    RequestVoteResponse,
)


class Transport(Protocol):
    """Outbound RPC channel to a single peer node."""

    async def request_vote(
        self,
        target: NodeConfig,
        body: RequestVoteRequest,
    ) -> RequestVoteResponse | None: ...

    async def append_entries(
        self,
        target: NodeConfig,
        body: AppendEntriesRequest,
    ) -> AppendEntriesResponse | None: ...


class Logger(Protocol):
    """Structured logger bound to a node context."""

    def info(self, event: str, **kwargs: object) -> None: ...

    def warning(self, event: str, **kwargs: object) -> None: ...