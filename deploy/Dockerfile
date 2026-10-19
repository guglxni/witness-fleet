# syntax=docker/dockerfile:1.7
FROM node:24-bookworm-slim@sha256:a5f4366e834695d5f363b920c104953a535d3a9864d1bdf74566a0ebe01daee5 AS demo-ui
WORKDIR /ui/demo
COPY demo/package.json demo/package-lock.json ./
RUN npm ci
COPY demo/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.11.15@sha256:e590846f4776907b254ac0f44b5b380347af5d90d668138ca7938d1b0c2f98d3 AS uv
FROM python:3.12-slim-bookworm
COPY --from=uv /uv /uvx /bin/
RUN apt-get update && apt-get install -y --no-install-recommends libegl1 libgl1 libglfw3 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY services/ services/
COPY --from=demo-ui /ui/src/witness_fleet/hosting/static/ src/witness_fleet/hosting/static/
RUN uv sync --frozen --no-dev --extra simulator && useradd --uid 10001 --create-home witness && mkdir -p /data && chown witness:witness /data
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 MUJOCO_GL=egl WITNESS_DATA_DIR=/data
USER 10001:10001
EXPOSE 8080
CMD ["python", "-m", "witness_fleet.hosting"]
