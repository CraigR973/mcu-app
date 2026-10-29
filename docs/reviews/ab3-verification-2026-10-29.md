# AB3 — Mark's addition notifications, verification 29 Oct

**Local verification complete; PR/CI/shipment pending.** Sitting 2 only; sitting 3 and
AA10c excluded. Craig approved all four pre-build picks (#306), including the exact additive
migration and optional clientRequestId/receipt contract, before any implementation.
Approved details: `ab3-owner-checkpoint-2026-10-29.md`. Current flow: `../architecture-map.md`.

## Mechanism and design decisions

Mark's verified UUID selects the sender independently of names/roles. His successful Add
crossing zero to one currently owned film/series/manual title queues each other active,
non-deleted profile's event. Downloads qualify. Extra copies/editions do not. A new Add
after all previous copies cease to be owned qualifies; restores/edits/imports/corrections
and old additions do not. No historical notification backfill.

Request/reference advisory locks and the resolved movie row lock serialise concurrent
add decisions. The add, audit, successful request receipt and outbox commit together.
The same actor/request/payload returns its original 201 response, even after removal;
a changed payload gets a distinct 409. Request IDs persist through offline queueing and
retry; existing unconfirmed-write readback is preserved. Old clients may omit the ID;
exact replay after an intervening removal needs the new ID.

A default-on preference controls the new category under existing quiet-hours/digest/device
rules. Old/cached answers show Unavailable rather than inventing a value. Immediate delivery
runs after commit. A transport exception cannot undo the addition; ordinary delivery failure
keeps the existing failed-status semantics. Queued rows are claimed with FOR UPDATE SKIP LOCKED
so concurrent API/cron delivery cannot send the same row simultaneously. Preference creation
uses an upsert to avoid a recipient's first-preference race. No delivery claim is a promise of
exactly-once physical receipt after an ambiguous external push-service response.

Migration 070 adds the preference, empty receipt table and new category to the existing
outbox constraint, retaining every prior category. Guarded read/backup grants withhold
credentials. No existing catalogue or history rewrite, hosting/credential change, real
provider/model request, fabricated production add or push. Persistent receipt storage and
lock-screen disclosure of title/year were included in the owner's approved cost/tradeoffs.

## Acceptance evidence so far

| Criterion | Evidence / remaining |
|---|---|
| Owner checkpoint | Four explicit approvals, #306, before code. |
| Correct trigger, recipients and exclusions | API regressions cover owned/extra/reacquisition/download/manual/series, rename/role, other viewer, inactive/deleted recipients, disabled preference, non-add mutations, validation and duplicate refusal. |
| Atomicity, replay and concurrency | Real Postgres tests force two-connection commit/rollback, same/different request IDs, two actors, preference creation and delivery claim races. A separate real-commit test injects transport failure and replays from a fresh session. |
| Preference and migration | Head → base → 069 → head → base → head passed on disposable Postgres. Pre-070 preference row gained true. Both mcu_readonly/mcu_backup can read the new preference/receipt table and cannot read profiles.pin_hash or refresh_tokens (catalogue privilege checks only). |
| Browser and fake push | Four new Chromium journeys passed: 375 px light/dark settings persistence, approved wording, old-response Unavailable, Mark's actual add screen, stable client request ID, decrypted Craig push/body/URL, no Mark push, retry/edition silence and title destination. |
| Full gate / CI / deployment | Pending below. Genuine later addition and Craig's real-phone receipt remain owner acceptance. |

The preflight main was clean at 588e552b2a93f140fc603bf51ae80c348cc0f835 after fetch.
Main CI 40858327603 succeeded; production API/web served that exact SHA with full readiness.
A read-only live query verified both profile IDs and active/deleted state, selecting no
credentials. These are baseline facts, not AB3 shipment proof.

## Failures and corrections (including first-attempt fixes)

- Disposable Postgres's first initdb failed under the ambient locale; explicit
  LANG/LC_ALL=en_US.UTF-8 created the replacement scratch server. No live URL was used.
- Two guarded edit scripts stopped on ambiguous match-count assertions. Scoped patches
  completed the intended changes; review removed one redundant movie-row lock statement.
- Initial lint found import ordering/unused imports and line lengths. Formatting and
  scoped corrections resolved them without suppression comments or gate changes.
- First Postgres add test returned 500: migration 070 initially omitted the existing
  ck_notifications_category constraint extension. Added the approved category while
  retaining all old categories; scratch downgrade/re-upgrade and subsequent tests passed.
- New test inputs initially used an invalid duplicate reason and represented Binned as
  a listing status. Corrected the fixtures to the existing another_copy reason and
  soft-deleted in_collection representation; no product ownership rule changed.
- Six existing sync tests caught an unnecessary bypass of lost-response readback for
  keyed creates. Restored the existing readback path; every old assertion remains intact.
- A subsequent client test timed out while host load reached 177; imports/other tests
  also took tens of seconds. The same 25 focused tests then passed with one worker and
  unchanged timeouts/assertions. Host contention is evidence, not proof of sole cause.
- New delivery-failure API test reused expired fixture actors after the intentional
  delivery rollback; the real next request loads fresh actors. Rehydrated the shared
  fixture before the retry and added a separate fresh-session real-commit regression.
- That new regression initially compared naive-UTC Python models with receipt-parsed
  aware-UTC models. It now checks the exact serialized API payload, which is the approved
  replay contract; no timestamp or response-field assertion is relaxed.

- First clean-tree full gate (9811f3b): API lint/format/typecheck passed; pytest stopped
  with 2 failed, 2,522 passed and 25 skipped. The committed OpenAPI snapshot had not yet
  been regenerated for the owner-approved fields/category. The scratch roles were created
  after the original test database migrated, leaving earlier photo grants absent. The
  synchronous trigger tests could not use the async-driver URL and skipped. Regenerated
  only the approved schema delta, created a fresh database with roles present before
  migration, and switched the test URL to plain postgresql so both drivers can connect.
  The first export command omitted PROCESS_ROLE=web and its process-role guard refused;
  reran the documented web-role export. No snapshot test, grant assertion or skip rule changed.

## Clean-tree full gate and shipment

Clean local source/document tree **8fee563ec0c74f5cd6ca70c56b9c3dd739c66f88** passed all ten
batch-verify commands. Final API run: **2,549 passed, zero skips**. Shared **159**, web **736**;
API lint/format/mypy, shared typecheck/build and web lint/typecheck/build passed. Eleven
existing web fast-refresh warnings remain outside changed screens; no lint errors.

The second API invocation had 2,540 passed and nine collection-refresh skips because the
socket-only DSN had no hostname. The final localhost-labelled socket URL was verified by
current_database()/inet_server_addr() to reach the same disposable database, and ran all
nine cases without changing their localhost safety guard. All derived-field tests ran.

Full local E2E on that same clean tree: Chromium **58 passed**; Firefox **57 passed + one
existing dictation skip**; jobs **six passed**. WebKit cannot run on this Mac and must run
in CI; its two pre-existing documented limitations remain visible. No new skips/retries.
The 375 px light/dark settings screenshots were visually inspected: approved wording,
wrapping, switch alignment and contrast; no horizontal overflow. Mark's screen add,
decrypted fake push, retry/edition silence and title destination passed in both browsers.
React best-practices review covered stable request identity, hook placement, switch semantics,
old-response state and mutation handling. Local source review found no remaining blocker.

Fresh origin/main remained 588e552, with latest CI still green before PR publication.
PR/merge exact-head seven-job CI and production SHA/readiness remain pending. A genuine
later addition and Craig's real-phone receipt remain owner acceptance. No next sitting.
