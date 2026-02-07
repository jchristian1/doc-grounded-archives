import typer

app = typer.Typer(help="Document-Grounded Archives (DGA) CLI")

@app.command()
def ingest():
    """Download datasets from the registry (stub)."""
    typer.echo("ingest: not implemented yet")

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
