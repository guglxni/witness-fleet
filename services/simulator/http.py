"""Loopback simulator API. No caller-supplied source authority or raw motion endpoints."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import unquote_to_bytes

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from services.simulator.service import SimulatorService
from witness_fleet.domain import DispatchEvent


class Episode(BaseModel):
    model_config = ConfigDict(extra='forbid')
    episode_id: str = Field(min_length=1)
    scenario: Literal['SC-001','SC-002','SC-003','SC-004','SC-005']
    seed: Annotated[int, Field(strict=True, ge=0)]


class Advance(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ticks: Annotated[int, Field(strict=True, ge=1, le=100000)]


def create_app(*, root=None):
    service = SimulatorService(Path(root) if root is not None else Path('artifacts/runtime/simulator'))

    @asynccontextmanager
    async def lifespan(app):
        yield
        service.close()

    app = FastAPI(title='Witness Fleet Simulator', lifespan=lifespan)
    app.state.service = service
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost','127.0.0.1','testserver'])

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError):
        return JSONResponse(status_code=422, content={'detail': 'invalid simulator request'})

    def invoke(method, *args):
        try:
            return getattr(service, method)(*args)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None

    @app.get('/health')
    def health():
        return {'status':'ok', 'scope':'local simulator', 'motion_authorized': False}

    @app.get('/state')
    def state():
        return service.status()

    @app.get('/observations')
    def observations():
        return invoke('observations')

    @app.post('/episodes', status_code=201)
    def episode(data: Episode):
        return invoke('create_episode', data.episode_id, data.scenario, data.seed)

    @app.post('/events')
    def event(data: DispatchEvent):
        return invoke('receive', data)

    @app.post('/advance')
    def advance(data: Advance):
        return invoke('advance', data.ticks)

    @app.get('/commands/{command_id}')
    def command(command_id: str):
        return service.command(command_id)

    @app.get('/events/{event_id:path}')
    def query_event(event_id: str, request: Request):
        # ASGI raw_path is the original encoded target; path may be decoded
        # more than once by an adapter. Decode exactly once to preserve IDs.
        raw_path = request.scope.get('raw_path')
        prefix = b'/events/'
        if not isinstance(raw_path, bytes) or not raw_path.startswith(prefix):
            raise HTTPException(status_code=422, detail='invalid simulator request')
        try:
            exact_id = unquote_to_bytes(raw_path[len(prefix):]).decode('utf-8', errors='strict')
        except UnicodeError:
            raise HTTPException(status_code=422, detail='invalid simulator request') from None
        return invoke('event', exact_id)

    return app
