"""Local-only HTTP operator boundary; graph state remains authoritative."""
import asyncio
import json
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse, StreamingResponse

from witness_fleet.doctor import dependency_report


class IncidentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    scenario: Literal["SC-001", "SC-002", "SC-003", "SC-004", "SC-005", "SC-008"]
    seed: Annotated[int, Field(strict=True, ge=0, le=2147483647)] = 0
    event_id: str = Field(min_length=1, max_length=128)


class EventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    event_id: str = Field(min_length=1, max_length=128)


class HoldRequest(EventRequest):
    reason: str = Field(min_length=1, max_length=512)


class StepRequest(EventRequest):
    ticks: Annotated[int, Field(strict=True, ge=1, le=100000)] = 10


class ApprovalRequest(EventRequest):
    expected_policy_epoch: Annotated[int, Field(strict=True, ge=0)]
    notes: str = Field(default="", max_length=512)


def create_app(controller=None, *, local_port=8090):
    if type(local_port) is not int or not 1024 <= local_port <= 65535:
        raise ValueError('invalid local operator port')
    allowed_origins = {f'http://{host}:{port}' for host in ('127.0.0.1', 'localhost')
                       for port in (local_port, 5173)}
    app = FastAPI(title="Witness Fleet", version="0.1.0")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    @app.middleware("http")
    async def protect_browser_writes(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin not in allowed_origins:
                return JSONResponse({"detail": {"code": "NOT_AUTHORIZED"}}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": {"code": "NOT_AUTHORIZED"}}, status_code=403)
        return await call_next(request)

    @app.get("/api/health")
    def health():
        return {"process": "healthy", "dispatch_ready": False if controller is None else controller.ready(),
                "dependencies": dependency_report()}

    def ready_controller():
        if controller is None:
            raise HTTPException(503, detail={"code": "NOT_READY"})
        return controller

    def motion_controller():
        target = ready_controller()
        if any(not callable(getattr(target, name, None)) for name in ('run', 'step', 'approve_release')):
            raise HTTPException(503, detail={'code': 'RUNTIME_INTEGRATION_INCOMPLETE'})
        return target

    @app.exception_handler(KeyError)
    async def missing_record(request: Request, exc: KeyError):
        return JSONResponse({"detail": {"code": "NOT_FOUND"}}, status_code=404)

    @app.exception_handler(ValueError)
    async def rejected_operation(request: Request, exc: ValueError):
        return JSONResponse({'detail': {'code': 'STATE_CONFLICT'}}, status_code=409)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        return JSONResponse({"detail": {"code": "INVALID_INPUT"}}, status_code=422)

    @app.get("/api/state")
    def state():
        return ready_controller().state()

    @app.get("/api/events")
    async def events(request: Request, once: bool = False):
        target = ready_controller()

        async def snapshots():
            revision = None
            while not await request.is_disconnected():
                snapshot = await asyncio.to_thread(target.state)
                current = snapshot.get('revision')
                if current != revision:
                    data = json.dumps(snapshot, separators=(',', ':'), allow_nan=False)
                    yield f'id: {current}\nevent: snapshot\ndata: {data}\n\n'
                    revision = current
                else:
                    yield ': heartbeat\n\n'
                if once:
                    break
                await asyncio.sleep(.5)

        return StreamingResponse(snapshots(), media_type='text/event-stream',
                                 headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    @app.post("/api/incidents")
    def incident(body: IncidentRequest):
        return ready_controller().create_incident(body.scenario, body.seed, body.event_id)

    @app.get("/api/sources/{revision_id}")
    def source(revision_id: str):
        return ready_controller().source(revision_id)

    @app.get("/api/decisions/{decision_id}/witness")
    def witness(decision_id: str):
        return ready_controller().witness(decision_id)

    @app.get("/api/commands/{command_id}")
    def command(command_id: str):
        return ready_controller().command(command_id)

    @app.get("/api/episodes/{episode_id}")
    def episode(episode_id: str):
        return ready_controller().episode(episode_id)

    @app.post("/api/hold")
    def hold(body: HoldRequest):
        target = ready_controller()
        if not callable(getattr(target, 'hold', None)):
            raise HTTPException(503, detail={'code': 'RUNTIME_INTEGRATION_INCOMPLETE'})
        return target.hold(body.reason, body.event_id)

    @app.post("/api/step")
    def step(body: StepRequest):
        return motion_controller().step(body.ticks, body.event_id)

    @app.post("/api/run")
    def run(body: EventRequest):
        return motion_controller().run(body.event_id)

    @app.post("/api/releases/{release_id}/approve")
    def approve(release_id: str, body: ApprovalRequest):
        return motion_controller().approve_release(release_id, body.expected_policy_epoch, body.event_id)

    return app
