# AB4 — approved 32px clearance: verification

Updated 31 Oct. **AB4 shipped in PR #122 (df6824a); original production iPhone accepted.**
Craig approved the exact 32px repair (#308) and separately the original-app re-add (#309).
Native sample preview appearance/keyboard and re-added Home cold-launch/resume/no-problem
results are explicitly confirmed (#310). Craig now also confirms original production
Archive/Search sharp in both themes and keyboard normal. No AB4 owner criterion remains.
No launch rewrite, sitting 4 or AA10c is included.

## How the repair works

Before React mounts, one Apple standalone signal tags the document. A shared CSS value
adds the measured 32px below the existing top safe area for phone layout (under 1024px)
with a positive top inset. The same value feeds the existing header and Search padding.
Desktop, browser, Android standalone and zero-top-inset orientation receive no extra gap.
The header stays relative in its flex shell; the main scroll area shrinks naturally.
There is no schema/API, status metadata, navigation, auth, provider or hosting change.

Design decisions are the exact approved proposal in ab4-repair-proposal-2026-10-30.md.
The current flow is in docs/architecture-map.md. React review: one synchronous startup
marker, no added render state/effects/listeners, and existing focus/dimming retained.

## Baseline

The branch was clean before implementation. Fetched origin/main and the latest green
main CI 40891874070 identify f341d1084cc75863c7c00d3830a93347fc265436. Production API/web
were read back at that exact SHA with full readiness before product changes.
A fresh local disposable Postgres was created and migrated to 070, using only an ignored
local URI. No test/migration points at Neon and no live data or provider/push was exercised.

## Checks

- Web and E2E typechecks passed during implementation.
- Initial focused Chromium run: 3 cases passed, checking the actual bundle's targeting,
  both themes, positive/zero simulated inset, computed header/Search padding, overlap,
  horizontal overflow and Search focus/close. This preceded final breakpoint/short-screen
  coverage; final clean-source and full-browser results are recorded below.
- Final browser cases cover Apple Home Screen, non-Apple generic standalone and no Apple
  signal, each in dark/light theme at normal/short portrait, zero-inset landscape and
  either side of the 1024px breakpoint. Insets are simulated for CSS geometry, never
  described as native blur or software-keyboard proof.
- Initial dark/light Search screenshots were inspected: existing solid themed Search
  surfaces, native-inset-plus-clearance geometry and intentional background dimming.
  Final actual-app sample-preview header/Search screenshots were also inspected below;
  Native repaired sample and original production after are explicitly accepted below; release proof is recorded in the 31 Oct sections.

One exploratory read used apps/e2e/tests instead of the actual specs directory; the
path was corrected without changing any test. The earlier diagnostic-only --skip-domain
CLI rejection remains in the diagnostic report. The verification audit below records the
coverage-incomplete first API run and scratch-helper corrections.

## Acceptance criteria

| Ledger criterion | Evidence / remaining owner work |
|---|---|
| Affected mode/version/re-add/theme/Search/launch versus resume | iPhone 16 Pro Max/iOS 27.0.1, before-repair original app not re-added, dark/Search-closed image, same-phone Safari sharp, original Home → close → Archive confirmed. 31 Oct normal resume preserves Home. Repaired actual-app sample preview confirms all four theme/Search states, Home Screen: yes and normal keyboard; approved re-add now cold-launches/resumes Home with no login/sync/notification problems. Record installation-refresh resolution; historical bundle/internal target uninspected. |
| Evidence and cause before approved repair | Isolated installed AB4-1 reproduced blur at all three positions; AB4-2 owner measurement 32px, then explicit Approve 32px repair (#308). Exact internal iOS compositor not inspected. |
| Preserve login/deep links/back/offline/resume/safe areas/focus/dimming | No navigation/auth/service-worker/status metadata changes. New computed geometry/focus cases and clean local regression results are below; native preview and original production keyboard normal, plus original-app normal resume preserving Home, are owner-confirmed; production-after is accepted. |
| Actual app before/after, both themes/Search, full gates/CI/production | Original dark/Search-closed before captured. Repaired actual-app sample preview is owner-confirmed sharp in both themes with Search closed/open, Home Screen: yes and keyboard normal. Original launch resolved by approved re-add; old bundle/internal target uninspected. Original production after is now owner-confirmed sharp in all four Archive/Search/theme states, keyboard normal. Final seven-job PR CI passes at df6824a (41150581181), main df6824a/e04ba53 all seven jobs pass; PR #122 is merged and exact API/web SHA/full readiness pass. Production acceptance is an actual phone observation, not inferred from the sample. |

## Release boundary

Do not strike AB4 or call sitting 3 complete while its required owner criteria remain
unresolved. Keep the Archive-launch investigation separate and do not force Home on
foreground/navigation. Do not remove the original app without a fresh local pending/
blocked-change check, preservation of local-only work and the owner's exact decision.
All isolated diagnostics and actual-app sample previews remain preview-only and must
never be promoted.

## Clean source verification

Implementation source: `4f2a12b3dc13e05ff3282ab76c6eb82079414249`.
All ten mandatory commands exited zero from that clean commit, and the tree remained
clean. API lint/format/mypy, shared typecheck/build, web lint/typecheck/build and recursive
shared/web tests passed. Recursive tests: shared 159, web 736. E2E TypeScript also passed.

The first API run was coverage-incomplete: 2,540 passed and 9 collection-refresh cases
skipped because the pgserver URI used a Unix socket and the existing safety guard requires
an explicitly local hostname. No guard was changed. A second disposable cluster bound only
to 127.0.0.1:55439 was verified by server address and data directory, migrated to 070, and
the entire API suite reran: **2,549 passed, zero skips**. The 30 existing warnings are
Starlette deprecated status-code names, not failures. Derived-field tests ran.

Final local browser run uses the production build and fake outside services on a separate
throwaway Postgres, never Neon. Full command exited zero: Chromium **61 passed**; Firefox
**60 passed, one existing skip** (Firefox has no Web Speech API/dictation); jobs **6 passed**.
No local product test failed. The source was 4f2a12b and only documentation changed afterwards.
WebKit cannot run on this Mac; the seven-job PR CI must run it. The only permitted browser
skips are the three documented in apps/e2e/README.md; no new skip/retry/timeout weakening.
The final AB4 cases cover both themes, normal/short phone viewport, zero-inset landscape,
1023/1024px breakpoint, Apple/no-Apple/generic standalone, real computed geometry,
header/main overlap, Search focus/cancel and overflow. Insets are simulated, not native proof.

## Actual repaired-app phone preview (AB4-3)

A separate preview serves the actual application compiled from the implementation SHA,
with VITE_API_URL empty and same-origin static sample responses captured from the existing
E2E API seed. All 83 emitted application JS/CSS assets match the isolated build byte for
byte. Preview-only changes are the shell's dummy local identifiers, distinctive name/
launcher manifest, sample responses and local-only access policy. No real token, PIN,
account, collection, provider, production CORS or hosting setting is used or changed.

The sample auth response says Header preview/viewer. Fifteen GET/image fixture routes
support Home, Archive, You and Search presentation. Poster/backdrop fields are cleared;
write methods return 405 and unknown API reads return 503. A restrictive preview CSP allows
only same-origin connections. Search appearance/focus is in scope; searching arbitrary
sample data, auth, queue/offline/push or production behaviour is not acceptance from this
fixture site. The normal full E2E suite separately covers those application regressions.

Final preview: `dpl_EcQczpRG6CkZq1g5r6maaek4pFZE`, READY, preview target (null),
https://mcu-4nvhs84hp-craigr973s-projects.vercel.app/ab4-check.html.
The preceding unused build `dpl_3SA7AChLtPEcFP6dghBboDZX8r4R` was superseded solely to make
the installed icon open the status/launcher page instead of bypassing its standalone check.
Never promote either sample preview. The temporary share token is in chat, not Git;
refresh through Vercel get_access_to_vercel_url if needed. The launcher shows Home Screen
and actual safe-area values; Safari Share → Add to Home Screen must use Open as Web App on.
Keep the original MCU installed. Theme changes through the launcher's buttons or the
application's profile → sun/moon control. The manifest launches the diagnostic page,
so it cannot establish the original installation's launch target.

Protected preview smoke passes with service worker blocked and with the real worker active
and controlling a reload: Home/Archive/You, both themes, header/Search geometry, Search
focus/cancel, named sample manifest, source version, write 405, unknown read 503, zero page
exceptions and zero requests to another origin. Local blob artwork URLs are same-origin.
Inspected final dark Archive/light Search screenshots: solid surfaces, clear title/input,
expected extra space and intentional modal background dimming. Browser screenshots still
cannot establish native-iPhone sharpness, keyboard or iOS launch behaviour.

Vercel project identity, framework, Node version and deployment-protection configuration
were compared before/after and remained equal. Live API/web still serve exact baseline
f341d1084cc75863c7c00d3830a93347fc265436 and all readiness fields pass. No production repair
is shipped and no merged-SHA proof is claimed.

## Failures and corrections retained

- The first socket-addressed API run skipped 9 cases; full localhost rerun above passed
  all 2,549 without changing tests or guards.
- A scratch preview-capture helper had a missing parenthesis and stopped before starting
  its stack; corrected helper then captured the fake API successfully.
- A scratch database-identity guard initially compared PostgreSQL's text inet value
  (127.0.0.1/32) with a plain host. It stopped before migration; using PostgreSQL host()
  retained exact localhost/data-directory assertions, then the full run passed.
- A scratch preview network audit initially counted local blob artwork URLs as external;
  corrected it to compare parsed URL origins. Both protected preview smoke runs then pass
  with no external requests. No application assertions changed.
- Earlier exploratory path and diagnostic CLI errors remain recorded above/in the device
  checkpoint report. No product test failure, test change to obtain green, new retry or
  new skip is concealed.

## Review and stop point

[Draft PR #122](https://github.com/CraigR973/mcu-app/pull/122) carries the existing
seven-job CI for its exact review head, including WebKit, Postgres 17, migration reversal,
deployed-image boot and dependency audit. Read its current checks for the final head/run outcome; a feature-
branch push with skipped E2E is insufficient. All local results above refer to the clean
implementation source; later handoff edits are documentation only.

CI success does not release this draft or close phone acceptance. Await the pending
same-iPhone preview response (explicit Home Screen yes, Archive/Search in both themes,
keyboard normal), then address the original-installation launch/version/resume checkpoint.
Keep the original app installed; no removal is authorised. Any real-app re-add comparison
needs a fresh sync/local-state check and exact owner decision. AB4 is not shipped or
complete, and Group AB sitting 4 / AA10c have not started.

## CI navigation-readiness failure and correction

Initial review head 90dc73d passed all seven jobs in run 41039099660: Chromium 61,
Firefox 60 + one documented dictation skip, WebKit 59 + its two documented limitations,
jobs 6. All three new AB4 cases passed in WebKit.

The documentation-only head d8fb9cd then failed run 41039699513 in the new non-Apple
standalone WebKit case: page.reload raised Frame load interrupted at its first theme
reload. Six other jobs passed, as did Chromium 61, Firefox 60 + its existing skip,
WebKit's other 58 cases + two existing skips, and jobs 6. Do not substitute the earlier
green run for this failed head or label this final CI green.

The retained trace shows initial /dashboard document load returning before /auth/me
and the lazy Home module graph had settled. The test requested its first reload while
that startup was still in flight; it had no initial Home-readiness assertion. The exact
WebKit internal cancellation mechanism is unconfirmed. The test now requires the actual
collection-numbers list to be visible before the first theme/reload sequence. Every
existing geometry, targeting, theme, focus and overlap assertion remains; no timeout,
retry, skip, expected value or product code changes. This adds a stronger prerequisite,
rather than treating a browser document load as completed application startup.

Corrected focused Chromium/Firefox and exact-head CI results belong to the next review
head/checks. Native iPhone acceptance and the original launch checkpoint remain open.

PR metadata tooling also failed once on GitHub's deprecated classic-project GraphQL field;
a REST invocation first rejected an unsupported repository flag locally, then the fully
qualified REST update succeeded. No product/source/test effect from those metadata errors.

## CI offline-persistence readiness failure and correction

Head 14bfbb1 / run 41042161988 passed all three AB4 cases in Chromium, Firefox and
WebKit. The new Home-readiness prerequisite passed its full-engine verification. The
run nevertheless remains red: the existing Chromium lost-answer offline-replay case
read [] where it requires exactly [["queued",null]]. Six other CI jobs passed;
Chromium's other 60 cases passed, Firefox 60 + its documented skip, WebKit 59 + its two
documented skips, jobs 6. The failure is not removed by those passing results.

Its retained trace/error snapshot shows the distinction: the test waits for the offline
banner, which can appear immediately on the browser's offline event before Add commits
to IndexedDB. Its immediate queue read saw []; the later error snapshot already shows
Show change, which OfflineBanner renders only with pending > 0. Source inspection also
confirms asynchronous enqueue. This is a readiness race in the test, rather than evidence
that the header repair changed queue persistence. No offline product code is changed.

Add one exact-state persistence wait before the existing immediate queued-state assertion.
The original assertion remains byte-for-byte, as do every unconfirmed-state, server-copy,
lost-answer and no-duplicate check. The test still requires exactly one queued/error-free
write before returning online, then exactly one server copy through the lost-answer replay.
No expected value, timeout, test retry or skip changes; a queue that never persists still
fails. The other existing immediate assertions after the observed completed sync remain.

The next review head requires focused Chromium/Firefox AB4 + offline verification and
full exact-head seven-job CI. Keep all failed runs visible. This is the final corrective
full-CI attempt before the command's three-attempt stop if E2E fails again; do not keep
rerunning until it happens to pass. The production repair remains held at the iPhone/
launch checkpoint, with the original installation preserved and sitting 4/AA10c excluded.

## Final automated result and owner response, 30 Oct

Review head 97b36e41033b6531b9708674b9f4a8825a65d0c9 passed all seven jobs in
[CI 41044309324](https://github.com/CraigR973/mcu-app/actions/runs/41044309324).
Chromium 61, Firefox 60 + existing dictation skip, WebKit 59 + its two documented
limitations, jobs 6. All nine AB4 engine cases passed. Corrected focused AB4/offline
checks also passed five cases each in local Chromium and Firefox; E2E types passed.
Both earlier red runs and their readiness corrections remain above. No expected value,
timeout, test retry or skip was weakened. The original application repair remains 4f2a12b.

Craig now replies **“all are sharp”** to the actual repaired-app preview question asking
about Archive and Search in dark and light themes. Record this as owner-reported
sharpness for all four requested states on the same affected iPhone, using sample data.
The reply does not separately confirm the launcher's Home Screen status or Search
keyboard behaviour; those two short observations remain requested. Do not infer them,
or call installed-mode acceptance closed from a sharp result without the mode value.

The original MCU remains installed. Original installed bundle version, normal resume,
production after, and the original Home → close → Archive launch investigation remain
open. No removal/re-add or launch rewrite is approved. AB4 remains unshipped and unstruck;
sitting 4 and AA10c remain excluded. This observation update changes documentation only.
The verified remote review head stays 97b36e4 while these owner checkpoints are open;
local evidence-only commits can be pushed together before fresh exact-head final CI.

## Native preview confirmation, 30 Oct

Craig replies **“yes to both”** to the two explicitly remaining observations: the
Header Check status said “Home Screen: yes”, and tapping Search opened the keyboard
normally. Combined with the earlier four sharp Archive/Search/light/dark states, this
confirms the repaired actual-app sample preview's installed-mode appearance and Search
keyboard on the affected iPhone 16 Pro Max/iOS 27.0.1. These are owner observations;
desktop targeting/geometry tests are not substituted for them. Do not repeat these checks.

The original MCU installation is preserved. Its Home → close → Archive cold launch is
confirmed; normal resume after briefly switching apps remains unanswered. Ask that
non-destructive comparison and a fresh online check for pending/blocked changes, unfinished
Add/edit forms and Move tray contents. The tray uses localStorage key mcu-move-tray; an
old screenshot without a banner is not a fresh queue/local-state clearance. No removal
is approved. Any later removal/re-add proposal must preserve local-only work, explain
PIN sign-in/notification re-enablement/local-state loss, and obtain the exact owner decision.

Original installed bundle version, launch cause and production-after remain open. No
launch rewrite, merge, promotion or production deployment occurs. AB4 stays unstruck;
sitting 4 and AA10c have not started. This documentation-only update does not rerun the
application gate: source remains 4f2a12b and verified remote review head 97b36e4, all seven
jobs green in 41044309324. Accumulate local evidence commits for one final push and fresh
exact-head CI after owner checkpoints clear.

## Original resume and local-state preflight, 31 Oct

Craig reports “home remains” after original MCU Home → switch apps → return without
swiping MCU away. He answers “none to any of that” to the online check for waiting/Needs
attention changes, unfinished Add/edit forms and discs in the Move tray. Normal resume
is now observed and must not be labelled unanswered. No local work was reported to preserve.
This is owner-reported preflight, not direct inspection of all device storage.

Fresh public readback at 00:14 UTC returns manifest start_url / and web version f341d10;
retained JSON is scratchpad/ab4/launch-preflight-2026-10-31.json (ignored). Source commit
4cc207d changed start_url from /movies to / on 23 Oct. The original installed bundle
version and launch target remain uninspected. The retained-target explanation fits cold
Archive versus normal Home resume, but is not proven by that correlation.

A concrete one-time remove/re-add comparison and its costs/stop conditions are prepared
in the repair proposal's 31 Oct section. It requires a separate owner decision before
removal: about 3–5 minutes, possible PIN sign-in/notification re-enablement and loss of
local cache/settings. It excludes account/collection deletion and Safari website-data
clearing. No removal has been authorised or performed. Production still serves the old
header; this proposed comparison addresses launch only. Native repaired sample appearance
and Search keyboard acceptance remain confirmed, without substituting desktop tests.

This evidence-only update changes no product code or tests. Verified remote head remains
97b36e4 with all seven CI jobs green in 41044309324; local documentation is held for a
final push/exact-head CI after owner checkpoints. AB4 remains unshipped and unstruck;
sitting 4 and AA10c have not started.

## Original-installation comparison approved, 31 Oct

Craig chooses “Approve removal/re-add comparison” at the exact separate owner checkpoint.
Decision #309 records the production-root, original-installation-only scope, previously
clear online/local-work report, 3–5 minute cost, possible PIN sign-in, notification
re-enablement and local cache/settings loss. No approval repeat is needed. The phone
procedure is ready in the repair proposal; owner first-page/cold-launch/normal-resume
results and any login/sync/notification problems remain pending. Stop if new pending/
blocked work, unfinished forms or Move tray items appear before removal.

No app code, tests, navigation, manifest, account/collection data or hosting changes in
this turn. No removal/re-add outcome is claimed on the owner's behalf. No test rerun is
needed for this documentation-only approval record; git diff --check is the applicable
check. Review source/CI remains 97b36e4 / seven-job run 41044309324, with accumulated local
documentation held for final exact-head verification after the remaining checkpoint.
AB4 stays unstruck and unshipped; sitting 4 and AA10c have not started.

## Overall re-add report, 31 Oct — named results requested

Craig answers “all looks fine” to the approved original-app re-add comparison covering
first settled page, cold launch, normal resume and any login/sync/notification problems.
This is a positive overall report. It does not explicitly name Home or Archive, so one
clarification asks whether it means cold-launch Home, resumed Home and no problems. The
owner is not asked to repeat tests or reinstall again. No exact page result or internal
launcher cause is inferred before that answer. Historical pre-re-add evidence remains
Archive cold launch and Home on normal resume. The accepted repaired installed sample
preview appearance/keyboard observations remain closed; production-after remains open.

Documentation only: no code/test change or rerun, no push/merge/deployment. Exact remote
review CI remains 97b36e4 / 41044309324; a final documentation push requires fresh exact-head
CI before eventual merge. AB4 remains unstruck; sitting 4 and AA10c remain excluded.

## Named re-add results and final release candidate, 31 Oct

Craig explicitly replies “yes” to the clarification: re-added original MCU opens Home
after swiping away/reopening its icon, keeps Home after briefly switching apps, and has
no login/sync/notification problems. This closes the launch/resume checkpoint with actual
affected-phone evidence. Record the before/after as installation-refresh resolution,
not a code repair. The old bundle/internal saved target was never inspected; the specific
retained-/movies explanation remains an inference, not a proven iOS internal mechanism.
No further reinstall, launcher redirect or owner repetition is needed.

Native actual-app sample appearance/keyboard acceptance is also complete: four sharp
Archive/Search/theme states, Home Screen: yes, Search keyboard normal. This supports
releasing the exact approved header code after final checks. The production original
phone's header-after remains a post-deploy owner checkpoint; do not strike AB4 or call
sitting 3 complete until required after acceptance. No desktop test closes that criterion.

Fresh pre-release checks confirm origin/main f341d10, successful main CI 40891874070,
API/web exact f341d10 and db ok/all five readiness integrations configured. Vercel MCP
confirms intended mcu-app project/team/domain and unchanged protection. Product source
remains 4f2a12b and tests remain 97b36e4; all later changes are evidence documents. Review
finds one synchronous pre-mount marker, shared CSS, unchanged relative flex header and
focus/dimming/navigation/auth/worker behaviour; no extra React state/listeners or data
fetches. No unrelated work, dependency, schema, live data or hosting changes.

An exploratory read of non-existent apps/web/src/lib/version-check.ts returned file-not-found;
the existing registration helper was read successfully. This inspection error changed no
source. All earlier tool/test failures remain recorded above.

Push the accumulated docs once, run seven-job CI on that exact head, and record its result
in PR metadata/ignored evidence without manufacturing another doc-only head before merge.
The old 97b36e4 green run remains historical proof, not the new-head result. On success,
release the normal Git application build only, never a diagnostic/sample deployment,
verify exact API/web SHA and full readiness, then stop at production-phone after acceptance.
Sitting 4 and AA10c remain excluded.

## Final exact-head release and production proof, 31 Oct

Final candidate df6824af2b23b5052b3df220637da4c1a1ebf35a passes all seven jobs in
[PR CI 41150581181](https://github.com/CraigR973/mcu-app/actions/runs/41150581181).
API 2,549 with zero skips, shared 159, web 736; Chromium 61, Firefox 60 + existing
dictation skip, WebKit 59 + its two documented limitations, jobs 6. All AB4 cases pass.
The previous 97b36e4 run is historical, not substituted for this result. The product/test
tree comparison from 97b36e4 to df6824a is empty; only accumulated evidence docs changed.
The branch was clean, main was unchanged/green at f341d10, and the ready PR head exactly
matched the tested candidate before the fast-forward merge/push. GitHub marks PR #122
merged at 00:46 UTC with mergeCommit df6824a. Main CI also runs on that exact commit.

Normal Git deployments, not samples: Vercel dpl_iRi1C1z12uegi6jD4vmuvq5ZMCrj is READY,
target production, intended mcu-app project/team, main df6824a. Railway API deployment
3deecc8f-0df9-46ff-a130-f54de8d88f05 is SUCCESS at the same SHA. Protection/config/env
was only inspected, not changed. No diagnostic or fixture deployment was promoted.

At 00:47 UTC public API health and web version both return exact df6824a. Ready returns
status ready, db ok, push/ai/ebay/tmdb/brave configured. The read-only production Chromium
smoke exits zero: unauthenticated root settles on login, Name/PIN fields visible; served
JS contains the standalone marker and served CSS both shared clearance classes; captured
JS/CSS all HTTP 200, zero page errors, zero API writes. Screenshot inspected: intact dark
phone login, aligned fields/button, no clipping. Service workers are blocked in this
isolated smoke and no account sign-in was attempted. It proves public bootstrap and the
new build are served, not authenticated journeys, native blur, keyboard or phone cache
uptake. Native acceptance remains the owner, never desktop smoke.

Ignored evidence: ci-release-candidate-result.json/.log, release-candidate-preflight.json,
production-release-smoke.json and production-release-login.png in scratchpad/ab4. A completed
job log request while its parent workflow still ran reported logs unavailable; it was read
successfully after completion. GitHub's --required query reports no configured required
checks; all seven jobs were therefore checked explicitly, including the non-skipped PR
E2E job. No gate was weakened and no branch protection setting was changed.

The final owner question now asks the original production MCU icon reopened online,
Archive/Search sharp in dark/light and keyboard normal. No reinstall or repeat of the
resolved launch comparison is requested. Until this observed result, leave AB4 unstruck
and sitting 3 incomplete despite released code. Sitting 4 and AA10c have not started.
Subsequent handoff-only commits require the same exact-head main CI and served-SHA check;
record final runtime proof in the final response/CI metadata without creating an endless
new documentation head solely to name its own SHA.

## Original production acceptance and sitting 3 close-out, 31 Oct

Craig explicitly replies **“yes”** to: original MCU reopened online, Archive and Search
sharp in dark/light themes, Search keyboard normal. This closes the final production
phone criterion on the affected iPhone 16 Pro Max/iOS 27.0.1. No sample/desktop/token test
is substituted. Earlier approved re-add already resolved cold-launch Home, normal-resume
Home and no login/sync/notification problems. No repeated test or further reinstall.

Main CI [41151986202](https://github.com/CraigR973/mcu-app/actions/runs/41151986202) at
df6824a and [41152283641](https://github.com/CraigR973/mcu-app/actions/runs/41152283641)
at e04ba53 both complete successfully with exactly seven successful jobs. Neither E2E
job is skipped. PR #122 merge remains df6824a; e04ba53 is handoff documentation only.
All prior failures and corrections remain in this report; no expectation, timeout, retry,
skip or safety guard was weakened. Main was clean and unchanged at e04ba53 before this
close-out update. Final documents get a new exact-head seven-job main CI and exact API/
web SHA/full-readiness check before the final handoff; runtime evidence/PR metadata will
record that result without another commit merely to name its own SHA.

Criterion verdicts:

- Affected mode/baseline/launch/resume: met by actual iPhone report/screenshot, public
  served-version readbacks, pre-change no-re-add history, controlled cold and normal
  resume comparisons, and the explicitly approved re-add result. Historical old bundle/
  internal target remains uninspected; no exact vendor mechanism is claimed.
- Cause/repair checkpoint: met before code; installed-only top-edge effect reproduced
  independently of MCU, positioning-only alternatives failed, 32px measured and exact
  scope/cost approved. No launch repair invented after re-add resolved it.
- Preservation: source leaves navigation/auth/worker/status metadata unchanged; full
  regression gates cover login/deep links/back/offline, computed geometry/focus/overlap;
  phone confirms resume, keyboard and no login/sync/notification problems.
- Actual before/after and shipping: original dark/Search-closed blur screenshot and
  always-visible report retained; sample then original production all four requested
  after states are sharp with normal keyboard. Full clean local, exact PR/main CI,
  production SHA/readiness and read-only bootstrap checks pass.

The ledger is struck, architecture reconciled and owner actions updated. Craig’s AA1
launch and W1 appearance/keyboard are now resolved; Mark’s device, W3 real camera scan,
AB3 genuine push receipt, speech/live-assistant and AA10b/AA10c remain separate/open.
Group AB sitting 3 is complete. Sitting 4 and AA10c have not started; no automatic next
sitting is authorised.

Fresh pre-close-out readback at 10:27 UTC again confirms exact e04ba53 API/web SHA, all
readiness fields, manifest / and successful read-only login/served-bundle smoke with zero
page errors/API writes. Final close-out documents do not change the product/test tree.

Close-out tooling correction: the first Railway status read on 31 Oct used a shell without
the repo-required Node 20 PATH and returned command-not-found; its empty pipe then caused
a JSON decode error. Reran with the documented Node 20 prefix and pipefail; Railway reports
SUCCESS for close-out 8e47a3e and Vercel READY at the same SHA. No deployment/config/data
mutation or application failure occurred. This final audit note changes documentation
only and receives fresh exact-head CI/served-SHA verification before handoff.
