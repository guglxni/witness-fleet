# Local setup and operator runbook

## Scope and prerequisites

This is a local synthetic simulation workflow. The repository front page lists Python 3.12+, `uv`, Node 26+, Docker Desktop and FFmpeg as the full demo toolchain ([root `README.md`](../../README.md)). The main project declares Python `>=3.12,<3.14` and an optional simulator extra in [`pyproject.toml`](../../pyproject.toml). The integrated corpus SDK uses a separate project/environment and is not needed to authorize SC-001 actions ([`INTEGRATIONS.md`](../../INTEGRATIONS.md)). No cloud credentials are required for this local mission.

From the repository root, the documented full path is:

```sh
uv sync --frozen --extra dev --extra simulator
npm --prefix web ci
npm --prefix web run build
.venv/bin/witness-fleet doctor
.venv/bin/python -m scripts.run_local_mission --run-dir /tmp/witness-fleet-new-run --port 8095
```

These commands are the existing root README recipe, not executed as part of writing this guide. The launcher requires an installed CLI and built `web/dist`, validates that the selected run directory is new/empty, starts a uniquely named graph container on a dynamic loopback port, and retains the volume and run directory on exit ([`scripts/run_local_mission.py`](../../scripts/run_local_mission.py)). Never point it at a retained run directory.

Open `http://127.0.0.1:8095` (or the port passed to the launcher). Startup should not move robots. Use the explicit Run action; inspect the graph/source witness and pause at owner release; submit the explicit local demo-owner release only when the synthetic demo steps are intended; then resume the task run. Root README records this operator sequence ([`README.md`](../../README.md)); mission phase and release checks are in [`runtime/mission.py`](../../src/witness_fleet/runtime/mission.py).

## Before a demo

- Use a fresh, dedicated, empty local run path.
- Review the loopback UI/API endpoint and Docker ownership label/name printed by the launcher.
- Verify the local Docker engine and required port availability without changing existing containers.
- Confirm `doctor` reports dependency status; it reports `motion_authorized: false` because it is a diagnostic command, not an arming endpoint ([`cli.py`](../../src/witness_fleet/cli.py)).
- Confirm operator understands the local configured principal is synthetic and `model_mode` is disabled.
- Do not expose the loopback app externally or copy credentials into source/config.

## During the mission

1. Start the episode explicitly; startup should be inert.
2. Allow the first four task outcomes to complete, then pause at the owner gate.
3. Inspect the retained source span, staged release target, policy epoch and physical verification evidence.
4. Submit the explicit release only for the intended exact target and current expected epoch.
5. Resume; inspect courier-scoped clearance and final delivery outcome separately.
6. If a command becomes unknown, any integrity/version check fails, or state is held, stop new admission and keep run data. Do not issue a duplicate motion request to see if it works.

## HOLD or interrupted process

- Stop issuing UI actions. Preserve `run_dir`, graph container/volume name, simulator journal/checkpoint, mission request ledger, source artifacts and relevant sanitized status output.
- Capture the exact visible phase, episode, task/command IDs, world tick, graph/policy/coordinator versions, dispatch sequence and hold reason. Do not include secrets.
- Determine whether the container/app process is still the one created for this exact run; do not stop or delete other containers.
- On restart, use the same retained identity/settings for inspection. Constructors do not take over a live lease or guess that an unknown command finished ([`runtime/coordinator.py`](../../src/witness_fleet/runtime/coordinator.py)).
- Resolve durable command/event receipts and any graph/simulator cursor mismatch through the explicit reconciliation path. If no positive proof determines whether motion was admitted, remain held.
- Only an identified clean new run may be started in a new empty directory. Never delete the graph volume or retained journal as a recovery shortcut.

The detailed protocol is in [`RUNTIME.md`](../../RUNTIME.md) §2–4 and [`services/simulator/service.py`](../../services/simulator/service.py). The ordinary successful mission UI flow is not itself a restart-recovery test.

## Shutdown and retention

Ctrl-C stops only the launched app/container instance; the volume and data are retained by design. Record the exact run directory and graph container/volume for later inspection. Cleanup/destruction requires an explicit separate decision and exact resource identification; this guide provides no bulk prune command.

## Other local command paths

The older inspection-only CLI and standalone native component capture have distinct scopes. See root [`README.md`](../../README.md), [`RUNBOOK.md`](../../RUNBOOK.md) and [submission capture instructions](../submission/CAPTURE.md). A component capture is not evidence of the full graph-authorized seven-task mission.
