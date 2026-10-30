# AB4 — approved 32px clearance: verification

30 Oct. **Approved repair implemented; AB4 owner acceptance remains open.**
Craig approved the exact measured repair (#308), including older Apple Home Screen
phone layouts and the 32px screen-space cost. Original-app removal/re-add, launch
rewrites, sitting 4 and AA10c remain excluded.

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
  actual native-iPhone after and production release remain open.

One exploratory read used apps/e2e/tests instead of the actual specs directory; the
path was corrected without changing any test. The earlier diagnostic-only --skip-domain
CLI rejection remains in the diagnostic report. The verification audit below records the
coverage-incomplete first API run and scratch-helper corrections.

## Acceptance criteria

| Ledger criterion | Evidence / remaining owner work |
|---|---|
| Affected mode/version/re-add/theme/Search/launch versus resume | iPhone 16 Pro Max/iOS 27.0.1, original installed app not re-added, dark/Search-closed image, same-phone Safari sharp, original Home → close → Archive confirmed. Installed original bundle version, remaining theme/Search/resume observations open. |
| Evidence and cause before approved repair | Isolated installed AB4-1 reproduced blur at all three positions; AB4-2 owner measurement 32px, then explicit Approve 32px repair (#308). Exact internal iOS compositor not inspected. |
| Preserve login/deep links/back/offline/resume/safe areas/focus/dimming | No navigation/auth/service-worker/status metadata changes. New computed geometry/focus cases and clean local regression results are below; native keyboard/resume observations remain owner work. |
| Actual app before/after, both themes/Search, full gates/CI/production | Original dark/Search-closed before captured. Actual affected-iPhone app after/light/Search, Archive-launch investigation and production release remain open. Exact-head CI is on draft PR #122; the actual repaired-app sample preview is available below. Prototype or desktop tests do not close them. |

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
