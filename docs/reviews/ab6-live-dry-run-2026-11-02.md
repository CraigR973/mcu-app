# AB6 approved live dry-run — 2 Nov

> Current checkpoint update (#329): Craig approved the report-only free-gap investigation
> below; it is now complete. Vue yielded two dates then refused; TMDB supplied three
> metadata candidates. See [the current evidence and revised-build decision](ab6-free-gap-investigation-2026-11-02.md).
> Historical “not authorised” statements below describe the preceding stage. No further
> implementation/new live pass/production action is approved by this result.

## Result and stop

Craig approved the exact capped all-nine live dry-run after reviewing draft PR #125.
One pass ran on clean `1cfd9b97c4f026918c72fd340ef76884a7cdc657`, at 16:36–16:37 UTC,
for 2–15 Nov inclusive. It found **1,185 dated showing records from eight venues**;
**1,102 were future, non-expired and non-cancelled at 16:37:18 UTC**. The other 83
already started earlier on 2 Nov. These are source observations, not completed bookings.

Vue Glasgow St Enoch returned **HTTP 401**. That host stopped without retry, alternate
request, browser/proxy, new credential or source switching. All nine-source acceptance
therefore fails. The CLI exits **2**, deliberately, with `sourcesObserved: false`.
The reviewed-artifact loader independently refuses this exact artifact with:
`vue-st-enoch: source acceptance unresolved; no reduced-coverage write`.

All 1,185 classifications remain **Unclassified**; all incoming TMDB/IMDb IDs are absent.
The current adapters do not extract verified run evidence. This pass proves that eight
venues return programme observations, not that New/Older filtering works. No scope or
classification definition has been changed to hide the gap. AB6 remains an unmerged
draft; AB7, AA10c and all other sittings remain unstarted.

## Counts and observed horizon

| Venue | Dated records / future at preparation | Observed dates in November |
|---|---:|---|
| ODEON Kilmarnock | 112 / 105 | 2–8 (7 dates) |
| ODEON Glasgow Quay | 223 / 198 | 2–8 (7 dates) |
| ODEON Braehead | 209 / 186 | 2–8 (7 dates) |
| ODEON East Kilbride | 163 / 144 | 2–8 (7 dates) |
| Cineworld Silverburn | 372 / 371 | 2–15 (14 dates) |
| Vue Glasgow St Enoch | 0 / 0 | Unavailable: 401 |
| Everyman Glasgow | 72 / 69 | 2–10, 14–15 (11 dates) |
| Glasgow Film Theatre | 20 / 15 | 2–3 (2 dates) |
| Science Centre IMAX | 14 / 14 | 3, 5–8, 12–15 (9 dates) |
| Total | 1,185 / 1,102 | Eight venues observed |

No adapter proves a complete operator programme on any selected date: all
`completeDates` sets are empty. An unobserved date is not a proved empty programme.
Cineworld has observations on all 14 selected dates; that is not a completeness claim.
All 1,102 future observations have syntactically validated operator/box-office booking
URLs. No link was opened, booking submitted, availability/seat inventory verified or
checkout contacted. No booking or cancellation history is established by this single pass.

CinemaTimes preserves `Times from ODEON, updated Monday 06:17` as a label. The label
does not provide a full dated UTC timestamp; upstream age remains unknown. The other
adapters also supply no evidenced upstream timestamp. Fetch time does not invent one.

## Budget, artifact and non-write proof

| Measure | Actual | Approved limit |
|---|---:|---:|
| Anonymous GETs | 49 | 120 |
| Decoded body bytes | 5,307,435 | 67,108,864 |
| CLI wall time | 55.122 seconds | 300 seconds |

The tested transport enforces 15 seconds/request, 2 MiB decoded responses, one concurrent
request/start per host with at least one second between starts, and two global slots.
No subscription, signup, message, payment, new service, hosting/configuration or credential
change. Source fees £0; existing compute/network use remains unpriced.

Snapshot SHA-256:
`3c7bdc6fcf3be1b9e15999be68c623ef2ae5b2d00f8c843d34ffa75977f8d3ba`.

Local evidence is in `scratchpad/ab6/live-2026-11-02T163622Z/`: scope, normalised snapshot,
CLI report/stderr, before/after database counts, per-venue facts, timing and the independent
import-refusal proof. The portable aggregate audit is alongside this report as
`ab6-live-dry-run-2026-11-02.json`. Raw provider bodies/images/plots were not persisted by
the CLI. The artifact is diagnostic, not eligible for import; its age must never be reset.

The database URL was verified as the owned localhost disposable Postgres by host and
`SHOW data_directory`. Before/after counts and all nine disabled enable flags are exactly
equal: cinema venues 9; cinema films/screenings/coverage/runs 0; catalogue/copies/diary/
release calendar/admin actions/heartbeats 0 in this test database. No production DB was
connected. The preview's 1,185 prospective additions are against the empty disposable
cinema tables; they are not production row counts or write approval.

## Required re-plan before further implementation

Keep all nine venues, Film first and the £0 source-fee constraint. Do not import the eight
working venues, enable collection, merge/close AB6, start AB7 or change hosting/credentials.
The free-source feasibility basis now needs a specific Vue/access and classification
evidence stage. Implementation remains unchanged while that stage is unapproved.

Offline comparison found a concrete request-format difference: the recorded 31 Oct
successful Vue URL has literal ISO-time colons; the collector's `urlencode` produces
percent-encoded colons. The earlier research also used different identifying app/Accept
headers. Both are ordinary anonymous requests. Neither difference is proved to cause
the new 401; no auth requirement, temporary failure or query-format diagnosis is claimed.
Saved Everyman/Cineworld metadata has null release dates, no `allMovieUnion` records,
and no explicit re-release/reissue/first-UK-theatrical phrases in editorial comments.
There are 75 distinct title strings across the live artifact, not 75 verified film identities.
Title-only matches and release-year shortcuts remain forbidden.

**Recommended next owner decision: one report-only free-gap investigation.**

1. Vue: one ordinary anonymous GET in the previously recorded public request format for
   the run day's St Enoch programme, identifying the private app. If successful, at most
   13 further date GETs to measure the remaining 14-day window. Any 401/403/429/challenge
   stops Vue immediately; no alternate after that refusal. No login/session/auth changes,
   impersonation, browser, proxy or provider switch. This is a separately approved new
   experiment after the observed refusal, not a retry already covered by #328.
2. Classification: inspect saved source evidence, then at most 12 read-only requests to
   the existing TMDB integration/documentation (`api.themoviedb.org` and
   `developer.themoviedb.org`) using already configured credentials only. Check the £0
   condition first; stop if a subscription, new credential/configuration or charge is
   required. Use three captured examples: Clayface, Interstellar and the Pan's Labyrinth
   anniversary programme, without assuming their identity/run from their titles. Report
   identity corroboration, first GB theatrical versus later release dates and what run
   evidence is still missing. TMDB dates alone do not prove a current first run. No bulk
   enrichment, model calls, catalogue/diary changes or invented classification rule.
3. Combined cap: 26 GETs, five minutes, 15 seconds/request, 2 MiB/response, 64 MiB total,
   two global slots and one request/second/host. Ordinary source refusal stops that host;
   no provider fallback or hosting/credential change. Cost is capped at £0 source fees;
   existing quota/compute usage is consumed and remains unpriced. If existing credentials
   are unavailable, stop rather than asking for or provisioning replacements mid-run.
4. Deliver one evidence report and revised build choices. Only after its acceptance may
   adapter/enrichment implementation resume; then regenerate and review a fresh eligible
   all-nine artifact. Actual row-count, production deployment/write and nine-row enable
   decisions remain separate. If free reliable evidence cannot be established, report
   that fact without silently reducing venues or relabelling unknown films.

This next experiment is **proposed, not authorised or run**. The approved one-pass
dry-run is complete. That pass continued only with its other pre-approved hosts after
the Vue refusal; no further Vue request or separate source pass has been made.
