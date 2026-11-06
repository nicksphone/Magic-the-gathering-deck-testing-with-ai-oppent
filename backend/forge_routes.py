"""Opt-in process sessions for the Forge Team/Card-Forge engine.

Native choices never enter the Python rules/action or snapshot APIs.
"""
from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import Field, StrictInt, model_validator

from api_contracts import DeckEntry, InputModel
from native_forge import ForgeError


_OPAQUE = r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$"
NativeToken = Annotated[str, Field(pattern=_OPAQUE)]


class ForgeStartRequest(InputModel):
    deck_a: list[DeckEntry] = Field(min_length=1, max_length=60)
    deck_b: list[DeckEntry] = Field(min_length=1, max_length=60)
    name_a: str = Field(min_length=1, max_length=200)
    name_b: str = Field(min_length=1, max_length=200)
    human_seat: Annotated[StrictInt, Field(ge=0, le=1)] = 0
    seed: Annotated[StrictInt, Field(ge=0, le=2**63 - 1)] | None = None

    @model_validator(mode="after")
    def sixty_card_mains(self):
        if any(sum(row.quantity for row in board) != 60 for board in (self.deck_a, self.deck_b)):
            raise ValueError("Forge preview requires exactly 60 cards in each mainboard")
        return self


class ForgeAnswerRequest(InputModel):
    request_id: NativeToken
    tokens: list[NativeToken] = Field(max_length=256)
    sequence: Annotated[StrictInt, Field(ge=0, le=2**63 - 1)]
    action_id: str = Field(min_length=1, max_length=100)


class _PrivateRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def private_response(request: Request):
            try:
                response = await original(request)
            except RequestValidationError as error:
                # Do not echo rejected input values, including tokens, in errors.
                details = [{key: row[key] for key in ("loc", "msg", "type")} for row in error.errors()]
                return JSONResponse(status_code=422, content={"detail": details}, headers={"Cache-Control": "no-store"})
            except HTTPException as error:
                error.headers = {**(error.headers or {}), "Cache-Control": "no-store"}
                raise
            response.headers["Cache-Control"] = "no-store"
            return response

        return private_response


def _capability(authorization: Annotated[str | None, Header()] = None) -> str:
    if authorization is None or re.fullmatch(r"Bearer [0-9a-f]{64}", authorization) is None:
        raise HTTPException(401, detail="Native session capability required", headers={"WWW-Authenticate": "Bearer"})
    return authorization[7:]


def create_forge_router(get_manager) -> APIRouter:
    router = APIRouter(prefix="/forge", route_class=_PrivateRoute)

    def call(operation, *args):
        try:
            return operation(*args)
        except ForgeError as error:
            raise HTTPException(error.status_code, detail={"code": error.code, "message": error.message}) from None

    @router.get("/status")
    def status():
        return call(lambda: {"available": get_manager().available})

    @router.post("/sessions")
    def start(payload: ForgeStartRequest, capability: str = Depends(_capability),
              idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None):
        if idempotency_key is None or not 1 <= len(idempotency_key) <= 100 or any(ord(c) < 32 for c in idempotency_key):
            raise HTTPException(422, detail={"code": "invalid_start_key", "message": "Supply a bounded Idempotency-Key"})
        return call(lambda: get_manager().create(payload.model_dump(exclude_none=True), capability, idempotency_key))

    @router.get("/sessions/{session_id}")
    def read(session_id: str, capability: str = Depends(_capability)):
        return call(lambda: get_manager().get(session_id, capability))

    @router.post("/sessions/{session_id}/answer")
    def answer(session_id: str, payload: ForgeAnswerRequest, capability: str = Depends(_capability)):
        return call(lambda: get_manager().answer(session_id, capability, payload.model_dump()))

    @router.delete("/sessions/{session_id}")
    def close(session_id: str, capability: str = Depends(_capability)):
        return call(lambda: get_manager().close(session_id, capability))

    return router
