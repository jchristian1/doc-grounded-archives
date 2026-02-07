from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import yaml


@dataclass(frozen=True)
class DatasetEntry:
    dataset_id: str
    name: str
    urls: tuple[str, ...]


@dataclass(frozen=True)
class Registry:
    allowed_domains: tuple[str, ...]
    datasets: tuple[DatasetEntry, ...]

    def by_id(self, dataset_id: str) -> DatasetEntry | None:
        for dataset in self.datasets:
            if dataset.dataset_id == dataset_id:
                return dataset
        return None


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Registry file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("Registry YAML must define a mapping at the top level.")
    return data


def _normalize_domains(domains: Iterable[str]) -> tuple[str, ...]:
    normalized = []
    for domain in domains:
        if not domain or not isinstance(domain, str):
            raise ValueError("Allowed domains must be non-empty strings.")
        normalized.append(domain.lower())
    return tuple(sorted(set(normalized)))


def _is_domain_allowed(hostname: str, allowed_domains: Iterable[str]) -> bool:
    hostname = hostname.lower()
    for domain in allowed_domains:
        if hostname == domain or hostname.endswith(f".{domain}"):
            return True
    return False


def _validate_urls(urls: Iterable[str], allowed_domains: Iterable[str]) -> tuple[str, ...]:
    validated: list[str] = []
    for url in urls:
        if not isinstance(url, str) or not url:
            raise ValueError("Dataset URLs must be non-empty strings.")
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise ValueError(f"URL must use https: {url}")
        if not parsed.hostname:
            raise ValueError(f"URL must include a hostname: {url}")
        if not _is_domain_allowed(parsed.hostname, allowed_domains):
            raise ValueError(f"URL domain not in allowlist: {url}")
        validated.append(url)
    return tuple(validated)


def load_registry(path: Path | str = "datasets/registry.yaml") -> Registry:
    """Load and validate the dataset registry."""
    path = Path(path)
    data = _load_yaml(path)
    allowed_domains = _normalize_domains(data.get("allowed_domains", []))
    datasets_raw = data.get("datasets", [])
    if not isinstance(datasets_raw, list):
        raise ValueError("datasets must be a list.")

    datasets: list[DatasetEntry] = []
    seen_ids: set[str] = set()
    for entry in datasets_raw:
        if not isinstance(entry, dict):
            raise ValueError("Each dataset entry must be a mapping.")
        dataset_id = entry.get("id")
        name = entry.get("name", dataset_id)
        urls = entry.get("urls", [])
        if not isinstance(dataset_id, str) or not dataset_id:
            raise ValueError("Each dataset must have a non-empty string id.")
        if dataset_id in seen_ids:
            raise ValueError(f"Duplicate dataset id: {dataset_id}")
        if not isinstance(name, str) or not name:
            raise ValueError(f"Dataset {dataset_id} name must be a non-empty string.")
        if not isinstance(urls, list):
            raise ValueError(f"Dataset {dataset_id} urls must be a list.")
        validated_urls = _validate_urls(urls, allowed_domains)
        datasets.append(
            DatasetEntry(
                dataset_id=dataset_id,
                name=name,
                urls=validated_urls,
            )
        )
        seen_ids.add(dataset_id)

    return Registry(allowed_domains=allowed_domains, datasets=tuple(datasets))
