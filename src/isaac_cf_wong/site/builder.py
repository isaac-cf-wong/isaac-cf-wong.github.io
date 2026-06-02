"""Rendering of the static site from content + templates + assets.

The build is deliberately small and explicit:

1. Load the structured content (``content/*.yaml``).
2. Derive a few sorted/grouped views (news, talks, awards, publications).
3. Render one page per ``site.pages`` entry to ``<slug>/index.html``.
4. Copy ``assets/`` into the output and add a ``.nojekyll`` marker.
"""

from __future__ import annotations

import shutil
from itertools import groupby
from pathlib import Path
from typing import Any

import markdown as markdown_lib
from jinja2 import ChainableUndefined, Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from isaac_cf_wong.site.content import load_content
from isaac_cf_wong.site.paths import SitePaths

_MD_EXTENSIONS = ["extra", "sane_lists", "smarty"]


def _render_markdown(text: str | None) -> Markup:
    """Render a block of Markdown to safe HTML."""
    if not text:
        return Markup("")
    # Content is authored in-repo and therefore trusted; rendering it as HTML is intentional.
    return Markup(markdown_lib.markdown(str(text), extensions=_MD_EXTENSIONS))  # noqa: S704


def _render_markdown_inline(text: str | None) -> Markup:
    """Render Markdown without the wrapping ``<p>`` tag (for inline snippets)."""
    rendered = str(_render_markdown(text)).strip()
    if rendered.startswith("<p>") and rendered.endswith("</p>"):
        rendered = rendered[len("<p>") : -len("</p>")]
    return Markup(rendered)  # noqa: S704


def _make_environment(templates_dir: Path) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        undefined=ChainableUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["markdown"] = _render_markdown
    env.filters["markdown_inline"] = _render_markdown_inline
    return env


def _items(content: dict[str, Any], key: str) -> list[dict[str, Any]]:
    section = content.get(key) or {}
    return list(section.get("items") or [])


def _group_software(content: dict[str, Any]) -> list[dict[str, Any]]:
    """Group software items by ``category``, preserving first-appearance order.

    Returns a list of ``{"category": str, "items": [...]}`` so the template can
    render each category under its own heading.
    """
    groups: list[dict[str, Any]] = []
    index: dict[str, dict[str, Any]] = {}
    for item in _items(content, "software"):
        category = item.get("category", "")
        group = index.get(category)
        if group is None:
            group = {"category": category, "items": []}
            index[category] = group
            groups.append(group)
        group["items"].append(item)
    return groups


def _resolve_publications(
    keys: list[str] | None, pub_by_key: dict[str, dict[str, Any]], *, owner: str
) -> list[dict[str, Any]]:
    """Resolve a list of publication ``key`` values to their full records.

    Raises:
        ValueError: If a key does not match any known publication.

    """
    resolved: list[dict[str, Any]] = []
    for key in keys or []:
        pub = pub_by_key.get(key)
        if pub is None:
            raise ValueError(f"projects.yaml: {owner} references unknown publication key {key!r}")
        resolved.append(pub)
    return resolved


def _resolve_project_publications(
    projects: list[dict[str, Any]], pub_by_key: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Attach resolved publication records to each project and its sub-topics.

    A project (and each of its optional ``topics``) may list publication ``key``
    values under ``publications``; these are resolved to the full records so the
    template can render them grouped together.

    Raises:
        ValueError: If a project or topic references a publication key that does not exist.

    """
    for project in projects:
        name = project.get("name", "?")
        project["related_publications"] = _resolve_publications(
            project.get("publications"), pub_by_key, owner=f"project {name!r}"
        )
        for topic in project.get("topics") or []:
            topic["related_publications"] = _resolve_publications(
                topic.get("publications"),
                pub_by_key,
                owner=f"project {name!r} topic {topic.get('name', '?')!r}",
            )
    return projects


def _normalize_pages(site: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand the ``site.pages`` config into a uniform structure for templates.

    Each section entry becomes ``{"name": str, "preview": int | None}`` whether
    it was authored as a bare string or as a mapping.
    """
    pages: list[dict[str, Any]] = []
    for raw in site.get("pages", []):
        sections = []
        for entry in raw.get("sections", []):
            if isinstance(entry, str):
                sections.append({"name": entry, "preview": None})
            else:
                sections.append({"name": entry["name"], "preview": entry.get("preview")})
        label = raw.get("label", "")
        pages.append(
            {
                "slug": raw.get("slug", ""),
                "label": label,
                "title": raw.get("title") or label,
                "nav": raw.get("nav", True),
                "sections": sections,
            }
        )
    return pages


def _page_path(output: Path, slug: str) -> Path:
    """Resolve the output file for a page slug (clean ``/slug/`` URLs)."""
    return output / "index.html" if not slug else output / slug / "index.html"


def _build_context(content: dict[str, Any]) -> dict[str, Any]:
    """Assemble the template context, including sorted and grouped views."""
    profile_doc = content.get("profile") or {}

    news = sorted(_items(content, "news"), key=lambda item: item.get("date", ""), reverse=True)
    talks = sorted(_items(content, "talks"), key=lambda item: item.get("date", ""), reverse=True)
    awards = sorted(_items(content, "awards"), key=lambda item: item.get("year", 0), reverse=True)

    all_publications = _items(content, "publications")
    pub_by_key = {p["key"]: p for p in all_publications if p.get("key")}
    projects = _resolve_project_publications(_items(content, "projects"), pub_by_key)

    included_publications = [p for p in all_publications if p.get("include", True) is not False]
    publications = sorted(included_publications, key=lambda item: item.get("year", 0), reverse=True)
    publications_by_year = [
        {"year": year, "items": list(group)} for year, group in groupby(publications, key=lambda item: item.get("year"))
    ]
    selected_publications = [item for item in publications if item.get("highlight")]

    return {
        "site": profile_doc.get("site", {}),
        "profile": profile_doc.get("profile", {}),
        "news": news,
        "talks": talks,
        "awards": awards,
        "publications": publications,
        "publications_by_year": publications_by_year,
        "selected_publications": selected_publications,
        "experience": _items(content, "experience"),
        "education": _items(content, "education"),
        "projects": projects,
        "teaching": _items(content, "teaching"),
        "software": _group_software(content),
    }


def build_site(paths: SitePaths) -> Path:
    """Build the site and return the path to the output directory.

    Args:
        paths: Resolved input/output locations for the build.

    Returns:
        The output directory containing the rendered site.

    """
    content = load_content(paths.content)
    context = _build_context(content)

    pages = _normalize_pages(context["site"])
    nav_pages = [page for page in pages if page["nav"]]

    env = _make_environment(paths.templates)
    template = env.get_template("page.html")

    output = paths.output
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    for page in pages:
        html = template.render(page=page, nav_pages=nav_pages, **context)
        destination = _page_path(output, page["slug"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(html, encoding="utf-8")

    if paths.assets.is_dir():
        shutil.copytree(paths.assets, output / paths.assets_dir, dirs_exist_ok=True)

    # Disable GitHub Pages' default Jekyll processing of the pre-built output.
    (output / ".nojekyll").write_text("", encoding="utf-8")

    return output
