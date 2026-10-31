# Cinema collection repeatability — 31 Oct

**Result: all nine repeat in the in-app-browser/HTTP comparison; five sources also answer
from the actual Railway API runtime. Four ODEON venues still need a deployable method.**
No application implementation, worker deployment, database write or subscription occurred.
The proposed build contract and next isolated experiment are in
`ab-cinema-ingestion-contract-2026-10-31.md`. Neither is approved by this report.

## Scope and method

Craig's “proceed” authorised repeatability checks after the all-nine specimens (#316).
The existing all-site public-source test permission (#315) remains in force. This was
bounded research, not recurring collection or a waiver of the concrete build checkpoint.

- Local HTTP: 22 anonymous source GETs; no retries, cookies copied from a browser, API
  keys, custom authentication, external redirect following or booking navigation.
- Existing Railway API runtime: 11 anonymous source GETs, using an existing authorised SSH
  key and a source-only Python command. No application imports, environment/secret reads,
  database connection, remote files, installation, restart, service or configuration change.
  The first ten ran at 18:55 UTC; one future-event check ran at 18:57 UTC.
- HTTP controls: 2 MB per successful body / 64 KB per error; redirects not followed here.
  Local requests use the prior 25-second HTTP timeout; Railway uses 12 seconds. These are
  response/read limits, not a browser transfer limit or guaranteed total wall-clock cap.
- Browser: reload Kilmarnock and Silverburn, revisit the other three ODEON branches, and
  select 1 Nov at Kilmarnock/Silverburn. Existing Codex in-app-browser session, not a fresh
  profile, Craig's normal Chrome/Safari or an unattended Linux browser. Browser subrequests
  are additional to the 33 explicit HTTP GETs and were not counted or transfer-capped.

## Same-window repeat samples

The first specimens and repeat observations are separated by elapsed time. Counts are
displayed/source rows, including past starts where a source retains them, not ticket stock.

| Venue | Earlier → repeat | Retained identity/start |
|---|---:|---:|
| GFT | 20 → 20 | 20 unchanged |
| Vue St Enoch | 31 → 19 | 19 unchanged |
| Everyman Glasgow | 11 → 6 | 6 unchanged |
| Science Centre IMAX | 53 → 52 | 52 unchanged |
| ODEON Kilmarnock | 15 → 10 | 10 unchanged |
| ODEON Glasgow Quay | 28 → 21 | 21 unchanged |
| ODEON Braehead | 25 → 17 | 17 unchanged |
| ODEON East Kilbride | 18 → 13 | 13 unchanged |
| Cineworld Silverburn | 25 → 19 | 19 unchanged |

All 177 retained keys have unchanged titles/starts; no duplicate keys appeared in these
samples. Every removed row starts before the repeat observation. This supports elapsed-time
pruning, **not a claim that 49 screenings were cancelled**. The previously expired/unlinked
Cineworld time also disappeared. A source can retain a recently started session, so the app
must independently suppress past starts rather than trusting source expiry alone.

Tomorrow's selected programmes yielded Kilmarnock 34 and Silverburn 53 time rows. This proves
two additional date selections, not the complete horizon of either operator or all branches.

## Actual Railway runtime comparison

The running API image is Linux/Python 3.12.16 with httpx, without Playwright or a Chromium
executable. No runtime dependency was added for this experiment.

| Source | Railway response | Evidence and limit |
|---|---|---|
| GFT listings | 200 | 20 unique showing references; same body hash as local. These are HTML SEO/fallback listings, not proof of full interactive-calendar coverage. |
| Vue schedule | 200 | 19 sessions; same response hash as local. |
| Everyman schedule | 200 | 6 sessions; same response hash as local. Metadata titles were joined from the earlier specimen, not freshly fetched. |
| Cineworld schedule | 200 | 18 sessions; all IDs/starts match the local 19-row response. The sole missing start is 18:30, already past. |
| Science Centre public Ticket Tailor | 200 | Past Shining page and a separate future event page. Future page has 20 structured startDate fields; this is one of the nine known event pages, not a fresh discovery of the whole box office. |
| Four ODEON venue pages | 403 each | No programme bodies obtained from this runtime. Local HTTP still redirects each to Queue-it. |
| Observed ODEON East Kilbride schedule | 401 | The exact URL was observed in the rendered page's resource inventory. One anonymous GET locally and one on Railway; no header/key/token extraction or follow-up authentication attempt. |

Cineworld's exact public schedule returned 403 in the earlier headless diagnostic but now
works in ordinary local HTTP and Railway HTTP. Its local HTTP booking references match all
19 displayed browser rows. The cause of the earlier refusal is unisolated; current access
does not promise future availability. It no longer needs to be grouped with ODEON as an
HTTP-inaccessible source on the strength of that earlier failure.

The Science Centre future HTML responses have equal byte lengths and different body hashes.
An attempted exact-body equality check failed. Do not claim byte-identical responses or
semantic equality from equal lengths/counts; dynamic page content is possible but unisolated.
The older Shining page still displays its past programme but now emits no Event JSON-LD.
Source structure disappearing after a start must not be interpreted as a cancellation.

## Readiness and extraction corrections

- Cineworld changes the selected day before replacing the old rows. Immediately after
  selecting 1 Nov, the page still showed 31 Oct times. The later extraction used the loaded
  next-day programme. A selected tab alone cannot certify which date the rows belong to.
- Kilmarnock also briefly has no programme while loading. Neither this nor an initial
  uninitialised location selector is evidence of an empty programme.
- The remote GFT regex found 80 textual occurrences but only 20 unique showing IDs. The
  local heading-aware parser also yields 20. The audit preserves the raw duplicate count;
  the report/contract deduplicate by source identity.
- The past Ticket Tailor page yielded zero startDate fields. This was investigated rather
  than called a parser outage: the visible event is past and its JSON-LD is absent. A future
  event page was then checked once, with 20 fields. No automated retry loop was used.

## What remains unproved

All-nine unattended collection on Linux; a complete horizon/discovery procedure per source;
cross-day/reschedule identity; genuine cancellation signals; original-release-year matching;
spring/autumn DST conversion; sustained freshness/request load; ongoing permission/licensing.
Owner permission to try restricted sites is recorded; it is not operator consent.

The unchanged API served c63bc06a7c7d317783b03a3379eb7b2b53852728 after the main runtime probe;
readiness reported db ok and all five integrations configured. This is a read-only health
observation, not an application close-out or deployment.

## Evidence and checks

Minimal tracked audit: `ab-cinema-repeatability-2026-10-31.json`. Raw responses, full rows,
source-only scripts and the next-day screenshot are gitignored under
`scratchpad/ab-cinema-research/repeatability-2026-10-31/`. No cookies, request authentication,
contact details, private production data or full programme payloads are published.

Offline checks verify nine comparisons/177 unique retained identities, all removed starts
are past, correct selected dates, 19 matching Cineworld HTTP/DOM booking references, 18
unchanged Railway Cineworld identities/starts and honest HTTP failures. Document diff/JSON
checks apply. Full application gates, migration, browser-worker, DST, cancellation and
production-ingestion checks have not run; no such implementation exists.

No AB6/AB7 acceptance criterion is closed by this report. AA10c and other sittings remain
excluded. The parked links-only proposal remains unapproved.
