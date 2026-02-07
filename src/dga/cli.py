from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import typer

from dga.ingest import append_manifest, download_file, load_registry, read_manifest, seen_url

app = typer.Typer(help="Document-Grounded Archives (DGA) CLI")

@app.command()
def ingest(
    dataset: str | None = typer.Option(
        None, "--dataset", help="Dataset id to ingest."
    ),
    all_: bool = typer.Option(False, "--all", help="Ingest all datasets."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print planned actions only."),
    max_files: int | None = typer.Option(
        None, "--max-files", min=1, help="Maximum number of files to download."
    ),
):
    """Download datasets from the registry."""
    if not dataset and not all_:
        raise typer.BadParameter("Provide --dataset or --all.")

    registry = load_registry()
    if all_:
        selected = list(registry.datasets)
    else:
        entry = registry.by_id(dataset or "")
        if entry is None:
            raise typer.BadParameter(f"Unknown dataset id: {dataset}")
        selected = [entry]

    manifest_records = read_manifest()
    planned = []
    total = 0
    for entry in selected:
        for url in entry.urls:
            if max_files is not None and total >= max_files:
                break
            if seen_url(url, manifest_records):
                typer.echo(f"Skipping already ingested URL: {url}")
                continue
            filename = Path(urlparse(url).path).name
            dest_dir = Path("data/raw") / entry.dataset_id
            dest_path = dest_dir / filename
            planned.append((entry, url, dest_dir, dest_path))
            total += 1
        if max_files is not None and total >= max_files:
            break

    if dry_run:
        for entry, url, _, dest_path in planned:
            typer.echo(f"[dry-run] {entry.dataset_id}: {url} -> {dest_path}")
        return

    for entry, url, dest_dir, _ in planned:
        metadata = download_file(url, dest_dir)
        record = {
            "dataset_id": entry.dataset_id,
            "dataset_name": entry.name,
            "url": url,
            "path": metadata["path"],
            "sha256": metadata["sha256"],
            "bytes": metadata["bytes"],
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }
        append_manifest(record)

@app.command()
def process():
    """Page-level extract + OCR (stub)."""
    typer.echo("process: not implemented yet")

@app.command()
def index():
    """Chunk + embed + FAISS index (stub)."""
    typer.echo("index: not implemented yet")

@app.command()
def search():
    """Keyword + semantic search (stub)."""
    typer.echo("search: not implemented yet")
