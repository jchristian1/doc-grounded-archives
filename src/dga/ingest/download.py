from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import httpx

_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_DEFAULT_MAX_REDIRECTS = 5


def _filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name
    if not name:
        raise ValueError(f"Unable to determine filename for {url}")
    return name


def _normalize_allowed_domains(
    allowed_domains: Iterable[str] | None, url: str
) -> tuple[str, ...]:
    if allowed_domains is None:
        hostname = urlparse(url).hostname
        if not hostname:
            raise ValueError(f"URL must include a hostname: {url}")
        allowed_domains = (hostname,)
    return tuple(domain.lower() for domain in allowed_domains)


def _is_domain_allowed(hostname: str, allowed_domains: Iterable[str]) -> bool:
    hostname = hostname.lower()
    for domain in allowed_domains:
        if hostname == domain or hostname.endswith(f".{domain}"):
            return True
    return False


def _ensure_allowed_url(url: str, allowed_domains: Iterable[str]) -> None:
    parsed = urlparse(url)
    if not parsed.hostname:
        raise ValueError(f"URL must include a hostname: {url}")
    if not _is_domain_allowed(parsed.hostname, allowed_domains):
        raise ValueError(f"Redirected URL domain not in allowlist: {url}")


def _is_age_verify_redirect(response: httpx.Response) -> bool:
    location = response.headers.get("Location", "")
    return (
        response.status_code in _REDIRECT_STATUSES
        and location
        and "/age-verify" in location
    )


def _verify_age_gate(
    client: httpx.Client, url: str, allowed_domains: Iterable[str]
) -> None:
    response = client.get(url, follow_redirects=False)
    if not _is_age_verify_redirect(response):
        return
    location = response.headers["Location"]
    age_url = urljoin(str(response.url), location)
    _ensure_allowed_url(age_url, allowed_domains)
    verified = client.get(age_url, follow_redirects=True)
    for history_response in (*verified.history, verified):
        _ensure_allowed_url(str(history_response.url), allowed_domains)


def _stream_with_redirects(
    client: httpx.Client,
    url: str,
    allowed_domains: Iterable[str],
    hasher: hashlib._Hash,
    dest_dir: Path,
) -> tuple[Path, int]:
    current_url = url
    redirects = 0
    byte_count = 0
    temp_path: Path | None = None
    while True:
        with client.stream("GET", current_url, follow_redirects=False) as response:
            if response.status_code in _REDIRECT_STATUSES and response.headers.get(
                "Location"
            ):
                location = response.headers["Location"]
                next_url = urljoin(str(response.url), location)
                _ensure_allowed_url(next_url, allowed_domains)
                redirects += 1
                if redirects > _DEFAULT_MAX_REDIRECTS:
                    raise httpx.HTTPStatusError(
                        "Too many redirects.",
                        request=response.request,
                        response=response,
                    )
                current_url = next_url
                continue
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
            break
    if temp_path is None:
        raise RuntimeError("Temporary file was not created.")
    return temp_path, byte_count


def download_file(
    url: str,
    dest_dir: Path,
    *,
    filename: str | None = None,
    retries: int = 3,
    timeout: float = 30.0,
    allowed_domains: Iterable[str] | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Download a URL to a destination directory with hashing and retries."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    final_name = filename or _filename_from_url(url)
    dest_path = dest_dir / final_name

    allowed_domains = _normalize_allowed_domains(allowed_domains, url)
    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=timeout, follow_redirects=False)

    try:
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            temp_path: Path | None = None
            try:
                hasher = hashlib.sha256()
                _verify_age_gate(client, url, allowed_domains)
                temp_path, byte_count = _stream_with_redirects(
                    client, url, allowed_domains, hasher, dest_dir
                )
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
