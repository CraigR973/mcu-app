# Movie-night seeding race — approved repair, 29 Oct

Craig approved the separate race fix in chat after the red-CI stop. The original AB1/AB2
implementation and approved planning history are preserved. Local handoff 5a1ccad is kept
on this repair branch and will go through the same PR/CI; it has not been pushed to main.
Starting main source cf28806 is red (40793684816); this fix is separate from AB2 and does
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

## Verification and failures

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
that load caused the timeout. Earlier progress messages incorrectly reported Chromium54;
the final nonzero result was inspected and that claim explicitly corrected. No timeout,
retry, assertion, skip or product change has been made. Request-timing diagnosis in ignored tooling passed the unchanged isolated case in22.3s:
login918ms, Wanted writes762/184ms, subscription111ms, daily scraper200 in17,181ms;
the expected under-limit push and over-limit exclusion both held. No endpoint error or
movie-night lock was involved. This does not prove what held the original request or rule
out a preceding-state effect. One full Chromium sequence with the same timing observation
will check that remaining concern; the original failure is retained rather than erased.

Complete green local E2E and exact-head CI/production proof remain pending. Existing red CI
artefact/logs are retained in the ignored AB2 scratchpad; the AB2 report records the original
diagnosis and stop.
