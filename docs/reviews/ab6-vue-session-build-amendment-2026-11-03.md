# Proposed AB6 public-page-first Vue build amendment — 3 Nov

**UNAPPROVED. No implementation or new live request is authorised by this proposal.**
This is a narrow amendment to accepted #327/#330 on existing branch/draft PR #125,
prepared after the owner-approved #333 report-only experiment. It preserves all nine
venues, Film first, £0 source fees, the existing service/job, today/tomorrow Vue horizon,
and strict identity/category/import/production gates.

## Decision and evidence

Build the ordinary sequence observed at 13:14 UTC on 3 Nov: public St Enoch programme page
200, then 4 Nov programme JSON 200/48 sessions using cookies set normally by that page.
The two requests used 481,312 bytes/1.454s. The same API URL returned 401 earlier that morning.
No contemporaneous control proves cookie causality; this proposal adopts the successful
ordinary request sequence as a bounded protocol, not a proved explanation or reliability claim.
The complete evidence is ab6-vue-session-investigation-2026-11-03.md/JSON.

Reject a today-only/eight-venue reduction or failed-prefix acceptance because it changes
the approved product before a reliable horizon is established. Reject paid APIs, browser
hosting and extra retries because the ordinary HTTP sequence succeeded and they add scope
or cost. No extra control experiment is needed to implement this exact observed sequence;
its live viability still requires a separately approved fresh all-nine acceptance read.

## Proposed request flow

```text
Vue public page
      ↓ ordinary session, memory only
Today's/tomorrow's Vue JSON
      ↓ existing validation and failure rules
Programme snapshot
```

## Exact proposed implementation

1. Derive Vue's selected dates exactly as now: only execution day/tomorrow in Europe/London
   intersected with the caller's at-most-14-day window. If none are selected, request nothing.
2. Before the first selected Vue date, GET exactly the known public programme entry point:
   `https://www.myvue.com/cinema/glasgow-st-enoch/whats-on`.
   Do this once per active Vue collection/pass, never once per date. Reuse the existing
   HTTP client and ordinary identifying/Accept headers. Cookies set by the public response
   remain only in that client's memory and normal host/path scope; no cookie values are
   logged, persisted, supplied by the owner or saved in a snapshot.
3. Only after an ordinary 200 page passes existing refusal/challenge checks, perform the
   existing observed Vue date GET(s) in that same client session. Preserve current URLs,
   session/venue/booking/date validation and the today/tomorrow limit. No redirect, script
   execution/download, guessed endpoint, login, copied/private token, browser, stealth,
   operator contact, provider switch or challenge solving.
4. Count the page GET inside the unchanged combined 120-GET/five-minute budget (including
   at most 12 optional cached TMDB GETs), 15s/request, 2 MiB/response, 64 MiB total,
   two global slots/one start per second per host. The new step costs at most one GET per
   Vue pass and up to 2 MiB/15s within those totals, not extra budget. Existing deadline
   and disabled-source behavior remain. No new service, credential, fee, schedule or
   Railway diff; previously prepared token-reference plan remains unapplied.
5. Any failed/refused/challenged public page fails the Vue snapshot before a date request.
   Any failed selected date still fails the whole Vue snapshot; successful prefixes remain
   diagnostic/quarantined and cannot replace accepted data. Empty, partial, healthy and
   stale states, cancellation uncertainty and all-nine acceptance rules stay unchanged.
   The collector stops on any public-page non-200, not just 401/403/429. Broaden no retry
   permission and make no fallback request. Check existing ordinary-page/title challenge
   handling against the successful page title using synthetic fixtures; do not add a new
   browser bypass or weaken refusal checks.
6. Bump the source adapter version for this protocol change so artifacts name the code
   that collected them. No new table, migration, API/zod/browser schema, catalogue/diary
   operation or automatic identity/category mapping. The historical failed artifact stays
   failed; the 48 diagnostic rows are never spliced into it.

## Verification and cost before the next owner stop

Add regressions for page-before-date order/one page for two dates, ordinary HTTP cookie
propagation without saved values, page refusal/challenge/non-200 causing zero date requests,
second-date refusal quarantining the prefix, no page for no selected Vue dates/disabled
collection, and the page consuming the existing request/byte/time budgets. Keep current
booking/identity/date assertions, 120/12/body/rate/deadline limits and all-nine gate intact.
Tests use synthetic HTTP/fixtures only; no automatic live request is part of verification.

Run the full normal ten-command clean local gate against an owned disposable local database
and exact-head seven-job PR CI, including the browser/jobs job. No assertion/timeout/skip
waiver or unrelated repair. A full verification cycle adds engineering/CI time; source
subscriptions stay £0 and existing compute/network/storage/CI cost remains unpriced.
This is still one AB6 branch/PR; do not merge or deploy because fixtures are green.

After implementation/checks, stop for a concrete fresh all-nine request scope. Its observed
source rows, coverage, omissions, candidates and exact mapping selections remain separate
owner review. The new successful Vue identity facts may support future source-specific
candidate review; existing CinemaTimes metadata records are not relabelled as Vue records.
New current first UK run/Older returning or reissue/Unclassified remain strict; a populated
New filter is still unproved and is not promised by this build.

Actual Railway config apply, disabled deployment, production import, selected mappings and
nine-row enable remain explicitly unapproved. No AB6 close-out/AB7/AA10c/other sitting.
If new feasibility evidence changes this scope, re-plan before further implementation.
