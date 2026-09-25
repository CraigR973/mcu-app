"""The dry run's report, for Craig to read before anything is written — Batch T9.

One self-contained HTML page that reads on a phone: the counts, every film that would merge
into one the collection already has, a sample of each outcome with its evidence, and every
film in full below that.
"""

from __future__ import annotations

import html
from collections.abc import Callable, Sequence
from datetime import datetime

from src.services.identify.plan import Item, Offered, Plan

#: Films shown in each sample before the full lists.
SAMPLE = 12

_STYLE = """
:root { --bg:#fbfaf7; --fg:#1d1b18; --muted:#6b645a; --line:#e4dfd6; --card:#ffffff;
  --accent:#8a5a14; --ok:#2f6b3a; --warn:#8a5a14; --tv:#4b5d7a; }
@media (prefers-color-scheme: dark) { :root { --bg:#161412; --fg:#ede8df; --muted:#a39b8e;
  --line:#2f2b26; --card:#1f1c19; --accent:#e0b060; --ok:#7fc28c; --warn:#e0b060;
  --tv:#9fb3d6; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font:15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
main { max-width:760px; margin:0 auto; padding:20px 16px 48px; }
h1 { font-size:22px; line-height:1.25; margin:0 0 4px; }
h2 { font-size:17px; margin:28px 0 8px; }
p { margin:6px 0; }
.muted { color:var(--muted); font-size:13px; }
.counts { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:8px;
  margin:14px 0; }
.count { background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:10px 12px; }
.count b { display:block; font-size:24px; }
.film { background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:10px 12px; margin:8px 0; }
.film h3 { font-size:15px; margin:0; }
.arrow { color:var(--muted); }
.tag { display:inline-block; font-size:11px; font-weight:600; letter-spacing:.02em;
  border-radius:999px; padding:1px 8px; margin-left:6px; border:1px solid currentColor; }
.ok { color:var(--ok); } .warn { color:var(--warn); } .tv { color:var(--tv); }
ul { margin:6px 0 0; padding-left:18px; }
li { margin:2px 0; }
details { margin:10px 0; }
summary { cursor:pointer; font-weight:600; }
.both { display:grid; grid-template-columns:1fr; gap:6px; margin-top:6px; }
.side { border-left:3px solid var(--line); padding-left:8px; }
"""


def _e(text: object) -> str:
    return html.escape(str(text), quote=True)


def _film_label(offered: Offered | None) -> str:
    if offered is None:
        return "—"
    year = f" ({offered.year})" if offered.year else ""
    return f"{_e(offered.title)}{year}"


def _discs(item: Item) -> str:
    labels = [disc.label() for disc in item.discs]
    watched = f" · watched {item.watches}×" if item.watches else ""
    return _e("; ".join(labels)) + _e(watched)


def _identify(item: Item) -> str:
    evidence = "".join(f"<li>{_e(line)}</li>" for line in item.evidence)
    return (
        f'<div class="film"><h3>{_e(item.title)} <span class="arrow">→</span> '
        f'{_film_label(item.chosen)}<span class="tag ok">identified</span></h3>'
        f'<p class="muted">{_discs(item)}</p><ul>{evidence}</ul></div>'
    )


def _offered_line(offered: Offered) -> str:
    notes = f" — {_e('; '.join(offered.notes))}" if offered.notes else ""
    return f"<li>{_film_label(offered)}{notes}</li>"


def _ask(item: Item) -> str:
    offered = "".join(_offered_line(c) for c in item.candidates[:4]) or "<li>No film found</li>"
    merge = ""
    if item.merge_into is not None:
        merge = (
            '<div class="both"><div class="side"><b>This row:</b> '
            f"{_e(item.title)} — {_discs(item)}</div>"
            '<div class="side"><b>Would merge into:</b> '
            f"{_e(item.merge_into.title)}"
            f"{' (' + str(item.merge_into.year) + ')' if item.merge_into.year else ''}"
            "</div></div>"
        )
    return (
        f'<div class="film"><h3>{_e(item.title)}<span class="tag warn">waits for you</span></h3>'
        f'<p class="muted">{_discs(item)}</p><p>{_e(item.reason)}</p>{merge}'
        f'<p class="muted">Offered, best first:</p><ul>{offered}</ul></div>'
    )


def _set_aside(item: Item) -> str:
    kind = "TV series" if item.set_aside_as == "tv" else "not a film"
    return (
        f'<div class="film"><h3>{_e(item.title)}<span class="tag tv">{kind}</span></h3>'
        f'<p class="muted">{_discs(item)}</p><p>{_e(item.reason)}</p></div>'
    )


def render_report(plan: Plan, *, ceiling_left: int | None = None) -> str:
    """The report as one HTML page."""
    identify = [item for item in plan.items if item.outcome == "identify"]
    ask = [item for item in plan.items if item.outcome == "ask"]
    aside = [item for item in plan.items if item.outcome == "set_aside"]
    merges = [item for item in ask if item.merge_into is not None]
    tv = sum(1 for item in aside if item.set_aside_as == "tv")
    made = datetime.fromisoformat(plan.made_utc)
    when = f"{made.day} {made:%b %Y}, {made:%H:%M} UTC"
    brave = f"{plan.brave_searches} Brave searches"
    if ceiling_left is not None:
        brave += f"; {ceiling_left:,} of this month's allowance were left before them"

    def listing(items: Sequence[Item], render: Callable[[Item], str]) -> str:
        return "".join(render(item) for item in items)

    parts = [
        "<!doctype html><html lang='en-GB'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>Identify films — dry run</title>",
        f"<style>{_STYLE}</style></head><body><main>",
        "<h1>Identifying the unmatched films — dry run</h1>",
        f"<p class='muted'>Made {_e(when)}. Nothing has been written. "
        f"{plan.tmdb_calls:,} TMDB calls and {_e(brave)}.</p>",
        "<div class='counts'>",
        f"<div class='count'><b>{plan.films}</b>films with a disc and no TMDB match</div>",
        f"<div class='count'><b class='ok'>{len(identify)}</b>identified automatically</div>",
        f"<div class='count'><b class='warn'>{len(ask)}</b>wait for you, "
        f"{len(merges)} of them merges</div>",
        f"<div class='count'><b class='tv'>{len(aside)}</b>set aside: {tv} TV, "
        f"{len(aside) - tv} not a film</div>",
        "</div>",
        "<p>The rule: a film is identified only when one TMDB film matches, and a year or a "
        "person agrees whenever TMDB holds another film of the same title. Anything that "
        "would merge into a film you already have waits for you.</p>",
    ]
    parts.append(f"<h2>Would merge into a film you already have ({len(merges)})</h2>")
    parts.append(
        "<p class='muted'>Each waits for you with both films shown. Nothing merges on its own.</p>"
    )
    parts.append(listing(merges, _ask) or "<p>None.</p>")
    parts.append(f"<h2>Identified automatically: a sample of {min(SAMPLE, len(identify))}</h2>")
    parts.append(listing(identify[:: max(1, len(identify) // SAMPLE)][:SAMPLE], _identify))
    parts.append(f"<h2>Waiting for you: a sample of {min(SAMPLE, len(ask))}</h2>")
    sample_ask = [item for item in ask if item.merge_into is None]
    parts.append(listing(sample_ask[:: max(1, len(sample_ask) // SAMPLE)][:SAMPLE], _ask))
    parts.append(f"<h2>Set aside ({len(aside)})</h2>")
    parts.append(listing(aside, _set_aside) or "<p>None.</p>")
    parts.append("<h2>Everything</h2>")
    parts.append(
        f"<details><summary>All {len(identify)} identified automatically</summary>"
        f"{listing(identify, _identify)}</details>"
    )
    parts.append(
        f"<details><summary>All {len(ask)} waiting for you</summary>{listing(ask, _ask)}</details>"
    )
    parts.append(
        "<h2>On your go</h2><p>The branch is merged, which deploys it, and the live run applies "
        "exactly this plan, after checking each film has not changed since. The films that "
        "wait for you then appear on You → Identify films, one tap each, and every "
        "identification can be undone there.</p>"
    )
    parts.append("</main></body></html>")
    return "".join(parts)
