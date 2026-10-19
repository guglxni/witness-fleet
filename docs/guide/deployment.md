# Deployment topology

Witness Fleet retains two separate operating boundaries:

1. **Local operator console:** the existing CLI and `scripts/run_local_mission.py` bind to loopback, use explicit configured owner authority, and retain evidence. They are not exposed as a public website API.
2. **Hosted simulation demo:** an additive gateway under [`src/witness_fleet/hosting`](../../src/witness_fleet/hosting) allocates synthetic, visitor-isolated SC-001 sessions. The static product site on Vercel links to this separate HTTPS origin.

## Azure

The [Bicep template](../../deploy/azure/main.bicep) provisions a dedicated Linux VM and network with only inbound HTTP/HTTPS. FalkorDB binds to loopback; the application binds to loopback behind Caddy. The app runs non-root, with resource limits, read-only filesystem, and an explicit persistent data mount. Registry pulls use VM managed identity rather than committed credentials.

The [deployment runbook](../../deploy/azure/README.md) documents infrastructure, deployment and preservation behavior. The actual running revision must be read from `/healthz`; the existence of source or a successful VM provisioning response does not prove mission execution.

## Hosted API boundary

The [hosted gateway](../../src/witness_fleet/hosting/__init__.py) has strict request DTOs, exact Origin/Host checks, Secure HttpOnly SameSite session cookies, separate CSRF protection, server-selected actors and graph namespaces, rate limits and durable resource limits. Its projection excludes internal paths, source text, raw graph data and local owner identity. The authenticated read-only `GET /demo/v1/scene` adds bounded, allowlisted native MuJoCo primitives and sites; it does not advance physics. The hosted React interface and its Three.js renderer are packaged as same-origin static assets in the application image, not loaded from a third-party script CDN. It has no arbitrary command, reset, graph query, source upload or HOLD-clear route.

A visitor confirms a synthetic demo release. That is **not** an authenticated production resource-owner identity. Uncertain outcomes do not grant authority to replay work.

## GitHub delivery

[Verification](../../.github/workflows/verify.yml) separates Python/corpus and frontend environments. [Azure deployment](../../.github/workflows/deploy-azure.yml) uses an environment-bound GitHub OIDC identity. Vercel's repository integration builds `site/` separately. These workflows must be checked at their exact commit before calling a deployment verified.

## Production exclusions

This demo does not establish multi-tenant production isolation, real robot commissioning, cloud restore objectives, industrial safety certification or physical fleet readiness. Retained data is not automatically purged to recover capacity. Hosting uptime does not replace graph/physical outcome verification.
