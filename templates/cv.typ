{#- Curriculum vitae, rendered from content/*.yaml to Typst and compiled to
    /assets/cv.pdf at build time (src/isaac_cf_wong/site/cv.py).
    Content strings are inserted with the typst_string and typst_inline
    filters, never as raw markup. -#}
{% from "partials/icons.html" import icon_path %}
#let accent = rgb("#1f3a5f")
#set document(title: {{ ("Curriculum vitae: " ~ profile.name) | typst_string }}, author: {{ profile.name | typst_string }})
#set page(
  paper: "a4",
  margin: (x: 2cm, top: 1.8cm, bottom: 2cm),
  footer: context [
    #set text(size: 8pt, fill: luma(110))
    #{{ ("Updated " ~ cv_updated) | typst_string }}
    #h(1fr)
    #counter(page).display("1 / 1", both: true)
  ],
)
#set text(size: 10pt, lang: "en")
#set par(justify: false, leading: 0.55em)
#show link: set text(fill: accent)

// A 24x24 icon from the site's icon set, drawn inline at text height.
#let icon(d) = box(baseline: 12%, image(
  bytes("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path fill='" + accent.to-hex() + "' d='" + d + "'/></svg>"),
  format: "svg",
  height: 0.95em,
))

#let section(title) = {
  v(0.9em)
  block(below: 0.5em, sticky: true)[
    #text(size: 11.5pt, weight: "bold", fill: accent, title)
    #v(-0.65em)
    #line(length: 100%, stroke: 0.5pt + accent)
  ]
}
#let entry(heading, period, detail: none, body: none) = block(below: 0.85em, breakable: false)[
  #set block(spacing: 0.3em)
  #set par(spacing: 0.3em)
  #grid(columns: (1fr, auto), column-gutter: 1em, heading, text(fill: luma(90), period))
  #if detail != none { text(fill: luma(70), detail) }
  #if body != none { body }
]

#align(center)[
  #text(size: 20pt, weight: "bold", {{ profile.name | typst_string }}) \
  #v(0.15em)
  #text(size: 10.5pt)[#{{ profile.title | typst_string }} · #{{ profile.affiliation | typst_string }}{% if profile.location %} · #{{ profile.location | typst_string }}{% endif %}] \
  #v(0.1em)
  #text(size: 9pt)[
{% set links = [] %}
{% for link in profile.social or [] %}
{% if link.url and link.icon != "cv" %}
{% set _ = links.append(link) %}
{% endif %}
{% endfor %}
{% for link in links %}
    #icon({{ icon_path(link.icon) | typst_string }})#h(0.25em)#link({{ link.url | typst_string }})[#{{ (link.url[7:] if link.icon == "email" else link.label) | typst_string }}]{% if not loop.last %}#h(0.9em){% endif %}

{% endfor %}
{% if site.url %}
    #h(0.9em)#icon({{ icon_path("home") | typst_string }})#h(0.25em)#link({{ site.url | typst_string }})[#{{ site.url.replace("https://", "").rstrip("/") | typst_string }}]
{% endif %}
  ]
]
{% if profile.research_interests %}

#section("Research interests")
{% for interest in profile.research_interests %}#{{ interest | typst_string }}{% if not loop.last %} · {% endif %}{% endfor %}

{% endif %}
{% if experience %}

#section("Positions")
{% for item in experience %}
#entry(
  [*#{{ item.role | typst_string }}*, #{{ item.organization | typst_string }}{% if item.location %}, #{{ item.location | typst_string }}{% endif %}],
  {{ (item.start ~ " – " ~ item.end) | typst_string }},
  body: [
{% if item.summary %}    {{ item.summary | typst_inline }}
{% endif %}
{% for highlight in item.highlights or [] %}
    - {{ highlight | typst_inline }}
{% endfor %}
  ],
)
{% endfor %}
{% endif %}
{% if education %}

#section("Education")
{% for item in education %}
#entry(
  [*#{{ item.degree | typst_string }}*, #{{ item.institution | typst_string }}{% if item.location %}, #{{ item.location | typst_string }}{% endif %}],
  {{ (item.start ~ " – " ~ item.end) | typst_string }},
{% if item.thesis or item.supervisor %}
  body: [{% if item.thesis %}Thesis: #emph({{ item.thesis | typst_string }}){% endif %}{% if item.thesis and item.supervisor %} \ {% endif %}{% if item.supervisor %}Supervisor: #{{ item.supervisor | typst_string }}{% endif %}],
{% endif %}
)
{% endfor %}
{% endif %}
{% macro publication_list(items) %}
#enum(
  numbering: n => [[#n]],
{% for pub in items %}
  [{% for author in pub.authors %}{{ author | typst_inline }}{% if not loop.last %}, {% endif %}{% endfor %}. #{{ pub.title | typst_string }}. #emph({{ (pub.venue or "") | typst_string }}){% if pub.doi %}, #link({{ ("https://doi.org/" ~ pub.doi) | typst_string }})[#{{ ("doi:" ~ pub.doi) | typst_string }}]{% endif %}{% if pub.arxiv and pub.venue and "arXiv" not in pub.venue %}, #link({{ ("https://arxiv.org/abs/" ~ pub.arxiv) | typst_string }})[#{{ ("arXiv:" ~ pub.arxiv) | typst_string }}]{% endif %}.],
{% endfor %}
)
{% endmacro %}
{% if cv_journal_articles or cv_preprints or cv_collaboration_papers %}

#section("Publications")
{% if cv_journal_articles %}
#text(weight: "bold")[Journal articles]
{{ publication_list(cv_journal_articles) }}
{% endif %}
{% if cv_preprints %}
#text(weight: "bold")[Preprints]
{{ publication_list(cv_preprints) }}
{% endif %}
{% if cv_collaboration_papers %}
#text(weight: "bold")[Collaboration papers]
{{ publication_list(cv_collaboration_papers) }}
{% endif %}
{% endif %}
{% if supervision %}

#section("Supervision and mentoring")
{% for item in supervision %}
#entry(
  [*#{{ item.name | typst_string }}*{% if item.topic %}: #{{ item.topic | typst_string }}{% endif %}],
  {{ (item.start ~ ((" – " ~ item.end) if item.end else "")) | typst_string }},
  detail: [#{{ (item.role ~ ", " ~ item.level ~ ", " ~ item.institution ~ ((". " ~ item.note) if item.note else "")) | typst_string }}],
)
{% endfor %}
{% endif %}
{% if software %}

#section("Software")
{% for group in software %}
#text(weight: "bold")[#{{ (group.category[:1] | upper ~ group.category[1:]) | typst_string }}]
{% for item in group["items"] %}
- {% if item.links %}#link({{ item.links[0].url | typst_string }})[*#{{ item.name | typst_string }}*]{% else %}*#{{ item.name | typst_string }}*{% endif %}{% if item.role %} (#{{ item.role | typst_string }}){% endif %}{% if item.summary %}: {{ item.summary | typst_inline }}{% endif %}{{ "" }}
{% endfor %}

{% endfor %}
{% endif %}
{% if presentations %}

#section("Talks and workshops")
{% for item in presentations %}
#entry(
  [{% if item.url %}#link({{ item.url | typst_string }})[#{{ item.title | typst_string }}]{% else %}#{{ item.title | typst_string }}{% endif %}],
  {{ item.date[:7] | typst_string }},
  detail: [#{{ ((item.kind | capitalize) ~ ", " ~ item.event ~ ((", " ~ item.location) if item.location else "")) | typst_string }}],
)
{% endfor %}
{% endif %}
{% if service %}

#section("Service and collaborations")
{% for group in service %}
#text(weight: "bold")[#{{ group.category | typst_string }}]
{% for item in group["items"] %}
#entry(
  [{% if item.url %}#link({{ item.url | typst_string }})[#{{ item.title | typst_string }}]{% else %}#{{ item.title | typst_string }}{% endif %}],
  {{ ((item.start ~ ((" – " ~ item.end) if item.end else "")) if item.start else "") | typst_string }},
{% if item.detail %}  detail: [{{ item.detail | typst_inline }}],
{% endif %}
)
{% endfor %}
{% endfor %}
{% endif %}
{% if teaching %}

#section("Teaching")
{% for item in teaching %}
#entry(
  [*#{{ item.course | typst_string }}*, #{{ item.institution | typst_string }}],
  {{ item.term | typst_string }},
  detail: [#{{ item.role | typst_string }}],
)
{% endfor %}
{% endif %}
{% if awards %}

#section("Awards")
{% for item in awards %}
#entry(
  [*#{{ item.title | typst_string }}*, #{{ item.issuer | typst_string }}],
  {{ item.year | string | typst_string }},
{% if item.note %}  body: [{{ item.note | typst_inline }}],
{% endif %}
)
{% endfor %}
{% endif %}
