"""Rendering of the CV as a PDF from the same content as the site.

The CV is a Jinja2 template (``templates/cv.typ``) that writes Typst source,
compiled to PDF with the ``typst`` package. Content strings never enter the
Typst source as markup: they are emitted as Typst string literals, so a
character such as ``#``, ``*``, ``$`` or ``@`` in a title cannot change the
layout. The small Markdown subset used in the content files (``**bold**``,
``*italic*`` and ``[text](url)``) is mapped to the matching Typst functions.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

import typst
from jinja2 import Environment

CV_TEMPLATE = "cv.typ"

_WHITESPACE = re.compile(r"\s+")

_INLINE = re.compile(
    r"\*\*(?P<bold>.+?)\*\*"
    r"|\[(?P<link_text>[^\]]+)\]\((?P<link_url>[^)\s]+)\)"
    r"|(?<![\w*])\*(?P<italic>[^*\s][^*]*?)\*(?![\w*])"
)


def typst_string(value: Any) -> str:
    """Return ``value`` as a Typst string literal, with quotes and backslashes escaped.

    Line breaks and runs of whitespace are collapsed to single spaces, as in
    the rendered site; a leading or trailing space is kept, since the string
    may be one fragment of a longer line.
    """
    text = _WHITESPACE.sub(" ", str(value if value is not None else ""))
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def typst_inline(value: Any) -> str:
    """Convert a short Markdown string to Typst markup built from string literals.

    Supports ``**bold**``, ``*italic*`` and ``[text](url)``; everything else is
    literal text.
    """
    text = _WHITESPACE.sub(" ", str(value if value is not None else "")).strip()
    parts: list[str] = []
    position = 0
    for match in _INLINE.finditer(text):
        if match.start() > position:
            parts.append(f"#{typst_string(text[position : match.start()])}")
        if match.group("bold") is not None:
            parts.append(f"#strong({typst_string(match.group('bold'))})")
        elif match.group("link_url") is not None:
            parts.append(f"#link({typst_string(match.group('link_url'))})[#{typst_string(match.group('link_text'))}]")
        else:
            parts.append(f"#emph({typst_string(match.group('italic'))})")
        position = match.end()
    if position < len(text):
        parts.append(f"#{typst_string(text[position:])}")
    return "".join(parts)


def add_cv_filters(env: Environment) -> None:
    """Register the Typst filters used by the CV template."""
    env.filters["typst_string"] = typst_string
    env.filters["typst_inline"] = typst_inline


def _cv_context(context: dict[str, Any]) -> dict[str, Any]:
    """Split publications into the groups the CV shows, and drop the software groups it collapses."""
    publications = context.get("publications", [])
    individual = [p for p in publications if not p.get("collaboration")]
    software_cv = context.get("software_cv") or {}
    collapsed = set(software_cv.get("collapse") or [])
    return {
        **context,
        "cv_software": [g for g in context.get("software", []) if g["category"] not in collapsed],
        "cv_software_summary": software_cv.get("summary") if collapsed else None,
        "cv_journal_articles": [p for p in individual if p.get("type") != "preprint"],
        "cv_preprints": [p for p in individual if p.get("type") == "preprint"],
        "cv_collaboration_papers": [p for p in publications if p.get("collaboration")],
        "cv_updated": date.today().strftime("%B %Y"),
    }


def render_cv_source(env: Environment, context: dict[str, Any]) -> str:
    """Render the Typst source of the CV from the site context."""
    return env.get_template(CV_TEMPLATE).render(**_cv_context(context))


def build_cv_pdf(env: Environment, context: dict[str, Any], destination: Path) -> Path:
    """Render and compile the CV to ``destination``.

    Args:
        env: The Jinja2 environment holding ``cv.typ``, with the CV filters added.
        context: The site template context.
        destination: Path of the PDF to write.

    Returns:
        The path of the written PDF.

    """
    source = render_cv_source(env, context)
    destination.parent.mkdir(parents=True, exist_ok=True)
    typst.compile(source.encode("utf-8"), output=str(destination))
    return destination
