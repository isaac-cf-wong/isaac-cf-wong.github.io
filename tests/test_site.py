"""Smoke tests for content validation and site rendering."""

from __future__ import annotations

from pathlib import Path

import pytest

from isaac_cf_wong.site import SitePaths, build_site, load_content, validate_content
from isaac_cf_wong.site.builder import _resolve_project_publications

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
    """Every page declared in the profile config is written to its own URL."""
    output = Path(tmp_path) / "_site"
    paths = SitePaths(root=ROOT, output_dir=str(output))
    result = build_site(paths)

    slugs = [page["slug"] for page in load_content(paths.content)["profile"]["site"]["pages"]]
    assert slugs, "no pages configured"
    for slug in slugs:
        expected = result / "index.html" if not slug else result / slug / "index.html"
        assert expected.exists(), f"missing page for slug '{slug}'"


def test_resolve_project_publications_attaches_records() -> None:
    """A project's publication keys resolve to the full publication records, in order."""
    pubs = {"k1": {"title": "Paper One", "key": "k1"}, "k2": {"title": "Paper Two", "key": "k2"}}
    projects = [{"name": "P", "publications": ["k2", "k1"]}]

    resolved = _resolve_project_publications(projects, pubs)

    assert resolved[0]["related_publications"] == [pubs["k2"], pubs["k1"]]


def test_resolve_project_publications_defaults_to_empty() -> None:
    """A project with no publications gets an empty related list (section stays hidden)."""
    resolved = _resolve_project_publications([{"name": "P"}], {})
    assert resolved[0]["related_publications"] == []


def test_resolve_project_publications_rejects_unknown_key() -> None:
    """Referencing a non-existent publication key fails the build with a clear error."""
    with pytest.raises(ValueError, match="unknown publication key"):
        _resolve_project_publications([{"name": "P", "publications": ["missing"]}], {})


def test_resolve_topic_publications_attaches_records() -> None:
    """A sub-topic's publication keys resolve to records, alongside project-level ones."""
    pubs = {"k1": {"title": "One", "key": "k1"}, "k2": {"title": "Two", "key": "k2"}}
    projects = [
        {
            "name": "Broad theme",
            "publications": ["k1"],
            "topics": [{"name": "Sub-thread", "publications": ["k2"]}],
        }
    ]

    resolved = _resolve_project_publications(projects, pubs)

    assert resolved[0]["related_publications"] == [pubs["k1"]]
    assert resolved[0]["topics"][0]["related_publications"] == [pubs["k2"]]


def test_resolve_topic_publications_rejects_unknown_key() -> None:
    """An unknown key inside a topic fails the build and names the offending topic."""
    with pytest.raises(ValueError, match=r"topic 'T'.*unknown publication key"):
        _resolve_project_publications([{"name": "P", "topics": [{"name": "T", "publications": ["missing"]}]}], {})
