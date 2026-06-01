# Personal website

[![codecov](https://codecov.io/gh/isaac-cf-wong/isaac-cf-wong.github.io/graph/badge.svg?token=N4V94JF8FC)](https://codecov.io/gh/isaac-cf-wong/isaac-cf-wong.github.io)

A content-driven personal academic website. All information lives in plain,
structured files; the site is rendered from them. To update the site, you edit
data — not HTML.

## How it is organised

| Path                 | What it holds                                                                                                         |
| -------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `content/`           | The single source of truth. One YAML file per kind of information.                                                    |
| `schemas/`           | A JSON Schema for each content file, defining its allowed structure.                                                  |
| `templates/`         | Jinja2 templates: a shared layout, the page shell, and one partial per section (`templates/partials/section_*.html`). |
| `assets/`            | CSS, JavaScript, images, and files (e.g. the CV) served as-is.                                                        |
| `src/isaac_cf_wong/` | The small generator and command-line interface.                                                                       |
| `_site/`             | The rendered output (generated; not committed).                                                                       |

The rule of thumb: **facts go in `content/`, appearance goes in `templates/` and
`assets/`.** You can update everything on the site by editing `content/` alone.

## Pages

The site is split across separate pages, each at its own clean URL (`/`,
`/publications/`, `/cv/`, …). Pages are defined as data under `site.pages` in
`content/profile.yaml`: every entry has a `slug` (the URL), a `label` (its name
in the navigation), and a `sections` list naming the content blocks shown on
that page, top to bottom. A block may be written as `{name: news, preview: 3}`
to show only the most recent items with a link through to its full page.

To add, remove, reorder, or regroup pages — or to move a section from one page
to another — edit `site.pages`. No template changes are needed; a block name
maps to `templates/partials/section_<name>.html`.

## Content files

Each file under `content/` is a YAML document validated against the matching
`schemas/<name>.schema.json`. Every file begins with comments explaining its
fields.

| File                        | Contents                                                                                               |
| --------------------------- | ------------------------------------------------------------------------------------------------------ |
| `content/profile.yaml`      | Identity, contact, social links, bio, and site-wide settings (title, navigation, which sections show). |
| `content/news.yaml`         | Dated news/announcement items.                                                                         |
| `content/publications.yaml` | Publications, grouped by year; mark selected work with `highlight: true`.                              |
| `content/experience.yaml`   | Professional and research positions.                                                                   |
| `content/education.yaml`    | Degrees.                                                                                               |
| `content/projects.yaml`     | Research projects and software.                                                                        |
| `content/teaching.yaml`     | Courses taught.                                                                                        |
| `content/awards.yaml`       | Awards, honours, grants.                                                                               |
| `content/talks.yaml`        | Invited talks and presentations.                                                                       |

### Editing rules

- Keep the existing keys and nesting; change the values.
- Markdown is supported in `profile.bio`, `news[].body`, and author names (wrap
  your own name in `**double asterisks**` to emphasise it).
- Dates are ISO format (`YYYY-MM-DD`); years are plain integers.
- To change which pages exist or what each one shows, edit `site.pages` in
  `content/profile.yaml` (see **Pages** above).
- After any edit, run `validate` (below) to confirm the structure is still
  correct.

## Publications sync

`content/publications.yaml` can be kept up to date automatically from
[INSPIRE-HEP](https://inspirehep.net), anchored on your ORCID iD.

```bash
uv run isaac-cf-wong publications sync
```

This resolves your ORCID to your INSPIRE author profile and merges your works
into `publications.yaml`.

**Curation happens by claiming papers on INSPIRE.** By default the sync lists
only papers whose authorship you have _claimed_ (curated) on your INSPIRE
profile — that claim is your "I contributed to this" signal. Claim the
collaboration papers you want shown and leave the rest unclaimed; unclaiming a
paper removes it on the next sync. (Run with `--all` to instead fetch every
paper assigned to your profile, with unclaimed ones written `include: false`.)

The merge is also **curation-preserving** locally:

- Entries are matched by a stable `key` (DOI → arXiv → INSPIRE id). For a match,
  metadata is refreshed but your `include` and `highlight` choices are kept.
- Hand-authored entries (no `key`) are never touched or removed.
- Your name is emphasised in author lists; large-collaboration papers collapse
  to the collaboration name (e.g. “LIGO Scientific Collaboration … (incl. **C.
  F. Wong**)”).

Configure it under `publications_sync` in `content/profile.yaml` (`orcid`,
`author_name`, `claimed_only`).

The `.github/workflows/sync-publications.yml` workflow runs this weekly (and on
demand) and opens a pull request when anything changes, so you review new papers
before they go live.

## Working locally

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync                          # install dependencies

uv run isaac-cf-wong validate    # check content against the schemas
uv run isaac-cf-wong build       # render the site into _site/
uv run isaac-cf-wong serve       # build and preview at http://localhost:8000
```

`build` validates the content first and fails fast if anything is malformed.

## Deployment

Pushing to `main` triggers `.github/workflows/deploy.yml`, which builds the site
and publishes `_site/` to GitHub Pages. Enable Pages once under **Settings →
Pages → Build and deployment → Source: GitHub Actions**.
