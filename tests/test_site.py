"""Smoke tests for content validation and site rendering."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from isaac_cf_wong.site import SitePaths, build_site, load_content, validate_content
from isaac_cf_wong.site.builder import _feed_entries, _group_software, _resolve_project_publications

ATOM_NS = "{http://www.w3.org/2005/Atom}"

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


def test_group_software_groups_by_category_in_first_seen_order() -> None:
    """Software items group by category, and categories keep first-appearance order."""
    content = {
        "software": {
            "items": [
                {"name": "a", "category": "Packages"},
                {"name": "b", "category": "Templates"},
                {"name": "c", "category": "Packages"},
            ]
        }
    }

    groups = _group_software(content)

    assert [g["category"] for g in groups] == ["Packages", "Templates"]
    assert [i["name"] for i in groups[0]["items"]] == ["a", "c"]
    assert [i["name"] for i in groups[1]["items"]] == ["b"]


def test_group_software_empty_when_null() -> None:
    """A null/absent software list yields no groups (section stays hidden)."""
    assert _group_software({"software": {"items": None}}) == []
    assert _group_software({}) == []


def test_software_schema_supports_optional_license() -> None:
    """The software schema accepts an optional `license` and still rejects typos."""
    paths = SitePaths(root=ROOT)
    schema = json.loads((paths.schemas / "software.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    valid = {"items": [{"name": "x", "category": "packages", "license": "MIT"}]}
    typo = {"items": [{"name": "x", "category": "packages", "licence": "MIT"}]}

    assert list(validator.iter_errors(valid)) == []
    assert list(validator.iter_errors(typo)), "misspelled 'licence' key should be rejected"


def test_feed_entries_combine_sources_newest_first() -> None:
    """News, presentations, and publications combine into one feed, sorted newest-first."""
    context = {
        "site": {"url": "https://example.com"},
        "news": [{"date": "2025-01-01", "body": "Older **news** item"}],
        "presentations": [
            {"kind": "talk", "date": "2026-05-01", "title": "A talk", "event": "Conf", "location": "Leuven"}
        ],
        "publications": [{"title": "Paper", "year": 2024, "authors": ["**Me**", "You"], "venue": "PRD"}],
    }

    entries = _feed_entries(context)

    assert [e["category"] for e in entries] == ["talk", "news", "publication"]
    assert entries[0]["title"] == "A talk"
    # author emphasis markers are stripped from the publication summary
    pub = next(e for e in entries if e["category"] == "publication")
    assert "**" not in pub["content_html"]
    assert "Me" in pub["content_html"]


def test_build_emits_valid_atom_feed(tmp_path: pytest.TempPathFactory) -> None:
    """The build writes a well-formed Atom feed and advertises it for autodiscovery."""
    output = Path(tmp_path) / "_site"
    paths = SitePaths(root=ROOT, output_dir=str(output))
    result = build_site(paths)

    feed = result / "feed.xml"
    assert feed.exists()
    root = ET.parse(feed).getroot()
    assert root.tag == f"{ATOM_NS}feed"
    # publications are real content, so the feed should carry at least one entry
    assert root.findall(f"{ATOM_NS}entry"), "expected at least one feed entry"

    home = (result / "index.html").read_text(encoding="utf-8")
    assert 'type="application/atom+xml"' in home
    assert 'href="/feed.xml"' in home
