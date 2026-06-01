"""Sync the publication list from INSPIRE-HEP, keyed on the author's ORCID iD.

INSPIRE-HEP is used as the metadata source because it has reliable author
lists, arXiv/DOI identifiers, and an explicit notion of *claimed* authorship:
when you claim a paper on your INSPIRE profile the matching author signature is
marked ``curated_relation: true``. That claim is treated as the "I contributed
to this" signal, so claimed papers are listed and auto-assigned ones (homonyms,
unclaimed large-collaboration papers) are not.

The sync is curation-preserving: entries are matched by a stable ``key``
(DOI, then arXiv, then INSPIRE record id). For a matched entry the metadata is
refreshed but the human decisions (``include`` and ``highlight``) are kept.
Hand-authored entries (those without an INSPIRE ``key``) are never modified or
removed.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from isaac_cf_wong.site.content import load_yaml

INSPIRE_LITERATURE_API = "https://inspirehep.net/api/literature"
INSPIRE_AUTHORS_API = "https://inspirehep.net/api/authors"
_REQUEST_FIELDS = (
    "titles,authors.full_name,authors.ids,authors.curated_relation,author_count,"
    "collaborations,dois,arxiv_eprints,publication_info,document_type,"
    "earliest_date,preprint_date,control_number,citation_count"
)
_PAGE_SIZE = 250
_USER_AGENT = "isaac-cf-wong.github.io publication sync (+https://isaac-cf-wong.github.io)"

_DOCUMENT_TYPE_MAP = {
    "article": "journal",
    "conference paper": "conference",
    "proceedings": "conference",
    "thesis": "thesis",
    "book": "book",
    "book chapter": "chapter",
}

_HEADER = """\
# Publications. Entries with an INSPIRE `key` are managed by
# `isaac-cf-wong publications sync`; hand-authored entries (no `key`,
# `source: manual`) are preserved untouched by the sync.
#
# By default the sync lists only papers you have claimed on your INSPIRE author
# profile (`claimed: true`). Claim a paper on INSPIRE to add it here; unclaim it
# to remove it on the next sync.
#
# Curation (preserved across syncs):
#   include:   set false to hide a listed paper from the site.
#   highlight: set true to mark selected work (rendered with a star).
#
# To add a paper by hand, add an entry without a `key`; wrap your own name in
# **double asterisks** to emphasise it.
"""

# The order keys are written within each entry, for stable, readable diffs.
_FIELD_ORDER = [
    "include",
    "highlight",
    "title",
    "authors",
    "venue",
    "year",
    "type",
    "doi",
    "arxiv",
    "key",
    "source",
    "claimed",
    "author_count",
    "collaboration",
    "links",
]


@dataclass
class SyncSummary:
    """Outcome of a sync, for reporting to the CLI and the pull request."""

    total_fetched: int = 0
    added: list[str] = field(default_factory=list)
    added_needs_review: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    updated: int = 0

    @property
    def changed(self) -> bool:
        """Whether the merge produced any additions, removals, or updates."""
        return bool(self.added) or bool(self.removed) or self.updated > 0


def _format_name(full_name: str) -> str:
    """Convert an INSPIRE ``"Last, First"`` name to ``"First Last"``."""
    if "," in full_name:
        last, first = full_name.split(",", 1)
        return f"{first.strip()} {last.strip()}".strip()
    return full_name.strip()


def _author_is_self(author: dict[str, Any], his_orcid: str, his_bai: str | None) -> bool:
    """Whether an INSPIRE author entry is the site owner.

    Matched by INSPIRE BAI or ORCID (never by surname), so co-authors who share
    a surname are never emphasised by mistake. The BAI is the primary signal
    because many author entries carry only the BAI, not an ORCID.
    """
    for identifier in author.get("ids", []):
        schema, value = identifier.get("schema"), identifier.get("value")
        if schema == "ORCID" and value == his_orcid:
            return True
        if schema == "INSPIRE BAI" and his_bai and value == his_bai:
            return True
    return False


def _self_author(metadata: dict[str, Any], his_orcid: str, his_bai: str | None) -> dict[str, Any] | None:
    """Return the owner's author entry within a record, if present."""
    for author in metadata.get("authors", []):
        if _author_is_self(author, his_orcid, his_bai):
            return author
    return None


def _is_claimed(metadata: dict[str, Any], his_orcid: str, his_bai: str | None) -> bool:
    """Whether the owner has claimed (curated) their authorship of this record."""
    author = _self_author(metadata, his_orcid, his_bai)
    return bool(author and author.get("curated_relation") is True)


def _build_authors(metadata: dict[str, Any], his_orcid: str, his_bai: str | None, his_display: str) -> list[str]:
    """Build the rendered author list, emphasising the owner's name.

    Returns a list of author strings (the template joins them with commas).
    Collaboration papers collapse to a single entry naming the collaboration(s)
    plus an "incl. <name>" note so the page stays readable.
    """
    collaborations = [c.get("value") for c in metadata.get("collaborations", []) if c.get("value")]
    if collaborations:
        names = ", ".join(collaborations)
        return [f"{names} (incl. **{his_display}**)"]
    rendered = []
    for author in metadata.get("authors", []):
        name = _format_name(author.get("full_name", ""))
        if _author_is_self(author, his_orcid, his_bai):
            name = f"**{name}**"
        rendered.append(name)
    return rendered


def _build_venue(metadata: dict[str, Any], arxiv_id: str | None) -> str:
    """Build a human-readable venue string from publication info or arXiv."""
    for info in metadata.get("publication_info", []):
        journal = info.get("journal_title")
        if journal:
            volume = info.get("journal_volume", "")
            page = info.get("artid") or info.get("page_start", "")
            year = info.get("year", "")
            bits = journal
            if volume:
                bits += f" {volume}"
            if page:
                bits += f", {page}"
            if year:
                bits += f" ({year})"
            return bits
        if info.get("pubinfo_freetext"):
            return str(info["pubinfo_freetext"])
    if arxiv_id:
        return f"arXiv:{arxiv_id}"
    doc_types = metadata.get("document_type", [])
    return doc_types[0].title() if doc_types else "Preprint"


def _publication_type(metadata: dict[str, Any], has_journal: bool, arxiv_id: str | None) -> str:
    """Map INSPIRE document types to the site's publication type enum."""
    for doc_type in metadata.get("document_type", []):
        mapped = _DOCUMENT_TYPE_MAP.get(doc_type)
        if mapped:
            if mapped == "journal" and not has_journal and arxiv_id:
                return "preprint"
            return mapped
    return "preprint" if arxiv_id and not has_journal else "other"


def _year(metadata: dict[str, Any]) -> int | None:
    """Extract a publication year from publication info, then dates."""
    for info in metadata.get("publication_info", []):
        if info.get("year"):
            return int(info["year"])
    for date_field in ("preprint_date", "earliest_date"):
        value = metadata.get(date_field, "")
        if value[:4].isdigit():
            return int(value[:4])
    return None


def normalize_record(
    metadata: dict[str, Any],
    *,
    his_orcid: str,
    his_bai: str | None,
    his_display: str,
) -> dict[str, Any]:
    """Turn one INSPIRE record's ``metadata`` into a publication entry.

    ``include`` defaults to whether the owner has *claimed* this paper on their
    INSPIRE profile (``curated_relation``). Claiming is the explicit "this is my
    contribution" signal, so claimed papers show by default and auto-assigned
    ones (e.g. homonyms, unclaimed large-collaboration papers) are hidden.
    """
    title = metadata.get("titles", [{}])[0].get("title", "Untitled")
    doi = (metadata.get("dois") or [{}])[0].get("value")
    arxiv_id = (metadata.get("arxiv_eprints") or [{}])[0].get("value")
    recid = metadata.get("control_number")

    has_journal = any(info.get("journal_title") for info in metadata.get("publication_info", []))
    author_count = metadata.get("author_count") or len(metadata.get("authors", []))
    claimed = _is_claimed(metadata, his_orcid, his_bai)

    if doi:
        key = f"doi:{doi}"
    elif arxiv_id:
        key = f"arxiv:{arxiv_id}"
    else:
        key = f"inspire:{recid}"

    links = []
    if doi:
        links.append({"label": "DOI", "url": f"https://doi.org/{doi}"})
    if arxiv_id:
        links.append({"label": "arXiv", "url": f"https://arxiv.org/abs/{arxiv_id}"})
    if recid:
        links.append({"label": "INSPIRE", "url": f"https://inspirehep.net/literature/{recid}"})

    entry: dict[str, Any] = {
        "include": claimed,
        "highlight": False,
        "title": title,
        "authors": _build_authors(metadata, his_orcid, his_bai, his_display),
        "venue": _build_venue(metadata, arxiv_id),
        "year": _year(metadata),
        "type": _publication_type(metadata, has_journal, arxiv_id),
        "key": key,
        "source": "inspire",
        "claimed": claimed,
        "author_count": author_count,
        "collaboration": bool(metadata.get("collaborations")),
        "links": links,
    }
    if doi:
        entry["doi"] = doi
    if arxiv_id:
        entry["arxiv"] = arxiv_id
    return entry


def _get_json(url: str, timeout: float) -> dict[str, Any]:
    # URLs are the fixed INSPIRE HTTPS endpoints and their own pagination links.
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.load(response)


def resolve_inspire_bai(orcid: str, *, timeout: float = 30.0) -> str | None:
    """Resolve an ORCID iD to its INSPIRE author identifier (BAI).

    INSPIRE's literature index is not queryable by ORCID directly, so the
    author profile is looked up first and its BAI used to fetch the works.

    Args:
        orcid: The ORCID iD to resolve.
        timeout: Request timeout in seconds.

    Returns:
        The INSPIRE BAI (e.g. ``"Isaac.C.F.Wong.1"``), or ``None`` if no author
        profile is linked to that ORCID.

    """
    query = urllib.parse.urlencode({"q": f"ids.value:{orcid}", "fields": "ids", "size": 1})
    payload = _get_json(f"{INSPIRE_AUTHORS_API}?{query}", timeout)
    for hit in payload.get("hits", {}).get("hits", []):
        for identifier in hit.get("metadata", {}).get("ids", []):
            if identifier.get("schema") == "INSPIRE BAI":
                return identifier.get("value")
    return None


def fetch_records_for_bai(bai: str, *, timeout: float = 30.0) -> list[dict[str, Any]]:
    """Page through all INSPIRE literature records for an author BAI.

    Args:
        bai: The INSPIRE author identifier (e.g. ``"Isaac.C.F.Wong.1"``).
        timeout: Per-request timeout in seconds.

    Returns:
        A list of record ``metadata`` mappings.

    """
    query = urllib.parse.urlencode(
        {"q": f"a {bai}", "fields": _REQUEST_FIELDS, "size": _PAGE_SIZE, "sort": "mostrecent"}
    )
    url: str | None = f"{INSPIRE_LITERATURE_API}?{query}"
    records: list[dict[str, Any]] = []
    while url:
        payload = _get_json(url, timeout)
        for hit in payload.get("hits", {}).get("hits", []):
            if "metadata" in hit:
                records.append(hit["metadata"])
        url = payload.get("links", {}).get("next")
    return records


def _entry_key(entry: dict[str, Any]) -> str | None:
    return entry.get("key")


def merge_items(
    existing: list[dict[str, Any]], fetched: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], SyncSummary]:
    """Merge fetched entries into the existing list, preserving curation.

    Existing entries are matched by ``key``. For a match the metadata is taken
    from the fetched entry while ``include`` and ``highlight`` are carried over.
    Hand-authored entries (no ``key``) are kept as-is. Nothing is deleted.

    Args:
        existing: The current publication entries.
        fetched: Freshly normalized entries from INSPIRE.

    Returns:
        The merged list and a summary of what changed.

    """
    summary = SyncSummary(total_fetched=len(fetched))
    by_key: dict[str, dict[str, Any]] = {k: e for e in existing if (k := _entry_key(e))}
    manual = [e for e in existing if not _entry_key(e)]

    merged_managed: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for entry in fetched:
        key = entry["key"]
        seen_keys.add(key)
        prior = by_key.get(key)
        if prior is None:
            merged_managed.append(entry)
            summary.added.append(entry["title"])
            if not entry["include"]:
                summary.added_needs_review.append(entry["title"])
        else:
            refreshed = dict(entry)
            refreshed["include"] = prior.get("include", entry["include"])
            refreshed["highlight"] = prior.get("highlight", entry["highlight"])
            if refreshed != prior:
                summary.updated += 1
            merged_managed.append(refreshed)

    # A successful fetch is authoritative: managed entries it no longer returns
    # (e.g. a paper you unclaimed) are dropped. Guard against an empty fetch so a
    # transient outage never wipes the list.
    for key, entry in by_key.items():
        if key in seen_keys:
            continue
        if fetched:
            summary.removed.append(entry.get("title", ""))
        else:
            merged_managed.append(entry)

    merged = manual + merged_managed
    merged.sort(key=lambda e: (e.get("year") or 0, e.get("title", "")), reverse=True)
    return merged, summary


def _ordered(entry: dict[str, Any]) -> dict[str, Any]:
    ordered = {field_name: entry[field_name] for field_name in _FIELD_ORDER if field_name in entry}
    for extra, value in entry.items():  # keep any unexpected/manual fields rather than dropping them
        if extra not in ordered:
            ordered[extra] = value
    return ordered


def write_items(path: Path, items: list[dict[str, Any]]) -> None:
    """Write the publication entries to ``path`` with the documented header."""
    body = yaml.safe_dump(
        {"items": [_ordered(item) for item in items]},
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=120,
    )
    path.write_text(f"{_HEADER}\n{body}", encoding="utf-8")


def sync_publications(  # noqa: PLR0913 - keyword-only config plus injection points for tests
    publications_path: Path,
    *,
    orcid: str,
    author_name: str,
    claimed_only: bool = True,
    bai: str | None = None,
    fetcher: Any = fetch_records_for_bai,
    bai_resolver: Any = resolve_inspire_bai,
) -> SyncSummary:
    """Fetch from INSPIRE, merge into the publications file, and write it back.

    Args:
        publications_path: Path to ``content/publications.yaml``.
        orcid: The ORCID iD, used to resolve the author profile and match the
            owner's signature.
        author_name: How the owner's name should appear (and be emphasised).
        claimed_only: When true, only papers the owner has claimed (curated) on
            their INSPIRE profile are written. When false, all papers assigned to
            the profile are written, with unclaimed ones hidden (``include: false``).
        bai: The INSPIRE BAI; resolved from ``orcid`` when not given.
        fetcher: Callable ``(bai) -> records`` (injectable for tests).
        bai_resolver: Callable ``(orcid) -> bai | None`` (injectable for tests).

    Returns:
        A summary of the changes made.

    Raises:
        LookupError: If no INSPIRE author profile is linked to the ORCID.

    """
    if bai is None:
        bai = bai_resolver(orcid)
    if not bai:
        raise LookupError(
            f"No INSPIRE author profile is linked to ORCID {orcid}. "
            "Claim your papers and add your ORCID on https://inspirehep.net, then retry."
        )

    existing_doc = load_yaml(publications_path) if publications_path.exists() else None
    existing = (existing_doc or {}).get("items") or []

    fetched = [
        normalize_record(metadata, his_orcid=orcid, his_bai=bai, his_display=author_name) for metadata in fetcher(bai)
    ]
    if claimed_only:
        fetched = [entry for entry in fetched if entry["claimed"]]

    merged, summary = merge_items(existing, fetched)
    write_items(publications_path, merged)
    return summary
