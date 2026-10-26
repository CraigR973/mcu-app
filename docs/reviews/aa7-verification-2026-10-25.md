# AA7 verification and stopped handoff — 25 Oct 2026

## Resumed 26 Oct

Craig approved the two route additions and then explicitly resumed the stopped run.
The earlier stop below is historical. The avatar issue was the new test replacing the
URL constructor with an object, so happy-dom rejected the image URL; spying only on
createObjectURL/revokeObjectURL preserves real URL validation. The original image-display,
error-fallback and cleanup assertions remain. No failing expectation was loosened.

Activity now has actorId beside actorName, with nullable/default-null shared parsing for
older offline answers. Both photo and activity API checks pass: 23 tests. All 10 focused
avatar/cache checks pass. Web and e2e typechecks pass. Migration 068 reverses/reapplies on
local throwaway Postgres; both read roles can read photos and cannot read the PIN hash.
Private photo reads (including missing pictures) are no-store and excluded from the offline
cache. Browser and full-gate verification are in progress; nothing has shipped yet.

## Original stop on 25 Oct

AA7 profile pictures are implemented locally on `feat/aa7-profile-pictures` but are not
verified, pushed, merged or deployed. AA11 has not started. Sitting 5 has not started.
The stop is `docs/agent-commands/group-start.md`: three runs of the same avatar check
failed. Craig approved the two route additions on 26 Oct; that narrow update is complete.

## Scope and acceptance, verbatim

### AA7 — Profile pictures 🟡
- **4.** An uploaded photo (answer 3). A person's picture shows wherever their initial does now (top bar, You,
  movie night, activity), the initial when there is none. If uploaded: stored in Postgres as copy
  photos are, resized, size-capped. Migration granted as above.
- Tests. Gate green.

## Implementation prepared

- Each person can upload, replace or remove only their own picture from You.
- One photo per person lives in a separate Postgres table, away from profile credentials.
  Migration 068 creates it without a backfill and grants the two read roles access to it.
- Existing disc-photo processing orients, re-encodes and resizes the photo. Input is capped
  at 12 MB; stored data is capped at 300 KiB in the route and database constraint.
- Authenticated GET returns JPEG bytes with private/no-store headers. The browser creates
  an object URL. The component is intended to fall back to an initial and revoke URLs on
  replacement/unmount. Rendering is currently failing the unit check below.
- Top bar, sidebar, You, night participants and personal history use the shared avatar.
  Activity integration is unfinished because the current activity JSON has a name but no
  actor id. This is an implementation gap, not a reason to cast away the type error.
- The new write responses are empty 204 responses, and the new read is binary; no new JSON
  response is introduced.

## Decisions made within AA7

- Separate photo table rather than adding image bytes to every authenticated profile read.
- Caller-only writes, with no administrative route for changing the other person's photo.
- Existing image pipeline and rectangular images cropped visually into round avatars.
- Private mutable reads with no-store, rather than a public image URL.

## Checks and failures

- Clean starting main: `f1e174e2b7fa2376a1ac9ad87b38d1b109f21864`.
- Starting main CI: run 40230927112, success, before the branch began.
- Initial disposable pgserver start failed on invalid locale settings. Retried with
  `LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8`, successfully, using `/tmp/mcu-aa7-pg`.
- Local migration upgrade from empty through 068 passed, only on disposable Postgres.
- New API suite: 5 passed, against disposable Postgres. Covers both roles' own writes,
  cross-person read, uneditable foreign ids, replace/remove, invalid input retaining the
  previous photo, anonymous access, bounds, image dimensions and EXIF removal.
- The role-grant test is conditional on the roles existing; these roles were not created
  for this local run. Production catalogue privilege checks have not run.
- Ruff check of the changed Python source passed; the router/test were formatted.
- Web typecheck failed: ActivityFeed reads `event.actorId`, absent from ActivityEvent.
- Focused frontend run: 29 passed, 2 failed. Existing You and AppLayout tests passed;
  the new avatar tests failed because no image element appears after the mocked byte read.
- A second run of the avatar file reproduced both failures. A third, diagnostic run of
  the image-rendering case reproduced one failure. The group stopped at that point.
  The query state showed successful Blob data; no root cause has been established.
- Full batch gate, migration reversal, image build, browser e2e, manual visual inspection,
  PR CI, production smoke and exact-SHA deploy verification have NOT run.

## Pending decisions and next work

Craig approved adding ONLY `/api/v1/profile-photos/me` (PUT/DELETE, self only)
and `/api/v1/profile-photos/{profile_id}` (authenticated GET) to the exact pinned route
inventory on 26 Oct. The inventory now includes exactly these additions and the generated
OpenAPI snapshot was refreshed. A comparison found no existing path changed or removed;
exact-set equality and all existing checks remain. All 16 health/snapshot tests passed.
This approval did not authorise resuming debugging past the three-attempt stop.

After Craig authorises resuming past the three-attempt stop, preserve this checkout and
its edits; resolve the avatar failure and activity identity properly. Also ensure the
service worker does not persist these no-store photo reads: its current matcher broadly
caches API GETs. Add focused coverage for that exclusion. Temporary console debug instrumentation was removed; the diagnostic log remains in
`/tmp/mcu-aa7-debug.log`. Then complete all gates, role-grant/credential-withholding checks,
architecture-map update and phone-width visual inspection. Create one AA7 PR, attach it,
wait for all CI jobs including e2e, merge, verify both production SHAs and readiness,
then close out the AA7 ledger and session docs.

Only after AA7 is shipped and local main is clean: inspect current loans, present AA11's
short four-state story to Craig, and STOP for sign-off before implementation. The intended
story is asked for → out → back, not shelved → shelved, with needed-by date, Mark's push,
either person recording return, and Mark's put-back list confirming/changing the shelf.
Do not start sitting 5.
