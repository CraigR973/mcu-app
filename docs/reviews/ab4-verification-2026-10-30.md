# AB4 — approved 32px clearance: verification

30 Oct. **Implementation under verification; AB4 acceptance remains open.**
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
  coverage; the final clean full suite is still required below.
- Final browser cases cover Apple Home Screen, non-Apple generic standalone and no Apple
  signal, each in dark/light theme at normal/short portrait, zero-inset landscape and
  either side of the 1024px breakpoint. Insets are simulated for CSS geometry, never
  described as native blur or software-keyboard proof.
- Initial dark/light Search screenshots were inspected: existing solid themed Search
  surfaces, native-inset-plus-clearance geometry and intentional background dimming.
  Final actual-app header screenshots and final full gates remain pending.

No implementation check has failed so far. One exploratory read used apps/e2e/tests
instead of the actual specs directory; the path was corrected without changing any test.
The earlier diagnostic-only --skip-domain CLI rejection remains in the diagnostic report.

## Acceptance criteria

| Ledger criterion | Evidence / remaining owner work |
|---|---|
| Affected mode/version/re-add/theme/Search/launch versus resume | iPhone 16 Pro Max/iOS 27.0.1, original installed app not re-added, dark/Search-closed image, same-phone Safari sharp, original Home → close → Archive confirmed. Installed original bundle version, remaining theme/Search/resume observations open. |
| Evidence and cause before approved repair | Isolated installed AB4-1 reproduced blur at all three positions; AB4-2 owner measurement 32px, then explicit Approve 32px repair (#308). Exact internal iOS compositor not inspected. |
| Preserve login/deep links/back/offline/resume/safe areas/focus/dimming | No navigation/auth/service-worker/status metadata changes. New computed geometry/focus cases and full regression suite pending final clean run. |
| Actual app before/after, both themes/Search, full gates/CI/production | Original dark/Search-closed before captured. Actual affected-iPhone app after/light/Search, Archive-launch investigation and full final gate/CI/production remain open. Prototype or desktop tests do not close them. |

## Release boundary

Do not strike AB4 or call sitting 3 complete while its required owner criteria remain
unresolved. Keep the Archive-launch investigation separate and do not force Home on
foreground/navigation. Do not remove the original app without a fresh local pending/
blocked-change check, preservation of local-only work and the owner's exact decision.
Both isolated diagnostic deployments remain preview-only and must never be promoted.
