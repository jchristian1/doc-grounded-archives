from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


def _filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name
    if not name:
        raise ValueError(f"Unable to determine filename for {url}")
    return name


def download_file(
    url: str,
    dest_dir: Path,
    *,
    filename: str | None = None,
    retries: int = 3,
    timeout: float = 30.0,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Download a URL to a destination directory with hashing and retries."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    final_name = filename or _filename_from_url(url)
    dest_path = dest_dir / final_name

    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=timeout)

    try:
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                hasher = hashlib.sha256()
                byte_count = 0
                temp_path: Path | None = None
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with tempfile.NamedTemporaryFile(
                        dir=dest_dir, delete=False
                    ) as temp_file:
                        temp_path = Path(temp_file.name)
                        for chunk in response.iter_bytes():
                            if not chunk:
                                continue
                            temp_file.write(chunk)
                            hasher.update(chunk)
                            byte_count += len(chunk)
                if temp_path is None:
                    raise RuntimeError("Temporary file was not created.")
                os.replace(temp_path, dest_path)
                return {
                    "url": url,
                    "path": str(dest_path),
                    "sha256": hasher.hexdigest(),
                    "bytes": byte_count,
                }
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                if temp_path is not None and temp_path.exists():
                    temp_path.unlink()
                last_error = exc
                if attempt == retries:
                    raise
        if last_error is not None:
            raise last_error
    finally:
        if owns_client and client is not None:
            client.close()

    raise RuntimeError("Download failed without raising an explicit error.")
