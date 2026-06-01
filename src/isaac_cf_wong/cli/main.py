"""Command-line entry point for building and checking the website.

Commands:
    build               Render the site from content into the output directory.
    validate            Check the content files against their JSON Schemas.
    serve               Build, then serve the output locally with live preview.
    publications sync   Refresh the publication list from INSPIRE-HEP.
"""

from __future__ import annotations

import functools
import http.server
import os
import socketserver
from pathlib import Path

import typer

from isaac_cf_wong.site import SitePaths, build_site, validate_content
from isaac_cf_wong.site.content import load_yaml
from isaac_cf_wong.site.publications_sync import sync_publications
from isaac_cf_wong.site.validate import validate_or_raise

app = typer.Typer(
    add_completion=False,
    help="Build and manage the personal website from its content files.",
)
publications_app = typer.Typer(add_completion=False, help="Manage the publication list.")
app.add_typer(publications_app, name="publications")


def _paths(root: Path, output: str) -> SitePaths:
    return SitePaths(root=root.resolve(), output_dir=output)


@app.command()
def validate(
    root: Path = typer.Option(Path.cwd(), help="Project root directory."),
) -> None:
    """Validate the content files against their JSON Schemas."""
    paths = _paths(root, "_site")
    errors = validate_content(paths.content, paths.schemas)
    if errors:
        typer.secho(f"Found {len(errors)} validation error(s):", fg=typer.colors.RED, bold=True)
        for error in errors:
            typer.secho(f"  - {error}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.secho("All content files are valid.", fg=typer.colors.GREEN)


@app.command()
def build(
    root: Path = typer.Option(Path.cwd(), help="Project root directory."),
    output: str = typer.Option("_site", help="Output directory for the built site."),
    skip_validation: bool = typer.Option(False, help="Skip schema validation before building."),
) -> None:
    """Render the site from content into the output directory."""
    paths = _paths(root, output)
    if not skip_validation:
        try:
            validate_or_raise(paths.content, paths.schemas)
        except Exception as exc:
            typer.secho("Content validation failed:", fg=typer.colors.RED, bold=True)
            typer.secho(str(exc), fg=typer.colors.RED)
            raise typer.Exit(code=1) from exc
    out = build_site(paths)
    typer.secho(f"Built site -> {out}", fg=typer.colors.GREEN)


@app.command()
def serve(
    root: Path = typer.Option(Path.cwd(), help="Project root directory."),
    output: str = typer.Option("_site", help="Output directory for the built site."),
    port: int = typer.Option(8000, help="Port to serve on."),
) -> None:
    """Build the site and serve it locally for preview."""
    paths = _paths(root, output)
    out = build_site(paths)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out))
    os.chdir(out)
    with socketserver.TCPServer(("", port), handler) as httpd:
        typer.secho(f"Serving {out} at http://localhost:{port} (Ctrl+C to stop)", fg=typer.colors.GREEN)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            typer.secho("\nStopped.", fg=typer.colors.YELLOW)


@publications_app.command("sync")
def publications_sync_command(
    root: Path = typer.Option(Path.cwd(), help="Project root directory."),
    orcid: str = typer.Option(None, help="ORCID iD to query (defaults to profile.yaml)."),
    author_name: str = typer.Option(None, help="How your name should appear, bolded, in author lists."),
    claimed_only: bool = typer.Option(
        None,
        "--claimed-only/--all",
        help="Only papers you've claimed on INSPIRE (default), or all assigned to your profile.",
    ),
) -> None:
    """Refresh the publication list from INSPIRE-HEP, keyed on your ORCID iD."""
    paths = _paths(root, "_site")
    config = (load_yaml(paths.content / "profile.yaml") or {}).get("publications_sync", {})
    orcid = orcid or config.get("orcid")
    author_name = author_name or config.get("author_name", "")
    if claimed_only is None:
        claimed_only = config.get("claimed_only", True)
    if not orcid:
        typer.secho(
            "No ORCID iD: pass --orcid or set publications_sync.orcid in content/profile.yaml.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    try:
        summary = sync_publications(
            paths.content / "publications.yaml",
            orcid=orcid,
            author_name=author_name,
            claimed_only=claimed_only,
        )
    except Exception as exc:
        typer.secho(f"Publication sync failed: {exc}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(code=1) from exc

    typer.secho(
        f"Synced from INSPIRE: {len(summary.added)} added "
        f"({len(summary.added_needs_review)} need review), {summary.updated} updated, "
        f"{len(summary.removed)} removed.",
        fg=typer.colors.GREEN,
    )
    for title in summary.added_needs_review:
        typer.secho(f"  needs review (include: false): {title}", fg=typer.colors.YELLOW)


if __name__ == "__main__":
    app()
