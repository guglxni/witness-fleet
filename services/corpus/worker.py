from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sdk_adapter import SDK_PIN, SDK_VERSION, CorpusSDKAdapter

from witness_fleet.ingestion import SourceStore


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(min_length=1, max_length=128)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)


def create_app(adapter: CorpusSDKAdapter | None = None) -> FastAPI:
    adapter = adapter or CorpusSDKAdapter(SourceStore(".data/corpus/sources"))
    app = FastAPI(title="Synthetic GraphRAG Corpus Service", version="0.1.0")

    @app.get("/health")
    async def health():
        if not await adapter.graph_ready():
            raise HTTPException(status_code=503, detail="corpus graph unavailable")
        return {"status": "ok", "graph": adapter.GRAPH_NAME, "sdk_pin": SDK_PIN, "sdk_version": SDK_VERSION}

    @app.post("/ingest")
    def ingest(body: IngestRequest):
        try:
            return adapter.ingest_path(body.source_id)
        except (ValueError, UnicodeError, OSError) as exc:
            raise HTTPException(status_code=422, detail="ingest request rejected") from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="corpus ingest unavailable") from exc

    @app.post("/search")
    def search(body: SearchRequest):
        try:
            return {"candidates": adapter.search(body.query, body.limit)}
        except (ValueError, UnicodeError, OSError) as exc:
            raise HTTPException(status_code=422, detail="search request rejected") from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="corpus search unavailable") from exc

    return app


app = create_app()
