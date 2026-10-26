# AA7 profile pictures — verification, 25–26 Oct 2026

## Result

AA7 shipped in [PR #111](https://github.com/CraigR973/mcu-app/pull/111), merge
`e6e5e1666819ce14e72bc047b15e32e3372436e6`. All seven PR CI jobs passed. Production API and web serve that
SHA; db is ready and all integrations are configured. AA11 implementation has not started;
its four-state story must be signed off first. Sitting 5 is excluded.

## Agreed acceptance, verbatim

### AA7 — Profile pictures 🟡
- **4.** An uploaded photo (answer 3). A person's picture shows wherever their initial does now (top bar, You,
  movie night, activity), the initial when there is none. If uploaded: stored in Postgres as copy
  photos are, resized, size-capped. Migration granted as above.
- Tests. Gate green.

## How it works

Each person chooses a photo or Use my initial on You. Only that person can replace/remove
it; both signed-in people can read it. One row per person in `profile_photos` keeps the
bytes separate from credentials. The existing disc-photo processor orients, resizes and
re-encodes uploads, stripping EXIF. Inputs are capped at 12 MiB; the stored image is capped
at 300 KiB in both the route and database. No provider, service, hosting or credential
change is involved.

The top bar, sidebar, You, movie-night participants/personal history and activity use one
avatar component. It fetches private bytes, creates and releases an in-memory object URL,
and falls back to the initial if there is no picture or the read/decode fails. Activity now
carries a stable actorId; older offline answers still parse with a null id and show initials.
Mutable photo reads, including 404s, are no-store and bypass the worker's offline API cache.

Migration 068 creates only the photo table, without a backfill. The guarded grants add it
to mcu_readonly and mcu_backup; local catalogue checks prove both can read the table and
cannot read profiles.pin_hash. No credential column is selected to test that boundary.
The architecture map records this flow.

## Local evidence, clean source 318f07ca6d0d9e7e318708d5466244c525a8b4a5

| Criterion | Evidence | Result |
|---|---|---|
| Own upload, replace, remove; other person reads | Real API and Postgres, both roles; foreign-id writes refused; bad input keeps old bytes | Pass |
| Re-encoding, bounds and private delivery | Real images, dimensions, JPEG/EXIF checks, input ceiling, private/no-store headers | Pass |
| Photo across named screens, initial fallback | Chromium and Firefox: both people, top bar/You/activity/night/sidebar, reload, removal; unit error and URL cleanup cases | Pass |
| Migration and grants | Local 068 downgrade/reapply with both roles; photo SELECT allowed and PIN SELECT withheld | Pass |
| Full local batch gate | All 10 commands, real throwaway Postgres | Pass |

Full API: 2,473 passed, nine collection-import cases skipped because their guard requires a
localhost hostname and this throwaway server uses a Unix socket. Derived-field trigger tests
ran. CI's Postgres 17 must run all database cases without those skips.
Shared: 155 passed. Web: 693 passed. API lint/format/mypy, shared typecheck/build and web
lint/typecheck/build passed. Lint reports 11 existing warnings and no errors. E2E typecheck
also passed. Chromium: 37 passed. Firefox: 36 passed, one existing documented dictation
skip. Cron jobs: six passed. Local WebKit cannot run on macOS 13; PR CI must run it, keeping
only the two previously documented platform skips. All outside services were faked.

The new photo case passed for both people in both available browsers. The 375 px Mark/You
and 1,280 px Craig/You screenshots were visually inspected: upload controls and photo avatars
fit, navigation remains usable and the sidebar shows the picture. The photo is a synthetic
image, not either person's real portrait. Four Chromium screenshots were retained under
`scratchpad/aa7-verification/` (ignored); the browser reports retain their own screenshots.

The before-production read-only check found revision 067, 1,943 films, 3,797 copies,
1,591 watch rows and nine nights; no photo table yet. Both read roles could read neither
PIN hashes nor night invite tokens. No production upload or live provider run was made.

## Failures and decisions, including fixed first attempts

- 25 Oct's initial pgserver start refused invalid locale settings. UTF-8 locale settings
  fixed the disposable local server start; production was never a test database.
- The new activity avatar initially failed typecheck because activity JSON had names only.
  Stable actorId now ships with its shared schema and old-cache fallback, with API assertions.
- The new avatar tests failed because they replaced the URL constructor with a plain object,
  making happy-dom reject the image source. Three runs triggered the group stop. Craig
  explicitly resumed on 26 Oct. A diagnostic reproduced the cause; spying only on the two
  object-URL methods fixed the fixture. Every image, fallback and cleanup assertion remains.
- Craig approved exactly two new pinned paths on 26 Oct: `/api/v1/profile-photos/me`
  (PUT/DELETE, own only) and `/api/v1/profile-photos/{profile_id}` (authenticated GET).
  Exact-set equality, every old path and all existing checks remain. OpenAPI was regenerated.
- The first full formatting check found migration 068 unformatted; it was formatted and the
  complete local gate passed from the clean committed tree.
- The first screenshot-inspection attempt raced the full runner clearing its output. The
  final full-run screenshots were inspected and copied outside the runner's output.

Design choices: separate photo storage, caller-only writes, reuse of the disc image pipeline,
private mutable reads, and initials for old offline answers whose actor id is unavailable.

## Limits and next checkpoint

Real iPhone photo selection/cropping is unverified. No signed-in production upload is claimed.
Existing owner-only device/push/speech acceptance remains owner-held. No AA10b eBay run or
collection refresh was started. AA11 waits for its story sign-off; sitting 5 stays unstarted.

## Shipment evidence, 26 Oct

PR source `7f17dfffd7b3322308df40ebba43397a2606750f`, CI run 40299605767:
all seven jobs passed, including Postgres 17, full migration reversal, the deploy image,
web build, audits and all browsers/jobs. The source tree matches the locally verified code;
only evidence/status/decision documentation followed the clean local gate.

The GitHub connector refused PR creation with 403 (integration access); the existing gh
CLI created the PR without any credential or permission change. The PR was attached to
the chat. The same authorised CLI performs its merge.

Production health and web version report the merge SHA, readiness is db ok with push, AI,
eBay, TMDB and Brave configured. Read-only catalogue/row-count results are recorded at close-out.
No signed-in production photo upload was made; anonymous photo reads/writes are checked.
The close-out documentation commit is followed by a final exact-SHA CI/deployment check.

PR CI totals: API 2,482 passed with zero skips; all 16 derived-field trigger tests ran.
Shared 155; web 693. Chromium 37; Firefox 36 plus its documented dictation skip;
WebKit 35 plus its two documented platform skips; cron six. No new skip was introduced.
Read-only production proof: revision 068, zero photo rows, catalogue/watch/night counts
unchanged from the before snapshot. Both roles read profile_photos and cannot read PIN hashes
or night invite tokens. Anonymous GET, PUT and DELETE each return 401.
