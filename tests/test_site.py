"""Smoke tests for content validation and site rendering."""

from __future__ import annotations

from pathlib import Path

import pytest

from isaac_cf_wong.site import SitePaths, build_site, load_content, validate_content

ROOT = Path(__file__).resolve().parents[1]


def test_content_files_are_valid() -> None:
    """Every shipped content file matches its schema."""
    paths = SitePaths(root=ROOT)
    errors = validate_content(paths.content, paths.schemas)
    assert errors == [], "\n".join(errors)


def test_every_content_file_has_a_schema() -> None:
    """Each content file is backed by a JSON Schema so edits can be checked."""
    paths = SitePaths(root=ROOT)
    for name in load_content(paths.content):
        assert (paths.schemas / f"{name}.schema.json").exists(), f"missing schema for {name}.yaml"


def test_build_produces_site(tmp_path: pytest.TempPathFactory) -> None:
    """A build renders the home page, copies assets, and adds the Pages marker."""
    output = Path(tmp_path) / "_site"
    paths = SitePaths(root=ROOT, output_dir=str(output))
    result = build_site(paths)

    index = result / "index.html"
    assert index.exists()
    html = index.read_text(encoding="utf-8")
    assert "<html" in html
    assert (result / "assets" / "css" / "style.css").exists()
    assert (result / ".nojekyll").exists()


def test_build_emits_a_page_per_configured_slug(tmp_path: pytest.TempPathFactory) -> None:
    """Each non-home page is written to its own clean URL directory."""
    output = Path(tmp_path) / "_site"
    paths = SitePaths(root=ROOT, output_dir=str(output))
    result = build_site(paths)

    for slug in ("publications", "cv", "projects", "teaching", "talks", "news", "contact"):
        assert (result / slug / "index.html").exists(), f"missing page for /{slug}/"
