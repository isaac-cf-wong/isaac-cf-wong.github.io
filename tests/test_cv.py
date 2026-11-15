"""Tests for the CV PDF rendered from the site content."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import typst

from isaac_cf_wong.site import SitePaths, build_site
from isaac_cf_wong.site.builder import _cv_output_path, _group_by_category, build_context, make_environment
from isaac_cf_wong.site.cv import _cv_context, render_cv_source, typst_inline, typst_string

ROOT = Path(__file__).resolve().parents[1]


def _compile_markup(markup: str) -> bytes:
    """Compile a fragment of Typst markup to PDF bytes."""
    return typst.compile(f"#set page(width: 10cm, height: auto)\n{markup}\n".encode())


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("plain", '"plain"'),
        ('say "hi"', '"say \\"hi\\""'),
        ("back\\slash", '"back\\\\slash"'),
        ("line\n  break", '"line break"'),
        (" kept ", '" kept "'),
        (None, '""'),
    ],
)
def test_typst_string_escapes_and_collapses_whitespace(value: object, expected: str) -> None:
    """Strings become Typst literals: quotes and backslashes escaped, whitespace collapsed."""
    assert typst_string(value) == expected


def test_typst_string_keeps_markup_characters_inert() -> None:
    """Typst markup characters inside content compile as text, not as markup."""
    hostile = 'A #title with $math$, @label, *stars*, [brackets], _under_ and "quotes" \\ end'
    pdf = _compile_markup(f"#{typst_string(hostile)}")
    assert pdf.startswith(b"%PDF")


def test_typst_inline_maps_the_markdown_subset() -> None:
    """Bold, italic and links map to Typst functions; other text stays literal."""
    assert typst_inline("**Bold** and *it* and [site](https://x.org)") == (
        '#strong("Bold")#" and "#emph("it")#" and "#link("https://x.org")[#"site"]'
    )


def test_typst_inline_keeps_the_space_before_bold_text() -> None:
    """A space next to a bold segment is kept (regression: it was stripped)."""
    assert typst_inline("ET (incl. **C. F. Wong**)") == '#"ET (incl. "#strong("C. F. Wong")#")"'


def test_typst_inline_leaves_unpaired_markers_as_text() -> None:
    """A lone asterisk or a multiplication sign is not read as emphasis."""
    assert typst_inline("2 * 3 = 6") == '#"2 * 3 = 6"'


def test_typst_inline_output_compiles() -> None:
    """The converted markup compiles, including escaped characters inside each part."""
    markup = typst_inline('**Isaac "C. F." Wong**, #1 at [home](https://example.org/#a) and *x $ y*')
    assert _compile_markup(markup).startswith(b"%PDF")


def test_cv_context_splits_publications() -> None:
    """Publications are grouped into journal articles, preprints and collaboration papers."""
    context = {
        "publications": [
            {"title": "a", "type": "journal"},
            {"title": "b", "type": "preprint"},
            {"title": "c", "type": "journal", "collaboration": True},
            {"title": "d", "type": "preprint", "collaboration": True},
        ]
    }
    groups = _cv_context(context)
    assert [p["title"] for p in groups["cv_journal_articles"]] == ["a"]
    assert [p["title"] for p in groups["cv_preprints"]] == ["b"]
    assert [p["title"] for p in groups["cv_collaboration_papers"]] == ["c", "d"]


@pytest.mark.parametrize(
    ("link", "expected"),
    [
        ("/assets/cv.pdf", "assets/cv.pdf"),
        ("/files/Wong_CV.pdf", "files/Wong_CV.pdf"),
        ("https://example.org/cv.pdf", None),
        ("", None),
        ("/assets/cv.html", None),
    ],
)
def test_cv_output_path_follows_the_profile_link(tmp_path: Path, link: str, expected: str | None) -> None:
    """The CV is built only for a site-root PDF link, at that path in the output."""
    result = _cv_output_path(tmp_path, {"profile": {"cv": link}})
    assert result == (None if expected is None else tmp_path / expected)


def test_cv_source_names_the_shipped_content() -> None:
    """The rendered source carries the profile name and every included publication title."""
    paths = SitePaths(root=ROOT)
    context = build_context(paths)
    source = render_cv_source(make_environment(paths), context)
    assert typst_string(context["profile"]["name"]) in source
    for publication in context["publications"]:
        assert typst_string(publication["title"]) in source


def test_build_writes_the_cv_pdf(tmp_path: Path) -> None:
    """A site build compiles the CV to the path that profile.cv links to."""
    output = tmp_path / "_site"
    result = build_site(SitePaths(root=ROOT, output_dir=str(output)))
    pdf = (result / "assets" / "cv.pdf").read_bytes()
    assert pdf.startswith(b"%PDF")
    pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf))
    assert pages >= 2, "the CV should span several pages of real content"


def test_group_by_category_keeps_first_seen_order() -> None:
    """Service items are grouped by category in the order categories first appear."""
    items = [
        {"category": "Peer review", "title": "a"},
        {"category": "Collaborations", "title": "b"},
        {"category": "Peer review", "title": "c"},
    ]
    groups = _group_by_category(items)
    assert [g["category"] for g in groups] == ["Peer review", "Collaborations"]
    assert [i["title"] for i in groups[0]["items"]] == ["a", "c"]


def test_cv_page_and_pdf_show_supervision_and_service(tmp_path: Path) -> None:
    """The CV page lists supervised students and service, and the CV source names them too."""
    paths = SitePaths(root=ROOT, output_dir=str(tmp_path / "_site"))
    result = build_site(paths)
    html = (result / "cv" / "index.html").read_text(encoding="utf-8")
    context = build_context(paths)
    source = render_cv_source(make_environment(paths), context)
    assert context["supervision"], "supervision.yaml has no entries"
    assert context["service"], "service.yaml has no entries"
    for item in context["supervision"]:
        assert item["name"] in html
        assert typst_string(item["name"]) in source
    for group in context["service"]:
        assert group["category"] in html
        assert typst_string(group["category"]) in source
