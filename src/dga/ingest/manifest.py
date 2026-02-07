from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def append_manifest(record: dict[str, Any], path: Path | str = "data/processed/manifest.jsonl") -> None:
    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True))
        handle.write("\n")


def read_manifest(path: Path | str = "data/processed/manifest.jsonl") -> list[dict[str, Any]]:
    manifest_path = Path(path)
    if not manifest_path.exists():
        return []
    records: list[dict[str, Any]] = []
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def seen_url(url: str, records: Iterable[dict[str, Any]]) -> bool:
    return any(record.get("url") == url for record in records)


def seen_sha256(sha256: str, records: Iterable[dict[str, Any]]) -> bool:
    return any(record.get("sha256") == sha256 for record in records)
