# Movie-night seeding race — shipped repair, 29 Oct

Craig approved the separate race fix in chat after the red-CI stop. The original AB1/AB2
implementation and approved planning history are preserved. Diagnostic handoff 5a1ccad is preserved through the repair PR/CI and merge.
Starting main source cf28806 was red (40793684816); this fix is separate from AB2 and does
not start sitting 2 or AA10c.

## Approved goal and criteria (verbatim from the owner-approved proposal)

Serialise shortlist seeding per night, add a deterministic concurrency regression, retain
every push assertion, then run full local/PR/main checks and production verification.
No schema/API change. Sitting 2 and AA10c remain excluded.

## Evidence and concrete plan

Final AB2 docs CI failed one existing Chromium invite case. Every AB2 case passed in all
three browsers. Its API artefact shows POST movie-night/<id>/send raised a uniqueness
violation on uq_movie_night_suggestion_movie, before notification delivery. Candidate GET
and Send both call ensure_seeded, which reads an empty list then inserts without a lock.

1. Write a two-connection regression holding the first seeder before insert; observe the
   second transaction's real database lock rather than timing sleeps. Cover both first
   commit and rollback. Demonstrate the new regression fails on the current source.
2. Hold the existing night's row FOR UPDATE before checking whether the shortlist exists,
   following the existing vote lock order. The later request rechecks after the first
   transaction commits; rollback permits it to perform the first seed itself.
3. Retain all existing invite, push, match, ownership, role and route assertions. No retry,
   skip, timeout extension, conflict swallowing, API field or migration is proposed.
4. Run the full clean local gate and available E2E projects, exact-head PR/main CI and
   production API/web SHA/full readiness. Update the architecture map, evidence and sitting
   handoff only after proof. No real production invitation, data rewrite or provider call.

A uniqueness-error catch/retry is rejected: it leaves a failed transaction and risks skipping
the invite path. A per-night database lock makes the read/seed decision atomic across API
workers, and automatically releases on commit/rollback. Different nights retain separate locks.
Verification allowance is roughly 45–60 minutes plus repair, not a completion promise.

## Verification and failures — running record

The corrected regression fails on the unpatched service with “Second seeder read the empty
shortlist before the first transaction finished”. After the six-line per-night lock change,
both deterministic commit/rollback cases and all existing movie-night service/concurrency
tests pass: 31 tests. Existing E2E push/access assertions are unchanged.

Initial fixture cleanup attempted an ordinary DELETE on its own committed copy; the real
soft-delete trigger retained it, so the subsequent Movie cleanup hit its FK. The fixture
now uses the existing transaction-local permanent-delete setting only for its own rows on
the disposable test database. The one earlier test copy/movie was removed by exact UUID on
that loopback-only database. No trigger or production row was changed. The corrected red
run fails on the intended concurrency assertion, with cleanup working.

The full ten-command local gate passed from clean implementation commit
c27d531837ebbea587a88662983bfd37aed36d8f, with a clean tree afterwards: 2,525 API tests
(no skips), 158 shared tests and 732 web tests; lint, formatting, types and builds pass.
The only service change is the per-night row lock; no existing E2E or push assertion changed.

Postgres concurrency review followed the short-transaction and consistent-lock-order
checklist. The lock uses the existing night primary key, matching the vote path's night-first
order. Candidate GET commits before metadata lookups; Send commits before push delivery.
Different nights lock different rows. The lock is released by the existing transaction,
including rollback; no application-process mutex or additional service is introduced.

The complete available local E2E returned nonzero: Chromium 53 passed and one existing
shop-price-alert case timed out at its unchanged 60-second limit; Firefox 53 passed with
its documented dictation skip, and cron six passed. All movie-night invite/push/match and
AB1/AB2 cases passed. The Chromium failure occurred before the first test assertion or
browser page was created; native fetch calls were not instrumented in its retained trace.
The machine showed load averages 13.46/53.13/57.74 after the run; this is context, not proof
that load caused the timeout. Earlier progress messages incorrectly reported Chromium 54;
the final nonzero result was inspected and that claim explicitly corrected. No timeout,
retry, assertion, skip or product change has been made. Request-timing diagnosis in ignored tooling passed the unchanged isolated case in 22.3s:
login 918ms, Wanted writes 762/184ms, subscription 111ms, daily scraper 200 in 17,181ms;
the expected under-limit push and over-limit exclusion both held. No endpoint error or
movie-night lock was involved. This does not prove what held the original request or rule
out a preceding-state effect. The full preceding Chromium sequence was then run with the same timing observation; final
results below supersede this checkpoint. The original failure is retained rather than erased.

At that checkpoint, green local E2E and exact-head CI/production proof remained pending. Existing red CI
artefact/logs are retained in the ignored AB2 scratchpad; the AB2 report records the original
diagnosis and stop.


## Final verification and acceptance, 29 Oct

The full diagnostic Chromium sequence passed 54/54 from clean 7e465f1 (source/tests identical
to clean-gate c27d531). Its shop-alert request returned 200 in 24,609ms and the case passed
26.5s with the expected push; the preceding-state sequence did not reproduce the timeout.
Firefox 53 plus one documented dictation skip and cron 6 passed in the complete first run.
Verification exceeded the 45–60 minute allowance: the first local projects alone took 6.4/9.9/17.7 minutes,
then the timed diagnosis/full-sequence run and normal CI/deployment gates were still required.
The original timeout's exact delay remains unconfirmed; it is not claimed fixed by this PR.
No timeout, retry, skip, assertion or product change was made for it.

PR #120 head 7e465f19fa47357a54c29f4b78208bdbdded06cf passed CI 40854587486, all seven jobs.
Merge bf0eb365fe2eedf348f01871e1e09c9637c311a2 passed CI 40856393675, all seven jobs. Both runs include 2,525 API tests with no skips,
158 shared/732 web; Chromium 54, Firefox 53+one existing skip, WebKit 52+two existing skips,
cron 6. The skips remain Firefox dictation, plus WebKit's lost replay-answer and live open-page
match limitations from `apps/e2e/README.md`; no new skip. Migration reversal and the actual Railway image boot pass. Logs/proofs are retained
in the ignored repair scratchpad; no gate was weakened.

Production API health and web version both report bf0eb365fe2eedf348f01871e1e09c9637c311a2. Readiness: db: ok and
push/ai/ebay/tmdb/brave: configured. Unauthenticated stats: 401. These read-only receipts do
not claim a production invitation or real-device push; existing owner checks remain open.

- Per-night atomic first-seed decision: existing row lock before emptiness check, confirmed
  by deterministic two-connection database lock observation.
- Commit and rollback: both regressions pass; selected ids are unique and complete.
- Existing invite/push/match/access expectations: retained unchanged, full browser suites pass.
- Full verification/history/boundary: ten clean local checks, full available local E2E,
  exact-head PR/main seven jobs, API/web SHA/full readiness; 5a1ccad and approved planning
  commits preserved. No schema/API change, next sitting, AA10c, production invite, provider
  call, live data rewrite, hosting or credential change.

Final closing docs change no source/test/schema. Their exact-head seven-job CI and production
API/web SHA/full readiness are checked again before the session ends.
