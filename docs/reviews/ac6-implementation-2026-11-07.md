# AC6 implementation and evidence

Owner checkpoint: all eight recommendations approved with “approved” on 7 Nov (#348).
Contract: `ac6-owner-checkpoint-2026-11-07.md`. Work is AC6 only, on the existing checkout.

## Acceptance criteria (verbatim, before implementation)

### AC6 — A daily digest of new films at your cinemas 🟡

- **Checkpoint before build:** Craig approves the wording and the new preference.
- After the daily refresh, each person with the switch on gets at most one push naming
  films seen for the first time anywhere among the nine, de-duplicated by AC3's identities,
  with run labels, opening "New this week" in At the cinema. Nothing new means no push. A
  film that returns after 30 days or more out of the programme counts as new again;
  otherwise never twice.
- A new Cinemas switch in Notification settings, default on, with "Older films only". Quiet
  hours and digest mode apply.
- New preference column or columns, a reversible migration and guarded grants.
- Safe under a retried, partial or failed refresh: at most one push per person per day, and
  a venue whose collection failed adds nothing.
- Full gate and E2E; after deploy, the first scheduled digest is read back in the outbox,
  never sent by hand. Phone receipt is Craig's observation.

## Evidence

Implementation follows the eight approved recommendations. Main was green at
`746b23027fc79223ffbc5405e0a2186cca91a265` (seven-job CI 42379182157).
PR #136 deployed implementation commit `46aaba5309bca4d5b4b62ef4a9ec5786f594b5be` on 7 Nov.
No scheduled-digest or real-phone acceptance is claimed. The approved migration/baseline ran
as part of deployment; no manual production source refresh, digest, trip or hosting change
was performed. The read-back below is a read-only database transaction.

## Mechanism and review

Migration 073 adds the two preferences, category and five durable tables, guarded grants to
both roles and a silent baseline; no source/catalogue/watch/trip data is rewritten. The daily
evaluator uses finished cron-run coverage provenance, AC3 identity and a transaction advisory
lock; history/day/outbox commit together. Profile row locks serialise preference changes and
send claims. Switching off cancels pending messages; narrowing to older-only permanently
excludes pending titles, even if broadened again. Claims commit before transport; uncertain
sends are not replayed. Delayed rows coalesce into one logical delivery per actual London day.

The shared preference and programme schemas are additive and tolerate older answers without
inventing an empty view or saved preference. The existing programme read supplies New this
week, including historical cards and delayed-match dates; reads do not queue or refresh.
The current architecture map records the new flow and its approved limits.

## Failures encountered and corrections

- Initial pgserver startup failed on locale settings; restarted with UTF-8 locale. Its Unix
  socket URI caused the collection replacement tests' localhost guard to skip nine cases.
  A new disposable TCP database fixes the test environment; no guard was loosened.
- The first full API run also exposed roles created by the backup tests after initial
  migrations, leaving the older profile-photo grant absent. A fresh database was migrated
  with both roles already present. The existing credential/grant assertions were preserved.
- The API contract snapshot was stale after adding approved response fields. Regenerated it
  using the project's exporter; the shared-contract assertions stay unchanged. This is the
  required expectation artefact change, not an assertion weakened to reach green.
- Initial new code had lint/format and an optional-variable typing issue; formatted/split SQL
  literals and renamed the conflicting local variable. No ignores or disabled checks.
- The new browser case initially sought an At the cinema link on the phone film page; the
  actual control is the labelled Back button. Corrected the locator while retaining the
  assertion that New this week's query survives Back. Its light/dark 375 px flow then passed.
  TypeScript also caught a Playwright-only `exact` option in a Testing Library call; removed
  that unsupported option (the literal accessible name still matches exactly).
- The full jobs run passed the digest assertions but its post-job HTTP preference cleanup
  hit ECONNRESET. Cleanup now restores the saved preferences directly in the disposable
  database, so a blocking command's idle HTTP connection is not a cleanup dependency.
  The two scheduled executions, decrypted push, exact counts and destination assertions
  are unchanged. No retry or relaxed expectation was added.

## Final implementation verification

Review found two additional edge cases before shipment, both pinned by failing regressions
before their repairs. A showing-key rollover could bypass an unresolved rollout baseline:
baseline inheritance now uses the existing AC3 fingerprint within the same source, without
linking identities across sources or guessing a film. A return reusing an old key records its
fresh observation as first-listed time, rather than displaying the original episode as a
delayed match. An already-due digest held by a late quiet-hours check could repeatedly restart
its digest clock and starve the daily morning pass: it now waits only for quiet hours to end,
preserving the original elapsed digest target. No assertion or expected outcome was relaxed.

The final clean implementation tree (`46aaba5`) passed the full local gate: API **2,741 passed,
zero skips**; Ruff/format/mypy (278 source files); shared **200** and web **881** tests;
shared/web typecheck and production builds, web lint, E2E typecheck. Existing warnings remain:
36 API deprecation warnings locally (37 in CI), 11 existing React Refresh lint warnings and
the existing browser test warnings; none was silenced. The API suite includes all 16 derived
field trigger tests against real disposable Postgres. Focused AC6 regressions: **39 passed**.

Local full E2E: Chromium **90 passed**, Firefox **89 passed + 1 permitted skip**, jobs **8 passed**.
The fake scheduled command ran twice and produced one named, run-labelled digest per person;
the decrypted push destination opened New this week through sign-in in both themes at 375 px,
with film-page Back preserving the query. Light/dark screenshots were visually inspected.
Local WebKit is unavailable on this Mac; CI supplied its evidence.

[PR CI 42391299778](https://github.com/CraigR973/mcu-app/actions/runs/42391299778) passed all
seven jobs for the exact implementation commit, including Postgres 17 (**2,741 passed, zero
skips**), complete upgrade → downgrade base, production image build/migrate/boot, dependency
audit and the full browser job. Chromium **90**, Firefox **89 + 1**, WebKit **88 + 2**, jobs **8**.
Only the three documented cases skip: Firefox dictation, WebKit live match on an open page,
and WebKit's lost replay-answer scenario. No AC6 case is skipped. Local migrations also proved
head → base → head, silent baseline/grants and refusal to downgrade populated digest history.

[Main implementation CI 42392858508](https://github.com/CraigR973/mcu-app/actions/runs/42392858508)
is the same implementation SHA. [PR #136](https://github.com/CraigR973/mcu-app/pull/136) carries
the final documentation-commit CI and served-SHA verification record as well. Completion of
all seven jobs and exact API/web SHA parity is required for the final handoff; a green
feature-push run with its E2E job skipped is not used as browser evidence.


## Production read-back — 7 Nov, 16:46 UTC

API `/api/v1/health` and web `/version.json` both serve
`46aaba5309bca4d5b4b62ef4a9ec5786f594b5be`. Readiness is `ready`, `db: ok` and
`push`, `ai`, `ebay`, `tmdb`, `brave` all `configured`. The normal Git-linked production
release was used; no hosting, variables, domains or credentials changed.

One explicit read-only transaction observed:

- Migration **073**; all five new tables and both new preference columns readable by
  `mcu_readonly` and `mcu_backup` (10 table grants and 4 column checks).
- Whole-profile/PIN-hash/push-credential access remains withheld for both roles, proved
  with privilege metadata rather than reading credential values.
- **278** retained source-film/listing aliases silently baselined; **23** retained verified
  identities silently baselined. No catalogue, source identity, showing, watch or trip data
  was rewritten by AC6.
- Both currently active people have Cinemas **on**, Older films only **off** and Movie night
  **on**. Implementation loops all active profiles; its tests include more than two.
- **0** appearances, **0** evaluated days, **0** delivery claims, **0** cinema outbox rows.
  No AC6 scheduled run has occurred since the deploy. These zeroes prove silent rollout,
  not successful scheduled evaluation or delivery.

## Acceptance by criterion

| Criterion | Evidence and remaining gap |
|---|---|
| Owner checkpoint | Met: Craig approved all eight recommendations, #348, before implementation. |
| First/return episodes, one named/run-labelled push opening New this week; no-new silence | Evaluator, transport and browser tests pass, including baseline/identity changes, 29/30-day boundary and delayed rows. **Positive naturally scheduled production evidence pending.** Partial programme completeness is not proved. |
| Cinemas default on / Older films only; quiet hours and digest mode | Migration defaults read back; API/UI/browser and delayed-clock regressions pass. Existing schedules may defer held delivery until the following day. |
| Columns, reversible migration, guarded grants | 073 upgrade/base/head passes locally and in CI; both role grants and credential exclusions read back. Populated-history downgrade refuses instead of silently deleting history. |
| Retry/partial/failure safety | Separate-connection concurrency, rollback, terminal-run provenance, failed venue exclusion, frozen daily result, committed claims and no uncertain replay pass. Source partiality remains the approved observation risk. |
| Full gate/E2E and scheduled outbox read-back, phone receipt | Code/local/PR gates pass; final main/documentation checks recorded in PR #136. **First natural qualifying outbox/claim and phone receipt/tap remain open.** |

**AC6 is deployed, not fully accepted. Its ledger row and heading remain unstruck.** No
production digest or refresh was triggered manually. A scheduled run without an eligible new
film must be recorded as empty and cannot supply positive delivery evidence. The next step
is to read the first genuine qualifying scheduled day's appearances, recipient eligibility,
outbox/claim payload, device dispositions and status without invoking evaluation or transport.
Push-service acceptance is not proof of phone receipt. Craig observes the phone and tap.
AC3's post-8-Nov rerun read-back and AC5's first real trip/phone observations remain separate.

## Implementation choices within the approved contract

- Reuse the existing programme GET and its shared schema/cache for New this week; no read
  queues notifications, fetches sources or writes history.
- Use the existing profile row as the common preference/claim lock; no new coordination
  service, timer, dependency, credential or fixed two-profile assumption.
- Dispatch cinemas in independent committed sessions and exclude it from collection bundling;
  caller transactions and AC5's Movie night behaviour remain intact.
- Freeze baseline DDL in migration 073; same-source AC3 fingerprints preserve unresolved
  baseline aliases through source-key rotation without speculative identity matching.
- Preserve elapsed digest targets when late quiet hours defer a due message; commit each
  actual London-day claim before one attempt per device and never replay uncertain transport.

To inspect the feature: **Settings → Notifications → Cinemas / Older films only** and
**Movie night → At the cinema → New this week**. Before a natural arrival this view is empty;
existing programme films remain under All films. No test notification is needed or authorised.


## Original final handoff CI failure — subsequently repaired separately

Implementation main CI 42392858508 passed all seven jobs. Final documentation SHA
`196f2d65df7403cb12bbdb0a84c0be7bd3c1bb68` is served from API/web with full readiness,
but CI 42393261032 failed Firefox's existing calendar feed-link case. Chromium 90 passed;
Firefox 88 passed, 1 failed, 1 permitted skip; WebKit 88 passed + 2 permitted skips; jobs 8
passed. Every AC6 case passed. The trace has zero calendar-subscription POSTs and changing
programme content between pointer-down/up. A held-response local reproduction proves the
button moves 541.5 px and loses that click. No blind rerun or gate weakening was used.

Craig authorised the separately scoped repair (#350), now deployed in PR #137 at
`7c536d9c99ebd0102a875f099e4bbc29bbbefc06`. Native shared-query readiness prevents the
lost enabled click and Coming soon has honest loading/offline states. The full local gate
(API 2,741, shared 200, web 891, C94/F93+1/jobs8) and all seven exact-head PR CI jobs
42400083769 (C94/F93+1/W92+2/jobs8) pass without relaxed feed assertions, skips or retries.
Both production services serve `7c536d9` with full readiness at 18:43 UTC. The repair report
preserves the original failure, host-contention failures and fixture correction:
`docs/reviews/ac6-calendar-ci-blocker-2026-11-07.md`. Final exact-SHA main/handoff CI and
parity are stamped in PR #137 before completion. Natural scheduled digest and real-phone
receipt/tap remain pending; no manual production digest/refresh/trip/feed action ran.

Additional tooling failure: this gh version's PR editor queries retired Projects (classic)
metadata and failed. GitHub REST updated the same PR description; no code/gate changed.

Read-only recheck at **17:20 UTC**: production API/web still serve `196f2d6`, full readiness
passes, migration/grants/defaults are unchanged, and appearances/days/claims/cinema outbox
remain zero. No manual production refresh, digest, trip or calendar-subscription action ran.

Read-only post-repair check at **18:43 UTC** confirms 073, unchanged grants/defaults, 278 silent baseline listings / 23 identities, and zero appearances/days/claims/cinema outbox rows. AC6 acceptance remains open.
