"""FastAPI application: internal Raft RPC endpoints + REST status API (infrastructure)."""

from __future__ import annotations

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from app.application.node import Node
from app.domain.messages import (
    AppendEntriesRequest,
    AppendEntriesResponse,
    RequestVoteRequest,
    RequestVoteResponse,
    StatusResponse,
)


class RoleChangeRequest(BaseModel):
    role: str = "follower"


def create_app() -> FastAPI:
    app = FastAPI(title="Raft node", version="0.1.0")
    router = APIRouter(route_class=DishkaRoute)

    @router.post("/raft/request_vote", response_model=RequestVoteResponse)
    async def request_vote(req: RequestVoteRequest, node: FromDishka[Node]) -> RequestVoteResponse:
        return node.handle_request_vote(req)

    @router.post("/raft/append_entries", response_model=AppendEntriesResponse)
    async def append_entries(req: AppendEntriesRequest, node: FromDishka[Node]) -> AppendEntriesResponse:
        return await node.handle_append_entries(req)

    @router.get("/status", response_model=StatusResponse)
    async def status(node: FromDishka[Node]) -> StatusResponse:
        return node.status()

    @router.get("/leader")
    async def leader(node: FromDishka[Node]) -> dict:
        return node.leader()

    @router.get("/vote")
    async def vote(node: FromDishka[Node]) -> dict:
        return node.vote()

    @router.post("/role", response_model=StatusResponse)
    async def set_role(body: RoleChangeRequest, node: FromDishka[Node]) -> StatusResponse:
        return node.force_role(body.role)

    app.include_router(router)
    return app