from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from graphrag_sdk import Column, ConnectionConfig, Context, TableMapping
from graphrag_sdk.core.connection import FalkorDBConnection
from graphrag_sdk.ingestion.loaders.record_loader import CsvRecordLoader
from graphrag_sdk.ingestion.mapping import record_mapping_for
from graphrag_sdk.ingestion.structured_pipeline import StructuredIngestionPipeline
from graphrag_sdk.storage.graph_store import GraphStore

from witness_fleet.ingestion import SourceStore

SDK_PIN = "35e67a0b27fdcc7f2c28508b09e86169851a8187"
SDK_VERSION = "1.4.0"


class CorpusSDKAdapter:
    """Only writes declared, source-located synthetic record rows; never finalizes."""

    GRAPH_NAME = "wf:demo:corpus"
    ROLE = "wf_corpus"
    ALLOWED_GRAPHS = {"wf:demo:corpus", "wf:demo:corpus_ontology"}
    FIXTURE_SOURCE_IDS = {
        "facility_manual_r1", "owner_roster_r1", "maintenance_ticket_r1",
        "restriction_decision_r1", "unsigned_chat_r1", "release_decision_r1",
        "blanket_ban_r1", "conflicting_owner_r1",
    }

    def __init__(self, source_store: SourceStore, fixture_root: str | Path = "fixtures/sources", *,
                 host: str = "127.0.0.1", port: int = 6380,
                 username: str = "wf_corpus", password: str | None = None,
                 graph_name: str = GRAPH_NAME):
        if graph_name not in self.ALLOWED_GRAPHS or graph_name != self.GRAPH_NAME:
            raise ValueError("only the configured synthetic tenant corpus graph is supported")
        if username != self.ROLE:
            raise ValueError("corpus adapter requires the least-privilege corpus role")
        self.source_store = source_store
        self.fixture_root = Path(fixture_root).resolve()
        self.host, self.port, self.username = host, port, username
        self._password = password
        self.graph_name = graph_name

    def ingest_path(self, source_id: str) -> dict[str, Any]:
        path = self._fixture_path(source_id)
        return self.ingest_source(source_id, path.read_bytes())

    def ingest_source(self, source_id: str, content: bytes) -> dict[str, Any]:
        path = self._fixture_path(source_id)
        if not isinstance(content, bytes) or content != path.read_bytes():
            raise ValueError("source bytes do not match the allowlisted synthetic fixture")
        revision = self.source_store.retain(source_id, content)
        rows = self._rows(revision.text, source_id, revision.revision_id)
        if not rows:
            raise ValueError("source has no exact evidence quote to ingest")
        return asyncio.run(self._ingest_rows(source_id, revision.revision_id, rows))

    def _fixture_path(self, source_id: str) -> Path:
        if source_id not in self.FIXTURE_SOURCE_IDS:
            raise ValueError("source_id is not on the synthetic fixture allowlist")
        path = self.fixture_root / f"{source_id}.json"
        if not path.is_file():
            path = self.fixture_root / f"{source_id}.md"
        if not path.is_file() or path.is_symlink() or path.resolve().parent != self.fixture_root:
            raise ValueError("allowlisted source file does not exist beneath fixture root")
        return path

    @staticmethod
    def _rows(text: str, source_id: str, revision_id: str) -> list[dict[str, str]]:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = {}
        quotes: list[str] = []
        if isinstance(parsed, dict):
            quotes.extend(value for key, value in parsed.items()
                          if key.endswith("quote") and isinstance(value, str) and value.strip())
        if not quotes:
            lines: list[tuple[str, int]] = []
            offset = 0
            for line in text.splitlines(keepends=True):
                quote = line.strip()
                if quote:
                    start = offset + len(line) - len(line.lstrip())
                    lines.append((quote, start))
                offset += len(line)
            return CorpusSDKAdapter._located_rows(lines, text, source_id, revision_id)
        located_quotes: list[tuple[str, int]] = []
        search_from = 0
        for quote in quotes:
            start = text.find(quote, search_from)
            if start < 0:
                start = text.find(quote)
            if start < 0:
                continue
            located_quotes.append((quote, start))
            search_from = start + len(quote)
        return CorpusSDKAdapter._located_rows(located_quotes, text, source_id, revision_id)

    @staticmethod
    def _located_rows(
        located_quotes: list[tuple[str, int]], text: str, source_id: str, revision_id: str,
    ) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        seen: set[tuple[int, int, str]] = set()
        for quote, start in located_quotes:
            end = start + len(quote)
            if text[start:end] != quote:
                continue
            key = (start, end, quote)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "span_id": hashlib.sha256(f"{revision_id}:{start}:{end}:{quote}".encode()).hexdigest(),
                "quote": quote, "source_id": source_id, "revision_id": revision_id,
                "start": str(start), "end": str(end),
                "quote_hash": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
            })
        return rows

    def _config(self) -> ConnectionConfig:
        return ConnectionConfig(host=self.host, port=self.port, username=self.username,
                                password=self._password, graph_name=self.graph_name,
                                retry_count=1, query_timeout_ms=5000)

    async def _ingest_rows(self, source_id: str, revision_id: str, rows: list[dict[str, str]]) -> dict[str, Any]:
        connection = FalkorDBConnection(self._config())
        try:
            store = GraphStore(connection)
            mapping = TableMapping(
                source="evidence.csv", label="EvidenceSpan", key="span_id", name="quote",
                properties={"source_id": Column("source_id"), "revision_id": Column("revision_id"),
                            "start": Column("start", "INTEGER"), "end": Column("end", "INTEGER"),
                            "quote_hash": Column("quote_hash")},
                description="Exact source-located synthetic evidence candidate; not an approval.",
            )
            with tempfile.TemporaryDirectory(prefix="wf-corpus-") as tmp:
                source = Path(tmp) / "evidence.csv"
                with source.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                pipeline = StructuredIngestionPipeline(CsvRecordLoader(), store)
                result = await pipeline.run(str(source), record_mapping_for(mapping),
                                            Context(tenant_id="demo"),
                                            document_id=f"{source_id}:{revision_id}", strict=True)
            return {"source_id": source_id, "revision_id": revision_id, "rows": result.records,
                    "graph": self.graph_name, "sdk_version": SDK_VERSION, "sdk_pin": SDK_PIN,
                    "mode": "structured-no-model-no-finalize"}
        finally:
            await connection.close()

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise ValueError("query must be a non-empty string of at most 500 chars")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
            raise ValueError("limit must be in [1, 50]")
        return asyncio.run(self._search(query, limit))

    async def _search(self, query_text: str, limit: int) -> list[dict[str, Any]]:
        connection = FalkorDBConnection(self._config())
        try:
            cypher = ("MATCH (d:Document)-[:PART_OF]->(c:Chunk) "
                      "WHERE toLower(c.text) CONTAINS $needle "
                      "RETURN d.id, c.id, c.text ORDER BY c.id LIMIT $limit")
            result = await connection.graph.ro_query(
                cypher, {"needle": query_text.casefold(), "limit": limit})
            raw_rows = getattr(result, "result_set", []) or []
            candidates: list[dict[str, Any]] = []
            for row in raw_rows:
                if not isinstance(row, (tuple, list)) or len(row) < 3:
                    continue
                document_id, chunk_id, chunk_text = str(row[0]), str(row[1]), str(row[2])
                for source_id, revision_id in self._known_revisions():
                    if document_id != f"{source_id}:{revision_id}":
                        continue
                    revision = self.source_store.get(revision_id)
                    for match in re.finditer(re.escape(query_text), revision.text, re.IGNORECASE):
                        start, end = match.span()
                        quote = revision.text[start:end]
                        if quote.casefold() not in chunk_text.casefold():
                            continue
                        validated = self.source_store.validate_span(revision_id, start, end, quote)
                        candidates.append({
                            key: value for key, value in validated.items()
                            if key not in {"bytes_path", "text_path"}
                        } | {"chunk_id": chunk_id, "candidate_kind": "lexical-sdk-chunk"})
            return candidates[:limit]
        finally:
            await connection.close()

    async def graph_ready(self) -> bool:
        connection = None
        try:
            connection = FalkorDBConnection(self._config())
            result = await connection.graph.ro_query("RETURN 1", {})
            rows = getattr(result, "result_set", []) or []
            return bool(rows and rows[0] and rows[0][0] == 1)
        except Exception:
            return False
        finally:
            if connection is not None:
                try:
                    await connection.close()
                except Exception:
                    return False

    def _known_revisions(self) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []
        for source_id in self.FIXTURE_SOURCE_IDS:
            folder = self.source_store.root / source_id
            for manifest in folder.glob("*.json") if folder.exists() else ():
                try:
                    payload = json.loads(manifest.read_text())
                    revision_id = payload["revision_id"]
                    revision = self.source_store.get(revision_id)
                    if revision.source_id == source_id:
                        found.append((source_id, revision_id))
                except (OSError, ValueError, KeyError, TypeError):
                    continue
        return found

    @staticmethod
    def is_governance_approved(candidate: dict[str, Any]) -> bool:
        """Corpus text is never a source of promotion approval."""
        return False
