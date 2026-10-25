# AA6 — Feeling lucky, 25 Oct

## Agreed scope and acceptance criteria (verbatim)

### AA6 — Feeling lucky 🟡
- **21.** "Feeling lucky" deals one film at a time until someone takes one: on Home for the person
  alone (the Archive, optionally unwatched by them), and on a night, where taking it adds it to
  the night's suggestions. Skipped films are not dealt again in that run.
- Tests. Gate green.

## Pre-flight

Clean main `07d859aa80f9c7c93685920a3c6af65dd8182821`; final CI 40212949471 all seven jobs green.
Both hosts serve that SHA, db ready, all integrations configured. AA4 and AA5 shipped in
separate PRs #108 and #109. Only AA6 remains in this authorised sitting; do not start sitting 4.
Owner-only device checks and AA10b's final valuation readback remain open.

## Design

One authenticated read-only draw request returns one eligible owned film, excluding the ids
already dealt in this browser run. This avoids loading the whole Archive or storing new run
rows. Start again clears the run; leaving the screen or switching account/night also ends it. Home can
limit the pool to the caller's unwatched films; choosing a film confirms the pick without
logging a watch. On a night, the existing filters apply, people's existing suggestions are
excluded, and choosing uses AA4's suggestion action (including promotion of a seeded pick
without losing votes). No migration, job, external provider call or hosting change.

## Evidence

Implementation complete; local verification is complete apart from the explicit route-list decision.

Focused API: 10 passed, covering once-only draws and exhaustion, caller-scoped live watch
history, owned-film eligibility, night filters/suggestion exclusions, membership/ended-night
boundaries, invalid payloads and unauthenticated requests. Draws create no watch/suggestion rows.

Initial UI checks found that a new h2 interrupted Home's fixed carousel heading list and the
night's section order. The chooser now uses a fieldset/legend for its controls; those original
assertions remain unchanged and pass. Test helper fixes replaced unavailable DOM/custom mock
matchers with equivalent supported assertions and reset queued mock answers between cases.
The first focused run had nine failures; the retry had one unsupported mock matcher, then all
six chooser cases passed in the full web suite. Initial Python test formatting was corrected
with the standard formatter; no gate assertions were loosened.

Full web gate: shared 154 and web 688 passed; shared type/build, web lint/type/build and E2E
typecheck passed. Eleven pre-existing lint warnings remain, with no new warnings.
Full API gate: lint/format/mypy passed; 2,467 tests passed, nine documented local Unix-socket
import-guard skips, and the pinned route-surface test failed solely on the new
`/api/v1/feeling-lucky` path. The exact one-path allowlist addition was prepared but not
applied: Craig's instruction requires a decision before changing test expectations. Approval
was requested in the chat. All new authentication/access/behaviour tests pass independently.

The first Chromium run passed both AA6 flows and produced inspected 375 px screenshots.
Its new test file ran before the import case and added one owned film to that case's expected
70-film starting catalogue, so the unchanged 73-film assertion failed. The AA6 cases now
live with the other movie-night cases, after the import checkpoint. The obsolete run was
interrupted and the full Chromium/Firefox/cron suite restarted; no import assertion changed.

A read-only production check confirmed the deployed live rows use `film` (1,879) and `tv`
(52), agreeing with the eligibility predicate. This was a SELECT, not a provider or catalogue
mutation. No AA6 production deployment or signed-in live acceptance is claimed yet.

## Local result at the initial handoff

- Chromium: 36 passed. Firefox: 35 passed and the existing documented dictation skip. Cron: six passed. Both new flows pass in both browsers; the unchanged import checkpoint passes after moving the new cases. Final E2E typecheck passes.
- Both 375 px screens were visually inspected: title/runtime/watch state/place, Choose and Skip controls fit; the night retains Suggest a film first. New source passed the React checklist: stable scope keys, state owned by the run, no effect that derives state, native controls, disabled pending actions and honest errors.
- The full local API run remains 2,467 passed, nine documented local Unix-socket skips and one failing route-inventory assertion. The proposed change is exactly one expected path, `/api/v1/feeling-lucky`, with equality and all existing paths/access checks retained. It remains unapplied pending Craig's decision. No gate was weakened.
- AA6 has no migration, provider job or hosting/credential change. Its CI, Docker-image verification, WebKit and production acceptance have not run. Real-device acceptance (6.2, 5.6, 9.5 and 8.4/16b), AA1's phone reinstall and AA10b's final valuation readback remain owner-held.
- Resume the existing `feat/aa6-feeling-lucky` branch. If Craig approves the inventory change, add the one expected path, rerun the API gate, confirm the other gate evidence remains current, then create its PR and run all seven CI jobs before merge/deployment/close-out. Stop after AA6. Do not start sitting 4.

The candidate route-list patch is prepared at `/tmp/mcu-aa6-route-allowlist.patch`; the exact
path above is enough to recreate it if the temporary file is gone. No AA6 PR was opened or
production deployment claimed while this decision was unanswered.

## Approved continuation, 25 Oct

Craig explicitly approved the one-path route-list addition and said continue. The prepared
patch is applied: only `/api/v1/feeling-lucky` is added; set equality and every existing route
and assertion remain. The checkpoint above records the initial pause, not an outstanding
owner action. The approved full API gate passed: lint/format/mypy and 2,468 tests, with nine documented local Unix-socket skips. PR/CI/production close-out follow.

The installed Git lacks `git branch --show-current`; the read-only branch check was repeated
with `git rev-parse --abbrev-ref HEAD`, confirming the existing AA6 branch. No branch or
history mutation resulted from that failed option.

## Shipment and completed acceptance

Craig's route-list approval resolved the only decision gate. The approved full API gate
passed 2,468 tests with the nine documented local Unix-socket skips; lint, formatting and
mypy passed. Other local gate evidence above remained current; no app source changed after
its green web/browser runs. PR [#110](https://github.com/CraigR973/mcu-app/pull/110), source `d7b09bbef78cdb0d8ad395671b1b8cbf5774cd57`, CI 40229655987: all seven jobs green,
including Postgres 17 without local database skips, the real image, full migration reversal,
and Chromium/Firefox/WebKit/cron. Merge `54dbc079fd9522c84584b09496bc8a4312421cca`.

Both production health and web version report the merge SHA; readiness is db ok with every
integration configured. The new draw endpoint refuses an unauthenticated POST. No new
migration or live provider acceptance run was needed for AA6. Signed-in flows and both 375 px
screens were exercised locally and in CI; the production browser has no authenticated
session, so a real phone or signed-in production flow is not claimed.

Acceptance 21 is met: Home and a night each deal one owned film at a time; Home optionally
uses only the caller's unwatched films; skipped ids are excluded until that run ends;
choosing on a night adds/promotes one suggestion without losing its seed's votes. Local and
CI gates are green. AA6 is closed; sitting 3 is complete. Sitting 4 was not started.

Final PR totals: API 2,477 passed with no skips; shared 154/web 688; Chromium 36; Firefox 35 plus its documented dictation skip; WebKit 34 plus its two documented platform skips; cron six. Read-only production SQL confirms revision 067, 1,943 films, 3,797 copies, 1,591 watches and nine nights, matching the post-AA5 observation. Both roles still read the 11 AA5 cache columns and cannot read credentials. Both IMDb caches remain empty; cron-specs last ran at 02:00 UTC on 25 Oct, before AA5, with nothing due and no IMDb error. First live refresh remains unverified; the agent did not start one.

Earlier stages: [AA4 verification](aa4-verification-2026-10-25.md) and [AA5 verification](aa5-verification-2026-10-25.md).
