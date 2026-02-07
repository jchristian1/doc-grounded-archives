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


def test_download_age_verify_redirect(tmp_path: Path) -> None:
    payload = b"%PDF-1.4 sample"
    state = {"file_hits": 0, "age_hits": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/file.pdf":
            state["file_hits"] += 1
            if state["file_hits"] == 1:
                return httpx.Response(
                    302,
                    headers={
                        "Location": "/age-verify?destination=/file.pdf",
                        "Set-Cookie": "QueueITAccepted-abc=1; Path=/; Expires=Wed, 21 Oct 2025 07:28:00 GMT",
                    },
                )
            return httpx.Response(200, content=payload)
        if request.url.path == "/age-verify":
            state["age_hits"] += 1
            return httpx.Response(200, content=b"ok")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    metadata = download_file("https://example.com/file.pdf", tmp_path, client=client)
    expected_hash = hashlib.sha256(payload).hexdigest()

    assert metadata["sha256"] == expected_hash
    assert Path(metadata["path"]).read_bytes() == payload
    assert state["file_hits"] == 2
    assert state["age_hits"] == 1
    client.close()
