import hashlib
from pathlib import Path

import httpx
import pytest

from dga.ingest import append_manifest, download_file, load_registry, read_manifest


def test_registry_rejects_non_allowlisted_domain(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        "\n".join(
            [
                "allowed_domains:",
                "  - example.com",
                "datasets:",
                "  - id: sample",
                "    name: Sample",
                "    urls:",
                "      - https://not-example.com/file.pdf",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="allowlist"):
        load_registry(registry_path)


def test_manifest_roundtrip(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.jsonl"
    record = {
        "dataset_id": "sample",
        "url": "https://example.com/file.pdf",
        "sha256": "abc123",
    }
    append_manifest(record, manifest_path)
    records = read_manifest(manifest_path)
    assert records == [record]


def test_download_hashing(tmp_path: Path) -> None:
    payload = b"hello world"

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    metadata = download_file(
        "https://example.com/file.txt", tmp_path, client=client
    )
    expected_hash = hashlib.sha256(payload).hexdigest()
    downloaded_path = Path(metadata["path"])

    assert metadata["sha256"] == expected_hash
    assert downloaded_path.read_bytes() == payload
    client.close()
