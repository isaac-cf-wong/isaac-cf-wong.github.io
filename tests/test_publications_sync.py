"""Unit tests for the INSPIRE-HEP publication sync (offline)."""

from __future__ import annotations

from pathlib import Path

from isaac_cf_wong.site.content import load_yaml
from isaac_cf_wong.site.publications_sync import (
    merge_items,
    normalize_record,
    sync_publications,
)

ORCID = "0000-0003-2166-0027"
BAI = "Isaac.C.F.Wong.1"

# A claimed (curated_relation true) small-team paper.
SMALL_PAPER = {
    "titles": [{"title": "A null-stream test of gravity"}],
    "authors": [
        {
            "full_name": "Wong, Chun Fung",
            "ids": [{"schema": "ORCID", "value": ORCID}, {"schema": "INSPIRE BAI", "value": BAI}],
            "curated_relation": True,
        },
        {"full_name": "Smith, John"},
    ],
    "author_count": 2,
    "dois": [{"value": "10.1000/xyz"}],
    "arxiv_eprints": [{"value": "2401.00001", "categories": ["gr-qc"]}],
    "publication_info": [{"journal_title": "Phys. Rev. D", "journal_volume": "109", "artid": "123456", "year": 2024}],
    "document_type": ["article"],
    "earliest_date": "2024-01-02",
    "control_number": 2750000,
}

# A claimed large-collaboration paper.
COLLAB_PAPER = {
    "titles": [{"title": "Observation of GW250000"}],
    "collaborations": [{"value": "LIGO Scientific Collaboration"}, {"value": "Virgo Collaboration"}],
    "authors": [
        {"full_name": "Wong, Chun Fung", "ids": [{"schema": "INSPIRE BAI", "value": BAI}], "curated_relation": True}
    ],
    "author_count": 1500,
    "dois": [{"value": "10.1000/abc"}],
    "publication_info": [{"journal_title": "Astrophys. J.", "year": 2025}],
    "document_type": ["article"],
    "earliest_date": "2025-03-03",
    "control_number": 2800000,
}

# An auto-assigned (unclaimed) paper, owner matched only by BAI.
UNCLAIMED_PAPER = {
    "titles": [{"title": "GWTC catalog paper"}],
    "authors": [{"full_name": "Wong, Chun Fung", "ids": [{"schema": "INSPIRE BAI", "value": BAI}]}],
    "author_count": 1800,
    "dois": [{"value": "10.1000/unclaimed"}],
    "publication_info": [{"journal_title": "Phys. Rev. X", "year": 2023}],
    "document_type": ["article"],
    "earliest_date": "2023-06-01",
    "control_number": 2700000,
}


def _normalize(record: dict) -> dict:
    return normalize_record(record, his_orcid=ORCID, his_bai=BAI, his_display="C. F. Wong")


def test_claimed_small_paper_is_included_and_self_emphasised() -> None:
    """A claimed small-team paper is included and the owner's name emphasised."""
    entry = _normalize(SMALL_PAPER)
    assert entry["include"] is True
    assert entry["claimed"] is True
    assert entry["collaboration"] is False
    assert entry["authors"] == ["**Chun Fung Wong**", "John Smith"]
    assert entry["venue"] == "Phys. Rev. D 109, 123456 (2024)"
    assert entry["year"] == 2024
    assert entry["type"] == "journal"
    assert entry["key"] == "doi:10.1000/xyz"
    assert {"label": "DOI", "url": "https://doi.org/10.1000/xyz"} in entry["links"]


def test_claimed_collaboration_paper_is_included() -> None:
    """A claimed collaboration paper is included, collapsed to the collaboration name."""
    entry = _normalize(COLLAB_PAPER)
    assert entry["include"] is True
    assert entry["claimed"] is True
    assert entry["collaboration"] is True
    assert entry["authors"] == ["LIGO Scientific Collaboration, Virgo Collaboration (incl. **C. F. Wong**)"]


def test_unclaimed_paper_is_hidden() -> None:
    """An unclaimed paper (auto-assigned) defaults to hidden."""
    entry = _normalize(UNCLAIMED_PAPER)
    assert entry["claimed"] is False
    assert entry["include"] is False


def test_self_matched_by_bai_when_entry_has_no_orcid() -> None:
    """The owner is emphasised when matched by BAI alone (no ORCID on the entry)."""
    record = {
        "titles": [{"title": "BAI only"}],
        "authors": [
            {
                "full_name": "Wong, Chun Fung",
                "ids": [{"schema": "INSPIRE BAI", "value": BAI}],
                "curated_relation": True,
            },
            {"full_name": "Other, Person"},
        ],
        "author_count": 2,
        "dois": [{"value": "10.1000/bai"}],
        "publication_info": [{"journal_title": "JCAP", "year": 2022}],
        "document_type": ["article"],
        "earliest_date": "2022-01-01",
        "control_number": 2600000,
    }
    entry = _normalize(record)
    assert entry["authors"][0] == "**Chun Fung Wong**"
    assert entry["claimed"] is True


def test_merge_preserves_curation_and_adds_new() -> None:
    """Merge keeps include/highlight and hand-authored entries, and adds new ones."""
    existing = [
        {"title": "Hand-authored", "authors": ["**C. F. Wong**"], "venue": "Thesis", "year": 2020},
        dict(_normalize(SMALL_PAPER), include=False, highlight=True, title="old title"),
    ]
    fetched = [_normalize(SMALL_PAPER), _normalize(COLLAB_PAPER)]

    merged, summary = merge_items(existing, fetched)

    assert any(e.get("title") == "Hand-authored" and "key" not in e for e in merged)
    refreshed = next(e for e in merged if e.get("key") == "doi:10.1000/xyz")
    assert refreshed["include"] is False
    assert refreshed["highlight"] is True
    assert refreshed["title"] == "A null-stream test of gravity"
    assert "Observation of GW250000" in summary.added


def test_sync_claimed_only_filters_unclaimed(tmp_path: Path) -> None:
    """claimed_only=True writes only claimed papers; =False keeps unclaimed ones too."""
    records = [SMALL_PAPER, UNCLAIMED_PAPER]

    target = tmp_path / "claimed.yaml"
    sync_publications(
        target,
        orcid=ORCID,
        author_name="C. F. Wong",
        claimed_only=True,
        bai=BAI,
        fetcher=lambda _bai: records,
    )
    claimed_titles = {item["title"] for item in load_yaml(target)["items"]}
    assert claimed_titles == {"A null-stream test of gravity"}

    target_all = tmp_path / "all.yaml"
    sync_publications(
        target_all,
        orcid=ORCID,
        author_name="C. F. Wong",
        claimed_only=False,
        bai=BAI,
        fetcher=lambda _bai: records,
    )
    all_items = load_yaml(target_all)["items"]
    assert {i["title"] for i in all_items} == {"A null-stream test of gravity", "GWTC catalog paper"}
    unclaimed = next(i for i in all_items if i["title"] == "GWTC catalog paper")
    assert unclaimed["include"] is False
