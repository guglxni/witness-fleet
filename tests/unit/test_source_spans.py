import hashlib
import json
from dataclasses import FrozenInstanceError

import pytest

from witness_fleet.ingestion import SourceStore


def test_retain_preserves_original_bytes_and_normalizes_newlines(tmp_path):
    store = SourceStore(tmp_path)
    raw = "α\r\nβ\rγ".encode()
    revision = store.retain("manual", raw)

    assert revision.bytes_hash == hashlib.sha256(raw).hexdigest()
    assert revision.text == "α\nβ\nγ"
    assert revision.normalized_hash == hashlib.sha256(revision.text.encode()).hexdigest()
    assert revision.bytes_path.read_bytes() == raw
    assert store.get(revision.revision_id) == revision
    with pytest.raises((FrozenInstanceError, AttributeError)):
        revision.text = "changed"


def test_span_is_half_open_codepoint_range_with_quote_hash(tmp_path):
    store = SourceStore(tmp_path)
    revision = store.retain("manual", "A café 🚚 policy.".encode())
    start = revision.text.index("café")
    quote = "café 🚚"

    span = store.validate_span(revision.revision_id, start, start + len(quote), quote)

    assert span["source_id"] == "manual"
    assert span["revision_id"] == revision.revision_id
    assert span["start"] == start and span["end"] == start + len(quote)
    assert span["quote"] == quote
    assert span["quote_hash"] == hashlib.sha256(quote.encode()).hexdigest()


@pytest.mark.parametrize("content", [b"\xff", b"a\x00b"])
def test_rejects_invalid_utf8_and_nul(tmp_path, content):
    with pytest.raises((ValueError, UnicodeError)):
        SourceStore(tmp_path).retain("manual", content)


def test_rejects_bad_spans_quote_mismatch_and_untrusted_ids(tmp_path):
    store = SourceStore(tmp_path)
    revision = store.retain("manual", b"trusted text")
    for start, end, quote in [(-1, 2, "tr"), (0, 999, "trusted"), (0, 2, "xx")]:
        with pytest.raises(ValueError):
            store.validate_span(revision.revision_id, start, end, quote)
    for source_id in ["../escape", "/absolute", "", "a/b", ".."]:
        with pytest.raises(ValueError):
            store.retain(source_id, b"x")


def test_same_source_same_content_dedupes_but_new_content_keeps_old_revision(tmp_path):
    store = SourceStore(tmp_path)
    first = store.retain("manual", b"one")
    assert store.retain("manual", b"one") == first
    second = store.retain("manual", b"two")
    assert second.revision_id != first.revision_id
    assert store.get(first.revision_id).text == "one"
    assert store.get(second.revision_id).text == "two"


def test_get_rejects_manifest_from_a_different_source_identity(tmp_path):
    store = SourceStore(tmp_path)
    revision = store.retain("manual", b"retained")
    manifest = revision.bytes_path.with_suffix(".json")
    payload = json.loads(manifest.read_text())
    payload["source_id"] = "other-source"
    manifest.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="manifest"):
        store.get(revision.revision_id)


def test_retain_rejects_symlinked_source_directory(tmp_path):
    store = SourceStore(tmp_path / "store")
    outside = tmp_path / "outside"
    outside.mkdir()
    (store.root / "manual").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="beneath"):
        store.retain("manual", b"must stay inside")
    assert list(outside.iterdir()) == []


def test_get_detects_corrupted_retained_bytes_and_normalized_text(tmp_path):
    store = SourceStore(tmp_path)
    revision = store.retain("manual", b"immutable")
    revision.bytes_path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="source bytes"):
        store.get(revision.revision_id)

    revision.bytes_path.write_bytes(b"immutable")
    revision.text_path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="normalized text"):
        store.get(revision.revision_id)


def test_get_reports_partial_revision_as_corruption_not_missing(tmp_path):
    store = SourceStore(tmp_path)
    revision = store.retain("manual", b"partial")
    revision.text_path.unlink()

    with pytest.raises(ValueError, match="incomplete"):
        store.get(revision.revision_id)
