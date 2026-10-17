#!/usr/bin/env bash
# Run through Azure VM Run Command. Dedicated host only; no retained data deletion.
set -euo pipefail
umask 027
IMAGE="${1:?digest-qualified application image required}"
HOST="${2:?public DNS hostname required}"
REVISION="${3:?source revision required}"
[[ "$IMAGE" =~ ^witnessfleetguglxni\.azurecr\.io/witness-fleet@sha256:[a-f0-9]{64}$ ]] || { printf 'Invalid image\n' >&2; exit 2; }
[[ "$HOST" =~ ^[a-z0-9.-]+\.cloudapp\.azure\.com$ ]] || exit 2
[[ "$REVISION" =~ ^[a-f0-9]{40}$ ]] || exit 2
cloud-init status --wait >/dev/null
ROOT=/opt/witness-fleet
mkdir -p "$ROOT/data" "$ROOT/caddy-config"
chown 10001:10001 "$ROOT/data"
chmod 750 "$ROOT/data"
az login --identity --allow-no-subscriptions --output none
az acr login --name witnessfleetguglxni --only-show-errors >/dev/null
docker pull "$IMAGE" >/dev/null
# A single dedicated persistent graph server. Never recreate/erase a prior graph.
if ! docker inspect wf-public-graph >/dev/null 2>&1; then
  docker run -d --name wf-public-graph --label app=witness-fleet --restart unless-stopped \
    --memory 1536m --cpus 1 --log-opt max-size=10m --log-opt max-file=3 \
    -p 127.0.0.1:6379:6379 -e BROWSER=0 \
    -e 'REDIS_ARGS=--appendonly yes --appendfsync always --maxmemory 900mb --maxmemory-policy noeviction' \
    -v wf-public-graph-data:/var/lib/falkordb/data \
    falkordb/falkordb@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6 >/dev/null
fi
[[ "$(docker inspect -f '{{.State.Running}}' wf-public-graph)" == true ]] || { printf 'Existing graph is not running; refusing automatic recovery\n' >&2; exit 3; }
[[ "$(docker exec wf-public-graph redis-cli ping)" == PONG ]] || exit 3
# Do not replay previous simulation sessions after restart. Stop gracefully, retain container.
if docker inspect wf-public-app >/dev/null 2>&1; then
  docker stop --time 120 wf-public-app >/dev/null
  docker rename wf-public-app "wf-public-app-retained-$(date -u +%Y%m%dT%H%M%SZ)"
fi
docker run -d --name wf-public-app --label app=witness-fleet --restart unless-stopped \
  --network host --read-only --tmpfs /tmp:rw,noexec,nosuid,size=256m \
  --security-opt no-new-privileges --cap-drop ALL --pids-limit 256 \
  --memory 3g --cpus 1.5 --log-opt max-size=10m --log-opt max-file=3 \
  -e WITNESS_DEMO_ORIGIN="https://$HOST" -e WITNESS_REVISION="$REVISION" \
  -e WITNESS_DATA_ROOT=/data -v "$ROOT/data:/data" "$IMAGE" >/dev/null
python3 - "$ROOT/caddy-config/Caddyfile" "$HOST" <<'PY'
from pathlib import Path
import sys
Path(sys.argv[1]).write_text('''{
  admin off
  email guglaniaaryan@gmail.com
}
%s {
  encode zstd gzip
  request_body {
    max_size 16KB
  }
  header {
    X-Content-Type-Options nosniff
    Referrer-Policy no-referrer
    X-Frame-Options DENY
    Permissions-Policy "camera=(), microphone=(), geolocation=()"
    Strict-Transport-Security "max-age=31536000"
  }
  reverse_proxy 127.0.0.1:8080 {
    transport http {
      read_timeout 180s
    }
  }
}
''' % sys.argv[2])
PY
if ! docker inspect wf-public-proxy >/dev/null 2>&1; then
  docker run -d --name wf-public-proxy --label app=witness-fleet --restart unless-stopped \
    --network host --memory 256m --log-opt max-size=10m --log-opt max-file=3 \
    -v "$ROOT/caddy-config:/etc/caddy:ro" -v wf-public-caddy-data:/data -v wf-public-caddy-config:/config \
    caddy:2.10.2@sha256:c3d7ee5d2b11f9dc54f947f68a734c84e9c9666c92c88a7f30b9cba5da182adb >/dev/null
fi
python3 - "$HOST" "$REVISION" <<'PY'
import json,sys,time,urllib.request
for attempt in range(24):
    try:
        req=urllib.request.Request('http://127.0.0.1:8080/healthz', headers={'Host': sys.argv[1]})
        with urllib.request.urlopen(req, timeout=5) as response:
            value=json.load(response)
        assert value['revision']==sys.argv[2]
        assert value['simulation_only'] is True
        print(json.dumps(value))
        break
    except Exception:
        if attempt == 23: raise
        time.sleep(5)
PY
