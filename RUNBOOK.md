# Operator quick start (local, synthetic)

```sh
cd <repository>
python3 scripts/setup.py
.venv/bin/witness-fleet doctor
```

The setup is idempotent and preserves the existing pinned vendor checkout and Docker volume. The native main environment and GraphRAG-SDK Python environment are intentionally isolated. It does not run a production bundle or clean frontend build output.

- Graph: 127.0.0.1:6380, container witness-fleet-graph, pinned module 60002, AOF always.
- Corpus API: http://127.0.0.1:8092, structured pinned SDK imports only; no semantic authority.
- Operator API: http://127.0.0.1:8090/api/health.
- Development console: http://127.0.0.1:5173.

Model calls are disabled by default. Live native provider/schema and calibration acceptance is separate from offline protocol fixtures. No physical robot control is provided.

## Verified native-component capture (not fleet acceptance)

From the repository root, the exercised command is:

```sh
.venv/bin/mjpython -m scripts.capture_simulation --output artifacts/repair-wave/native-visual --seed 3
```

This uses the actual MuJoCo renderer and physical controllers. `recovery.mp4` shows recovery only. `measurements.json` also records an actual loaded courier crossing with `delivery_zone: true`. The verified video is H.264, 640x368, 20fps, 11.8 seconds. FFmpeg emits a compatibility resize warning because rendering starts at640x360. Direct script-path execution fails to import the `services` namespace; use the module invocation above.

The current checkpoint-model fingerprint component passed37 simulation tests and matching independent SPEC/QUALITY review. These captures do not establish graph-authorized fleet behavior, process-kill coordinator recovery, or real-robot safety.

Full integrated run commands and test results will be appended only after exercised.
