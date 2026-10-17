from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

_NORMALIZER_VERSION = "lf-strict-utf8-v1"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True, slots=True)
class SourceRevision:
    source_id: str
    revision_id: str
    bytes_hash: str
    normalized_hash: str
    normalizer_version: str
    text: str
    bytes_path: Path
    text_path: Path


class SourceStore:
    """Append-only local retention for original bytes and canonical text."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def retain(self, source_id: str, content: bytes) -> SourceRevision:
        if not isinstance(source_id, str) or not _SAFE_ID.fullmatch(source_id):
            raise ValueError("source_id must be a trusted opaque path-safe identifier")
        if not isinstance(content, bytes):
            raise TypeError("content must be bytes")
        if b"\x00" in content:
            raise ValueError("NUL bytes are not supported in source text")
        original = content.decode("utf-8", errors="strict")
        normalized = original.replace("\r\n", "\n").replace("\r", "\n")
        normalized_bytes = normalized.encode("utf-8")
        bytes_hash = hashlib.sha256(content).hexdigest()
        normalized_hash = hashlib.sha256(normalized_bytes).hexdigest()
        revision_id = f"{source_id}:{bytes_hash}"
        directory = self._source_directory(source_id, create=True)
        bytes_path = directory / f"{bytes_hash}.bytes"
        text_path = directory / f"{bytes_hash}.txt"
        manifest_path = directory / f"{bytes_hash}.json"
        self._write_once(bytes_path, content)
        self._write_once(text_path, normalized_bytes)
        manifest = {
            "source_id": source_id,
            "revision_id": revision_id,
            "bytes_hash": bytes_hash,
            "normalized_hash": normalized_hash,
            "normalizer_version": _NORMALIZER_VERSION,
        }
        manifest_bytes = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
        self._write_once(manifest_path, manifest_bytes)
        return SourceRevision(source_id, revision_id, bytes_hash, normalized_hash,
                              _NORMALIZER_VERSION, normalized, bytes_path, text_path)

    @staticmethod
    def _write_once(path: Path, content: bytes) -> None:
        try:
            with path.open("xb") as handle:
                written = handle.write(content)
                handle.flush()
                if written != len(content):
                    raise OSError("short write")
        except FileExistsError:
            if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
                raise ValueError(f"immutable retained artifact collision: {path.name}") from None
        if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
            raise ValueError(f"immutable retained artifact verification failed: {path.name}")

    def _source_directory(self, source_id: str, *, create: bool = False) -> Path:
        directory = self.root / source_id
        if create:
            directory.mkdir(parents=True, exist_ok=True)
        if directory.is_symlink():
            raise ValueError("source directory must remain beneath the source store")
        resolved = directory.resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError("source directory must remain beneath the source store")
        return resolved

    def get(self, revision_id: str) -> SourceRevision:
        if not isinstance(revision_id, str) or ":" not in revision_id:
            raise ValueError("invalid revision_id")
        source_id, bytes_hash = revision_id.split(":", 1)
        if not _SAFE_ID.fullmatch(source_id) or not re.fullmatch(r"[0-9a-f]{64}", bytes_hash):
            raise ValueError("invalid revision_id")
        directory = self._source_directory(source_id)
        manifest_path = directory / f"{bytes_hash}.json"
        bytes_path = directory / f"{bytes_hash}.bytes"
        text_path = directory / f"{bytes_hash}.txt"
        if any(path.is_symlink() for path in (manifest_path, bytes_path, text_path)):
            raise ValueError("retained artifacts must not be symlinks")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            raw = bytes_path.read_bytes()
            text_bytes = text_path.read_bytes()
        except FileNotFoundError as exc:
            if any(path.exists() for path in (manifest_path, bytes_path, text_path)):
                raise ValueError("incomplete retained revision artifacts") from exc
            raise KeyError(revision_id) from exc
        if hashlib.sha256(raw).hexdigest() != bytes_hash:
            raise ValueError("retained source bytes failed integrity check")
        text = raw.decode("utf-8", errors="strict").replace("\r\n", "\n").replace("\r", "\n")
        if not isinstance(manifest, dict) or manifest.get("source_id") != source_id:
            raise ValueError("retained manifest identity mismatch")
        if manifest.get("bytes_hash") != bytes_hash:
            raise ValueError("retained manifest bytes hash mismatch")
        normalized_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if normalized_hash != manifest.get("normalized_hash") or text.encode("utf-8") != text_bytes:
            raise ValueError("retained normalized text failed integrity check")
        if manifest.get("revision_id") != revision_id or manifest.get("normalizer_version") != _NORMALIZER_VERSION:
            raise ValueError("retained manifest identity/version mismatch")
        return SourceRevision(source_id, revision_id, bytes_hash, normalized_hash,
                              _NORMALIZER_VERSION, text, bytes_path, text_path)

    def validate_span(self, revision_id: str, start: int, end: int, quote: str) -> dict:
        revision = self.get(revision_id)
        if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, int) or not isinstance(end, int):
            raise ValueError("span offsets must be integer codepoint positions")
        if start < 0 or end <= start or end > len(revision.text):
            raise ValueError("span must be a non-empty half-open range within normalized text")
        if not isinstance(quote, str) or revision.text[start:end] != quote:
            raise ValueError("quote does not exactly match normalized source span")
        return {
            "source_id": revision.source_id,
            "revision_id": revision.revision_id,
            "start": start,
            "end": end,
            "quote": quote,
            "quote_hash": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
            "normalized_hash": revision.normalized_hash,
            "normalizer_version": revision.normalizer_version,
            "bytes_path": str(revision.bytes_path),
            "text_path": str(revision.text_path),
        }
