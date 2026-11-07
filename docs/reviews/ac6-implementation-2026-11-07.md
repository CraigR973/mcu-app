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
Deployment and exact final-tree verification are pending. No scheduled-digest or real-phone
acceptance is claimed. No production source refresh, digest, trip or data write was performed.

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

## Verification in progress

The intermediate API run passed 2,733 tests with zero skips, including all database tests.
The intermediate shared/web run passed 200 shared and 881 web tests; focused shared-contract,
cinema-view and preference tests passed 16. The scheduled command on fake source/TMDB/push
data generated one labelled digest per person across two executions, and its push URL opened
New this week in both themes at 375 px. The browser Back check passed. Final exact-tree gates,
PR/main CI, deployment/readiness, migration/grant read-back and naturally scheduled outbox
evidence still need their own results below; these intermediate runs do not close acceptance.
