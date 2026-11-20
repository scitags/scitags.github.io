#!/usr/bin/env python3
"""Build the draft redesign's generated pages.

Writes draft/docs/index.html (from howto.md), draft/docs/collectors.html
(from collectors.md) and draft/events/index.html (from events.json).
draft/index.html and draft/assets/ are edited by hand.

Needs Python-Markdown:  pip install markdown
Run from anywhere:      python3 _draft/build.py

Jekyll skips folders that start with "_", so this folder is not published.
"""
import html
import json
import re
from pathlib import Path

import markdown

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DRAFT = ROOT / "draft"
EDIT_BASE = "https://github.com/scitags/scitags.github.io/blob/main/"

FONTS = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600"
         "&family=JetBrains+Mono:wght@400&family=Space+Grotesk:wght@500;700&display=swap")


def shell(title, rel, current, body, script=""):
    """Wrap a page body in the shared head, banner, header and footer.

    rel is the path from the page back to draft/ (e.g. "../").
    current is "docs" or "events" and marks the active menu item.
    """
    def nav(name, href, label):
        cur = ' aria-current="page"' if name == current else ""
        return f'<a href="{rel}{href}"{cur}>{label}</a>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow">
  <title>{html.escape(title)} · SciTags (draft)</title>
  <link rel="icon" href="{rel}assets/img/favicon.svg" type="image/svg+xml">
  <link rel="icon" href="{rel}assets/img/favicon-32.png" sizes="32x32" type="image/png">
  <link rel="apple-touch-icon" href="{rel}assets/img/apple-touch-icon.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="{FONTS}">
  <link rel="stylesheet" href="{rel}assets/draft.css">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="draft-banner"><div class="wrap"><span>Draft redesign for review, not yet the official site.</span><a href="{rel}../">Go to the current scitags.org</a></div></div>
<header class="site-header light">
  <div class="wrap">
    <a class="brand" href="{rel}"><img src="{rel}assets/img/scitags-logo.svg" alt="SciTags home"></a>
    <nav aria-label="Main">
      {nav("home", "", "Home")}
      {nav("docs", "docs/", "Docs")}
      {nav("events", "events/", "Events")}
      <a class="nav-button" href="https://github.com/scitags">GitHub</a>
    </nav>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer">
  <div class="wrap top">
    <div class="about">
      <img src="{rel}assets/img/scitags-logo-dark.svg" alt="SciTags">
      <p>Scientific Network Tags: identifying science domains and their activities at the network level.</p>
    </div>
    <nav aria-label="Footer">
      <div><p>Project</p><a href="{rel}#how">How it works</a><a href="{rel}events/">Events</a><a href="{rel}events/#pubs">Publications</a></div>
      <div><p>Docs</p><a href="{rel}docs/">Get started</a><a href="{rel}docs/collectors.html">Collectors</a><a href="https://www.scitags.org/api.json">Registry API</a></div>
      <div><p>Community</p><a href="https://github.com/scitags">GitHub</a><a href="https://groups-portal.web.cern.ch/group/net-wg/">Mailing list</a></div>
    </nav>
  </div>
  <div class="wrap bottom">Hosted on GitHub Pages</div>
</footer>
{script}</body>
</html>
"""


# ---------------------------------------------------------------- docs

DOCS = [
    # (source markdown, output file, page title, heading levels in the side menu)
    ("howto.md", "index.html", "Get started", (3,)),
    ("collectors.md", "collectors.html", "Firefly collector guide", (2,)),
]


def flatten(tokens):
    for t in tokens:
        yield t
        yield from flatten(t.get("children", []))


def render_md(path):
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists"])
    body = md.convert(path.read_text(encoding="utf-8"))
    body = body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    return body, list(flatten(md.toc_tokens))


def build_docs():
    rendered = []
    for src, out, title, levels in DOCS:
        body, toc = render_md(ROOT / src)
        if not re.search(r"<h1[ >]", body):
            body = f"<h1>{html.escape(title)}</h1>\n" + body
        sections = [t for t in toc if t["level"] in levels]
        rendered.append((src, out, title, body, sections))

    for src, out, title, body, _ in rendered:
        menu = []
        for s2, o2, t2, _, secs in rendered:
            cur = ' aria-current="page"' if o2 == out else ""
            href = "./" if o2 == "index.html" else o2
            sub = ""
            if o2 == out and secs:
                items = "".join(f'<li><a href="#{s["id"]}">{html.escape(s["name"])}</a></li>' for s in secs)
                sub = f"<ul>{items}</ul>"
            menu.append(f'<li><a href="{href}"{cur}>{html.escape(t2)}</a>{sub}</li>')
        page = f"""<div class="wrap docs">
  <nav class="docs-nav" aria-label="Docs">
    <div>
      <p class="group-title">Guides</p>
      <ul>{''.join(menu)}</ul>
    </div>
    <div>
      <p class="group-title">Reference</p>
      <ul>
        <li><a href="https://www.scitags.org/api.json">Registry (api.json)</a></li>
        <li><a href="{EDIT_BASE}schemas/v1.0.0/firefly.schema.json">Firefly schema v1.0.0</a></li>
        <li><a href="{EDIT_BASE}schemas/v1.0.0/registry.schema.json">Registry schema v1.0.0</a></li>
        <li><a href="https://datatracker.ietf.org/doc/draft-cc-v6ops-wlcg-flow-label-marking/">IPv6 flow label draft</a></li>
      </ul>
    </div>
  </nav>
  <article class="docs-main">
    <p class="crumbs">Docs / {html.escape(title)}</p>
    <div class="prose">
{body}
    </div>
    <div class="docs-foot">
      <a href="{EDIT_BASE}{src}">Edit this page on GitHub</a>
      <span>Generated from {html.escape(src)}</span>
    </div>
  </article>
</div>"""
        dest = DRAFT / "docs" / out
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(shell(title, "../", "docs", page), encoding="utf-8")
        print("wrote", dest.relative_to(ROOT))


# ---------------------------------------------------------------- events

PUBS = [
    ("https://www.scitags.org/assets/img/CHEP_2025.pdf", "CHEP 2025 · EPJ Web of Conferences",
     "Scitags: A Standardized Framework for Traffic Identification and Network Visibility in Data-Intensive Research Infrastructures", "PDF"),
    ("https://www.scitags.org/assets/img/chep_paper23.pdf", "CHEP 2023 · EPJ Web of Conferences",
     "Identifying and Understanding Scientific Network Flows", "PDF"),
    ("https://datatracker.ietf.org/doc/draft-cc-v6ops-wlcg-flow-label-marking/", "IETF Internet-Draft",
     "Use of the IPv6 Flow Label for WLCG Packet Marking", "Datatracker"),
]

FILTER_JS = """<script>
(function () {
  var buttons = document.querySelectorAll('.filters button');
  var years = document.querySelectorAll('.year');
  buttons.forEach(function (b) {
    b.addEventListener('click', function () {
      var pick = b.getAttribute('data-year');
      buttons.forEach(function (o) { o.setAttribute('aria-pressed', String(o === b)); });
      years.forEach(function (y) { y.hidden = !(pick === 'all' || y.getAttribute('data-year') === pick); });
    });
  });
})();
</script>
"""


def build_events():
    events = json.loads((HERE / "events.json").read_text(encoding="utf-8"))
    years = []
    for e in events:
        if e["year"] not in years:
            years.append(e["year"])
    esc = html.escape
    pubs = "".join(
        f'<a class="pub" href="{esc(u)}"><span class="venue">{esc(v)}</span>'
        f'<span class="title">{esc(t)}</span><span class="note">{esc(k)}</span></a>'
        for u, v, t, k in PUBS)
    filters = '<button type="button" data-year="all" aria-pressed="true">All years</button>' + "".join(
        f'<button type="button" data-year="{y}" aria-pressed="false">{y}</button>' for y in years)
    blocks = []
    for y in years:
        evs = [e for e in events if e["year"] == y]
        items = []
        for e in evs:
            what = (f'<a href="{esc(e["url"])}">{esc(e["title"])}</a>' if e.get("url") else esc(e["title"]))
            extras = "".join(f' <a class="extra" href="{esc(x["url"])}">{esc(x["label"])}</a>'
                             for x in e.get("extras", []))
            items.append(f'<li><span class="when">{esc(e["month"])}</span><span class="what">{what}</span>{extras}</li>')
        n = len(evs)
        blocks.append(f'<div class="year" data-year="{y}"><div class="year-label"><strong>{y}</strong>'
                      f'<span>{n} event{"s" if n != 1 else ""}</span></div>'
                      f'<ul class="event-list">{"".join(items)}</ul></div>')
    body = f"""<div class="wrap section first last">
  <div class="page-head">
    <h1>Events and publications</h1>
    <p>Papers, the IETF draft, and every talk and demo since {years[-1]}.</p>
  </div>
  <section aria-labelledby="pubs" class="group">
    <h2 id="pubs" class="small">Publications</h2>
    <div class="pubs row">{pubs}</div>
  </section>
  <section aria-labelledby="talks" class="group">
    <div class="links" style="justify-content: space-between; align-items: center">
      <h2 id="talks" class="small">Talks and demos</h2>
      <div class="filters" role="group" aria-label="Filter by year">{filters}</div>
    </div>
    <div>{"".join(blocks)}</div>
  </section>
</div>"""
    dest = DRAFT / "events" / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(shell("Events and publications", "../", "events", body, FILTER_JS), encoding="utf-8")
    print("wrote", dest.relative_to(ROOT), f"({len(events)} events)")


if __name__ == "__main__":
    build_docs()
    build_events()
