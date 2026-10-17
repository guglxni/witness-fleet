"""Bounded public simulation gateway, deliberately separate from local APIs.

The gateway owns only a small set of demo routes. The local mission app is used
as a provisioning factory so the existing controller/native chain stays intact;
none of its routes are mounted or proxied here.
"""
from __future__ import annotations

import hashlib
import hmac
import math
import secrets
import shutil
import sqlite3
import threading
import time
import uuid
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr
from starlette.middleware.trustedhost import TrustedHostMiddleware

COOKIE_CAPABILITY = "__Host-wf-session"
COOKIE_BOOTSTRAP_CSRF = "__Host-wf-csrf"
COOKIE_SESSION_CSRF = "__Host-wf-session-csrf"
MAX_BODY_BYTES = 8192
MIN_FREE_BYTES = 32 * 1024 * 1024


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CreateSession(StrictDTO):
    request_id: StrictStr = Field(min_length=1, max_length=128)


class RunRequest(StrictDTO):
    request_id: StrictStr = Field(min_length=1, max_length=128)


class StepRequest(StrictDTO):
    request_id: StrictStr = Field(min_length=1, max_length=128)
    ticks: StrictInt = Field(ge=1, le=100000)


class ReleaseRequest(StrictDTO):
    request_id: StrictStr = Field(min_length=1, max_length=128)
    expected_policy_epoch: StrictInt = Field(ge=0)
    confirmed: bool

    @classmethod
    def model_validate(cls, obj: Any, *args: Any, **kwargs: Any):
        # Pydantic's strict mode accepts 1 as bool on some versions; the
        # confirmation contract intentionally accepts only the literal True.
        if isinstance(obj, dict) and type(obj.get("confirmed")) is not bool:
            raise ValueError("confirmed must be a JSON boolean")
        return super().model_validate(obj, *args, **kwargs)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now(clock) -> float:
    return float(clock()) if clock is not None else time.time()


def _secure_cookie(response: Response, key: str, value: str, max_age: int) -> None:
    response.set_cookie(key, value, max_age=max_age, path="/", secure=True,
                        httponly=True, samesite="strict")


class _BodyLimitMiddleware:
    """Bound request bytes before JSON parsing, including missing-length bodies."""
    def __init__(self, app, limit=MAX_BODY_BYTES):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        length = headers.get(b"content-length")
        if length:
            try:
                if int(length) > self.limit:
                    await JSONResponse({"error": "request_too_large"}, status_code=413)(scope, receive, send)
                    return
            except ValueError:
                await JSONResponse({"error": "invalid_content_length"}, status_code=400)(scope, receive, send)
                return
        chunks = []
        size = 0
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.limit:
                await JSONResponse({"error": "request_too_large"}, status_code=413)(scope, receive, send)
                return
            chunks.append(chunk)
            more = message.get("more_body", False)

        sent = False
        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}
        await self.app(scope, replay, send)


class _HostedStore:
    def __init__(self, root: Path, max_sessions: int, max_active: int, clock):
        self.root, self.max_sessions, self.max_active, self.clock = root, max_sessions, max_active, clock
        root.mkdir(parents=True, exist_ok=True)
        self.db_path = root / "hosted-sessions.sqlite3"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("""CREATE TABLE IF NOT EXISTS sessions (
                sid TEXT PRIMARY KEY, capability_hash TEXT NOT NULL UNIQUE,
                csrf_hash TEXT NOT NULL, status TEXT NOT NULL,
                created_at REAL NOT NULL, expires_at REAL NOT NULL,
                create_key TEXT NOT NULL UNIQUE, failure_code TEXT)""")
            # A new process deliberately never reattaches to an old controller.
            db.execute("UPDATE sessions SET status='restarted' WHERE status IN ('reserved','active')")

    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=0.15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=150")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def lookup(self, capability: str):
        with closing(self.connect()) as db:
            return db.execute("SELECT * FROM sessions WHERE capability_hash=?", (_digest(capability),)).fetchone()

    def reserve(self, sid: str, capability: str, csrf: str, request_key: str, now: float, ttl: int):
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            active = db.execute("SELECT COUNT(*) FROM sessions WHERE status IN ('reserved','active') AND expires_at>?",
                                (now,)).fetchone()[0]
            if count >= self.max_sessions or active >= self.max_active:
                db.rollback()
                return False
            db.execute("INSERT INTO sessions(sid,capability_hash,csrf_hash,status,created_at,expires_at,create_key) "
                       "VALUES(?,?,?,?,?,?,?)", (sid, _digest(capability), _digest(csrf), "reserved", now,
                                                  now + ttl, request_key))
            db.commit()
            return True

    def status(self, sid: str, status: str, failure: str | None = None):
        with closing(self.connect()) as db:
            db.execute("UPDATE sessions SET status=?,failure_code=? WHERE sid=?", (status, failure, sid))

    def by_create_key(self, request_key: str):
        with closing(self.connect()) as db:
            return db.execute("SELECT * FROM sessions WHERE create_key=?", (request_key,)).fetchone()


_DEMO_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#101a1d"><title>Witness Fleet · Simulation Demo</title>
<style>
:root{color-scheme:dark;--bg:#101a1d;--panel:#172629;--line:#294044;--muted:#9ab0ae;--ink:#e8f0ed;--mint:#75e0bb;--amber:#f4bc63;--red:#f27e75;font:15px/1.5 ui-sans-serif,system-ui,-apple-system,sans-serif}*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 75% -15%,#244448 0,transparent 48%),var(--bg);color:var(--ink)}main{max-width:1040px;margin:auto;padding:30px 22px 56px}.top{display:flex;justify-content:space-between;align-items:center;gap:16px}.brand{font-size:12px;letter-spacing:.18em;color:var(--mint);font-weight:750}.pill{border:1px solid #41645f;color:var(--mint);border-radius:99px;padding:5px 10px;font-size:11px;letter-spacing:.1em;text-transform:uppercase}h1{font-size:clamp(32px,6vw,56px);line-height:1.04;letter-spacing:-.045em;margin:34px 0 12px;max-width:720px}.lede{color:var(--muted);max-width:660px;margin:0 0 28px}.grid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(280px,.8fr);gap:16px}.card{background:linear-gradient(145deg,#1a2b2d,#142123);border:1px solid var(--line);border-radius:15px;padding:20px;box-shadow:0 16px 55px #07101255}.card h2{font-size:14px;text-transform:uppercase;letter-spacing:.12em;color:#b1c8c2;margin:0 0 16px}.scene{width:100%;height:265px;background:#0e191a;border:1px solid #23383a;border-radius:10px}.legend{display:flex;gap:18px;color:var(--muted);font-size:12px;margin-top:12px}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--mint);margin-right:6px}.dot.orange{background:var(--amber)}.phase{font-size:22px;font-weight:650;letter-spacing:-.02em}.sub{color:var(--muted);font-size:12px}.tasks{list-style:none;padding:0;margin:0;display:grid;gap:8px}.tasks li{display:grid;grid-template-columns:24px 1fr auto;align-items:center;gap:9px;padding:9px 10px;border:1px solid #273b3e;border-radius:9px;font-size:13px}.num{color:#8ba09c;font-variant-numeric:tabular-nums}.state{font-size:10px;letter-spacing:.08em;color:var(--muted)}.state.done{color:var(--mint)}.state.active{color:var(--amber)}.controls{display:flex;gap:9px;flex-wrap:wrap;margin-top:18px}button{background:var(--mint);border:0;border-radius:8px;color:#10201d;font-weight:750;padding:10px 15px;cursor:pointer}button.secondary{background:#263c3f;color:var(--ink);border:1px solid #3a5558}button:disabled{opacity:.48;cursor:not-allowed}.notice{min-height:23px;color:var(--muted);font-size:12px;margin-top:12px}.metrics{display:flex;gap:10px;margin:16px 0}.metric{flex:1;border:1px solid #294044;padding:10px;border-radius:9px}.metric b{display:block;font-size:21px;color:var(--mint)}.metric span{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.footer{margin-top:18px;padding:16px 2px;color:var(--muted);font-size:12px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}.footer a{color:var(--mint);text-decoration:none}label{font-size:12px;color:var(--muted)}.confirm{display:flex;align-items:center;gap:8px;margin-top:10px}.confirm input{accent-color:var(--mint)}@media(max-width:740px){main{padding:20px 14px}.grid{grid-template-columns:1fr}.scene{height:230px}.top{align-items:flex-start}}
</style></head><body><main><div class="top"><div class="brand">WITNESS FLEET / FIELD LAB</div><div class="pill">Synthetic simulation · no hardware</div></div>
<h1>See evidence-first autonomy in motion.</h1><p class="lede">A bounded, isolated MuJoCo fleet simulation. Actions advance only when you request them; release is an explicit demo confirmation. No connection to production robots.</p>
<div class="grid"><section class="card"><h2>Simulation floor · x / y pose</h2><svg class="scene" viewBox="0 0 700 265" role="img" aria-label="Simplified fleet simulation map"><defs><pattern id="grid" width="35" height="35" patternUnits="userSpaceOnUse"><path d="M35 0H0V35" fill="none" stroke="#213436" stroke-width="1"/></pattern></defs><rect width="700" height="265" fill="url(#grid)"/><path d="M54 205H630M54 66H630" stroke="#385356" stroke-width="2" stroke-dasharray="5 7"/><rect x="314" y="91" width="80" height="88" rx="9" fill="#223739" stroke="#45605f"/><text x="354" y="138" text-anchor="middle" fill="#91aaa4" font-size="10">SAFE ZONE</text><circle id="scout" cx="90" cy="205" r="11" fill="#75e0bb"/><path id="scout-dir" d="M90 191l6 9h-12z" fill="#e8f0ed"/><circle id="recovery" cx="120" cy="205" r="11" fill="#f4bc63"/><text x="58" y="239" fill="#98afaa" font-size="10">SERVICE CORRIDOR</text><text x="540" y="53" fill="#98afaa" font-size="10">DELIVERY BAY</text><rect x="604" y="60" width="35" height="25" rx="4" fill="#35504c"/></svg><div class="legend"><span><i class="dot"></i>Scout</span><span><i class="dot orange"></i>Recovery</span><span id="tick-label">World tick · 0</span></div><div class="controls"><button id="start">Start isolated session</button><button id="run" class="secondary" disabled>Run authorized tasks</button><button id="step" class="secondary" disabled>Next task</button></div><div class="notice" id="notice" aria-live="polite">Start a fresh session to begin. No simulation runs automatically.</div></section>
<section class="card"><h2>Mission progress</h2><div id="phase" class="phase">Not started</div><div id="subtitle" class="sub">Up to 7 graph-authorized tasks</div><div class="metrics"><div class="metric"><b id="recovery-count">0</b><span>Recovery verified</span></div><div class="metric"><b id="delivery-count">0</b><span>Delivery complete</span></div></div><ol class="tasks" id="tasks"><li><span class="num">—</span><span>Awaiting isolated session</span><span class="state">READY</span></li></ol><div id="release-box" hidden><div class="confirm"><input type="checkbox" id="release-check"><label for="release-check">Confirm synthetic release to continue</label></div><button id="release" style="margin-top:10px" disabled>Confirm demo release</button></div></section></div>
<div class="footer"><span>Static fallback: <a href="https://witness-fleet.vercel.app" rel="noopener noreferrer">recorded, sanitized film / replay</a></span><span>Simulation-only · no owner authority · no hardware dispatch</span></div></main>
<script>
let csrf=null,started=false,lastState=null;const $=id=>document.getElementById(id);const labels={inspect:'Inspect corridor',recover:'Recover safely',navigate:'Navigate corridor',deliver:'Deliver payload'};function requestId(prefix){return prefix+'-'+crypto.randomUUID()}
async function call(path,body){const headers={'Content-Type':'application/json'};if(body){headers.Origin=location.origin;headers['X-CSRF-Token']=csrf}const r=await fetch('/demo/v1/'+path,{method:body?'POST':'GET',headers,body:body?JSON.stringify(body):undefined,credentials:'same-origin',cache:'no-store'});const data=await r.json();if(!r.ok)throw Error(data.error||'request_failed');if(data.csrf_token)csrf=data.csrf_token;return data}
function draw(s){lastState=s;$('phase').textContent=(s.mission_phase||'ready').replaceAll('_',' ');$('subtitle').textContent='Revision tick · '+s.revision_tick;$('tick-label').textContent='World tick · '+(s.revision_tick||0);$('recovery-count').textContent=(s.metrics||{}).recovery_verified||0;$('delivery-count').textContent=(s.metrics||{}).delivery_completed||0;const list=$('tasks');list.replaceChildren();(s.tasks||[]).forEach((t,i)=>{const li=document.createElement('li'),n=document.createElement('span'),name=document.createElement('span'),st=document.createElement('span');n.className='num';n.textContent=String(i+1).padStart(2,'0');name.textContent=labels[t.kind]||'Fleet task';st.className='state '+(t.state==='VERIFIED'?'done':t.state==='READY'?'active':'');st.textContent=t.state;li.append(n,name,st);list.append(li)});const bots={scout:$('scout'),recovery:$('recovery')};(s.robots||[]).forEach(r=>{const el=bots[r.robot_id||r.id];if(!el)return;const p=r.pose||{},x=Math.max(50,Math.min(650,50+(Number(p.x)||0)*80)),y=Math.max(35,Math.min(230,215-(Number(p.y)||0)*45));el.setAttribute('cx',x);el.setAttribute('cy',y)});$('run').disabled=false;$('step').disabled=false;const awaiting=s.mission_phase==='awaiting_owner_release';$('release-box').hidden=!awaiting;$('release').disabled=!awaiting||!$('release-check').checked}
function message(text){$('notice').textContent=text}async function start(){try{$('start').disabled=true;const boot=await call('bootstrap');csrf=boot.csrf_token;const created=await call('sessions',{request_id:requestId('create')});csrf=created.csrf_token;started=true;draw(created.state);message('Isolated session ready. Choose an explicit action to advance.')}catch(e){message('Session unavailable: '+e.message+' · View recorded fallback below.')}finally{$('start').disabled=started}}
async function mutate(path,body){try{const d=await call(path,body);draw(d);message('State updated from the isolated simulation.')}catch(e){message('Action stopped: '+e.message+'. No automatic retry was made.')}}$('start').onclick=start;$('run').onclick=()=>mutate('run',{request_id:requestId('run')});$('step').onclick=()=>mutate('step',{request_id:requestId('step'),ticks:1});$('release-check').onchange=()=>{$('release').disabled=!$('release-check').checked||!lastState||lastState.mission_phase!=='awaiting_owner_release'};$('release').onclick=()=>mutate('confirm-release',{request_id:requestId('release'),expected_policy_epoch:lastState.expected_policy_epoch,confirmed:true});
</script></body></html>'''


def _public_state(controller) -> dict[str, Any]:
    """Build the only live-state DTO; never pass through controller state."""
    raw = controller.state()
    tasks = []
    for task in raw.get("tasks", [])[:32]:
        ident, kind, state = task.get("id"), task.get("kind"), task.get("state")
        if all(isinstance(v, str) and len(v) <= 128 for v in (ident, kind, state)):
            robot = task.get("robot_id")
            tasks.append({"task_id": ident, "kind": kind, "state": state,
                          "robot_id": robot if isinstance(robot, str) and len(robot) <= 64 else None})
    robots = []
    for robot in raw.get("robots", [])[:16]:
        ident = robot.get("id")
        pose = robot.get("pose") or {}
        try:
            xyz = {axis: float(pose[axis]) for axis in ("x", "y", "yaw")}
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if (not isinstance(ident, str) or len(ident) > 64
                or not all(math.isfinite(v) and abs(v) <= 10000 for v in xyz.values())):
            continue
        robots.append({"robot_id": ident, "pose": xyz})
    commands = []
    for command in raw.get("commands", [])[-32:]:
        safe = {key: command.get(key) for key in ("kind", "state", "task_id", "robot_id")}
        if all(isinstance(safe[k], str) and len(safe[k]) <= 128 for k in ("kind", "state")):
            safe = {k: v for k, v in safe.items() if v is None or isinstance(v, str) and len(v) <= 128}
            native = command.get("native")
            native = native if isinstance(native, dict) else {}
            result = native.get("result")
            result = result if isinstance(result, dict) else {}
            effects = result.get("postcondition")
            effects = effects if isinstance(effects, dict) else {}
            booleans = {k: v for k, v in effects.items() if isinstance(k, str) and len(k) <= 64 and type(v) is bool}
            if booleans:
                safe["effects"] = booleans
            commands.append(safe)
    source_metrics = raw.get("metrics") or {}
    metrics = {key: source_metrics[key] for key in ("recovery_verified", "delivery_completed", "unauthorized_executed")
               if key in source_metrics and (type(source_metrics[key]) in (int, float) or source_metrics[key] is None)}
    phase = raw.get("mission_phase")
    if not isinstance(phase, str) or len(phase) > 64:
        phase = "unknown"
    tick = raw.get("revision", raw.get("world_tick", 0))
    if type(tick) is not int or tick < 0:
        tick = 0
    epoch = raw.get("policy_epoch")
    if type(epoch) is not int or epoch < 0:
        epoch = 0
    return {"mission_phase": phase, "revision_tick": tick, "tasks": tasks,
            "robots": robots, "commands": commands, "metrics": metrics,
            "expected_policy_epoch": epoch}


def create_hosted_app(root, *, origin, graph_port=6379, controller_factory=None,
                      max_sessions=100, max_active=3, session_ttl=1200,
                      revision="development", clock=None):
    """Create an inert, bounded simulation-only public gateway.

    `controller_factory(root)` may be injected by tests. Production provisioning
    uses the local mission composition only to obtain its controller; its FastAPI
    routes are discarded and never mounted.
    """
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("origin must be an exact HTTPS origin")
    if any(type(n) is not int or n <= 0 for n in (max_sessions, max_active, session_ttl)):
        raise ValueError("capacity and TTL limits must be positive integers")
    public_origin, host = f"https://{parsed.netloc}", parsed.hostname
    data_root = Path(root).expanduser().resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    controllers: dict[str, Any] = {}
    capability_cache: dict[str, tuple[str, str]] = {}
    operation_lock = threading.Lock()
    bootstrap_times: dict[str, list[float]] = {}

    # One process/worker can own this data root. LOCK_NB prevents a second gateway
    # from accepting traffic against the same admission/capacity database.
    lock_path = data_root / ".hosted-gateway.lock"
    lock_file = lock_path.open("a+")
    try:
        import fcntl
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (ImportError, BlockingIOError, OSError):
        lock_file.close()
        raise RuntimeError("hosted gateway data root is already locked") from None

    # The lock must be held before opening or changing the admission ledger.
    try:
        store = _HostedStore(data_root, max_sessions, max_active, clock)
    except BaseException:
        lock_file.close()
        raise

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            for controller in list(controllers.values()):
                try:
                    controller.close()
                except Exception:
                    pass
            controllers.clear()
            try:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            finally:
                lock_file.close()

    app = FastAPI(title="Witness Fleet simulation demo", docs_url=None,
                  redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[host])
    app.add_middleware(_BodyLimitMiddleware)
    app.state.hosted_store = store
    app.state.controllers = controllers

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        scheme = request.url.scheme
        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
        is_https = scheme == "https" or forwarded_proto == "https"
        if request.url.path.startswith("/demo/v1/") and not is_https:
            return JSONResponse({"error": "https_required"}, status_code=400)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    def require_origin(request: Request):
        host_header = request.headers.get("host", "").split(":", 1)[0].lower()
        if host_header != host.lower():
            raise HTTPException(400, "invalid_host")
        origin_header = request.headers.get("origin")
        if origin_header != public_origin:
            raise HTTPException(403, "origin_required")
        if request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(403, "cross_site_request")
        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
        if request.url.scheme != "https" and forwarded_proto != "https":
            raise HTTPException(400, "https_required")

    def bootstrap_token(request: Request, token: str | None):
        if not token:
            raise HTTPException(403, "csrf_required")
        cookie = request.cookies.get(COOKIE_BOOTSTRAP_CSRF)
        if not cookie or not hmac.compare_digest(_digest(cookie), _digest(token)):
            raise HTTPException(403, "csrf_invalid")

    def session(request: Request, *, mutation=False):
        capability = request.cookies.get(COOKIE_CAPABILITY)
        if not capability:
            raise HTTPException(401, "session_required")
        row = store.lookup(capability)
        if row is None:
            raise HTTPException(401, "session_invalid")
        if _now(clock) >= row["expires_at"]:
            store.status(row["sid"], "expired")
            controllers.pop(row["sid"], None)
            raise HTTPException(410, "session_expired")
        if mutation:
            require_origin(request)
            csrf = request.headers.get("x-csrf-token")
            if not csrf or not hmac.compare_digest(row["csrf_hash"], _digest(csrf)):
                raise HTTPException(403, "csrf_invalid")
        if row["status"] == "restarted" or row["sid"] not in controllers:
            raise HTTPException(410, "session_not_attached_after_restart")
        if row["status"] != "active":
            raise HTTPException(410, "session_unavailable")
        return row, controllers[row["sid"]]

    def nonblocking():
        if not operation_lock.acquire(blocking=False):
            raise HTTPException(429, "gateway_busy")

    @app.get("/healthz")
    async def health():
        return {"process": "healthy", "simulation_only": True, "revision": revision}

    @app.get("/demo", response_class=HTMLResponse)
    async def demo():
        return HTMLResponse(_DEMO_HTML)

    @app.get("/demo/v1/bootstrap")
    async def bootstrap_route(request: Request, response: Response):
        peer = request.client.host if request.client else "unknown"
        now = _now(clock)
        times = [t for t in bootstrap_times.get(peer, []) if now - t < 60]
        if len(times) >= 30:
            raise HTTPException(429, "bootstrap_rate_limited")
        times.append(now)
        bootstrap_times[peer] = times
        csrf = secrets.token_urlsafe(32)
        _secure_cookie(response, COOKIE_BOOTSTRAP_CSRF, csrf, min(session_ttl, 300))
        response.headers["Cache-Control"] = "no-store"
        return {"csrf_token": csrf, "simulation_only": True}

    @app.post("/demo/v1/sessions", status_code=201)
    async def create_session(body: CreateSession, request: Request, response: Response,
                             x_csrf_token: str | None = None):
        require_origin(request)
        bootstrap_token(request, request.headers.get("x-csrf-token"))
        if not operation_lock.acquire(blocking=False):
            raise HTTPException(429, "gateway_busy")
        try:
            free = shutil.disk_usage(data_root).free
            if free < MIN_FREE_BYTES:
                raise HTTPException(503, "storage_unavailable")
            bootstrap_cookie = request.cookies[COOKIE_BOOTSTRAP_CSRF]
            request_key = _digest(_digest(bootstrap_cookie) + ":" + body.request_id)
            previous = store.by_create_key(request_key)
            if previous:
                if previous["status"] != "active" or previous["sid"] not in controllers:
                    raise HTTPException(409, "creation_outcome_unavailable")
                capability, csrf = capability_cache.get(previous["sid"], (None, None))
                if not capability:
                    raise HTTPException(410, "capability_not_reattachable")
                _secure_cookie(response, COOKIE_CAPABILITY, capability, max(1, int(previous["expires_at"] - _now(clock))))
                _secure_cookie(response, COOKIE_SESSION_CSRF, csrf, max(1, int(previous["expires_at"] - _now(clock))))
                return {"session": {"status": "active", "expires_in": max(0, int(previous["expires_at"] - _now(clock)))},
                        "csrf_token": csrf, "state": _public_state(controllers[previous["sid"]])}
            sid, capability, csrf = uuid.uuid4().hex, secrets.token_urlsafe(48), secrets.token_urlsafe(32)
            now = _now(clock)
            try:
                reserved = store.reserve(sid, capability, csrf, request_key, now, session_ttl)
            except sqlite3.OperationalError:
                raise HTTPException(503, "admission_unavailable") from None
            if not reserved:
                raise HTTPException(429, "capacity_exhausted")
            run_root = data_root / "sessions" / sid
            try:
                if controller_factory is not None:
                    controller = controller_factory(run_root)
                else:
                    from witness_fleet.api.mission import create_mission_app
                    local_app = create_mission_app(run_root, graph_port=graph_port)
                    controller = local_app.state.controller
                    # The local app and all its routes are intentionally discarded.
                controllers[sid] = controller
                store.status(sid, "active")
                capability_cache[sid] = (capability, csrf)
            except BaseException as exc:
                store.status(sid, "failed", type(exc).__name__[:64])
                raise HTTPException(503, "session_provisioning_failed") from None
            _secure_cookie(response, COOKIE_CAPABILITY, capability, session_ttl)
            _secure_cookie(response, COOKIE_SESSION_CSRF, csrf, session_ttl)
            return {"session": {"status": "active", "expires_in": session_ttl},
                    "csrf_token": csrf, "state": _public_state(controller)}
        finally:
            operation_lock.release()

    @app.get("/demo/v1/sessions")
    async def get_session(request: Request):
        row, controller = session(request)
        state = _public_state(controller)
        return {"session": {"status": row["status"],
                            "expires_in": max(0, int(row["expires_at"] - _now(clock)))}, "state": state}

    @app.get("/demo/v1/state")
    async def get_state(request: Request):
        _, controller = session(request)
        return _public_state(controller)

    @app.post("/demo/v1/run")
    async def run(body: RunRequest, request: Request):
        row, controller = session(request, mutation=True)
        nonblocking()
        try:
            result = controller.run(body.request_id)
            return _public_state_from_result(controller, result)
        except ValueError as exc:
            raise HTTPException(409, _safe_runtime_error(str(exc))) from None
        finally:
            operation_lock.release()

    @app.post("/demo/v1/step")
    async def step(body: StepRequest, request: Request):
        _, controller = session(request, mutation=True)
        nonblocking()
        try:
            result = controller.step(body.ticks, body.request_id)
            return _public_state_from_result(controller, result)
        except ValueError as exc:
            raise HTTPException(409, _safe_runtime_error(str(exc))) from None
        finally:
            operation_lock.release()

    @app.post("/demo/v1/confirm-release")
    async def confirm_release(body: ReleaseRequest, request: Request):
        _, controller = session(request, mutation=True)
        if body.confirmed is not True:
            raise HTTPException(422, "explicit_confirmation_required")
        manifest = getattr(controller, "manifest", None) or {}
        release_id = manifest.get("release_id")
        if not isinstance(release_id, str) or not release_id:
            raise HTTPException(409, "release_unavailable")
        nonblocking()
        try:
            result = controller.approve_release(release_id, body.expected_policy_epoch, body.request_id)
            return _public_state_from_result(controller, result)
        except ValueError as exc:
            raise HTTPException(409, _safe_runtime_error(str(exc))) from None
        finally:
            operation_lock.release()

    app.add_exception_handler(sqlite3.OperationalError,
        lambda request, exc: JSONResponse({"error": "admission_unavailable"}, status_code=503))
    return app


def _safe_runtime_error(message: str) -> str:
    lowered = message.lower()
    if "unknown" in lowered or "pending" in lowered or "unresolved" in lowered:
        return "outcome_unknown_no_retry"
    if "release" in lowered or "approval" in lowered or "epoch" in lowered or "prerequisite" in lowered:
        return "release_not_authorized"
    if "held" in lowered:
        return "simulation_held"
    return "simulation_action_rejected"


def _public_state_from_result(controller, result):
    # Controller methods return a state snapshot; re-reading through the same
    # explicit projection also handles wrapped/idempotent native responses.
    return _public_state(controller)
