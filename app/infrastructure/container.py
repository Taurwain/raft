"""Dishka composition root wiring for a single Raft node."""

from __future__ import annotations

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide

from app.application import Logger, Node, Transport
from app.domain.config import ClusterConfig

from .logger import get_logger
from .network import RpcClient


class RaftProvider(Provider):
    """Binds application ports to infrastructure implementations."""

    def __init__(self, config: ClusterConfig) -> None:
        super().__init__()
        self._config = config

    @provide(scope=Scope.APP)
    def config(self) -> ClusterConfig:
        return self._config

    @provide(scope=Scope.APP)
    def transport(self, config: ClusterConfig) -> Transport:
        return RpcClient(config.limits.rpc_timeout_ms)

    @provide(scope=Scope.APP)
    def logger(self, config: ClusterConfig) -> Logger:
        return get_logger().bind(node_id=config.self_id)

    @provide(scope=Scope.APP)
    def node(self, config: ClusterConfig, transport: Transport, logger: Logger) -> Node:
        return Node(config, transport, logger)


def build_container(config: ClusterConfig) -> AsyncContainer:
    return make_async_container(RaftProvider(config))