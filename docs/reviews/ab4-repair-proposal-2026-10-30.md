# AB4 — measured header clearance: proposed repair

30 Oct. **Proposal awaiting Craig's approval. No app repair implemented.**
This is the owner checkpoint before changing app header/Search/iOS chrome.
Sitting 4 and AA10c are excluded. AB4 and its real-phone acceptance remain open.

## Evidence and cause

Craig's iPhone 16 Pro Max runs iOS 27.0.1. The original installed app blurs header
content in dark theme; the same screen in Safari is sharp. The original screenshot
captures Search closed and softening of the app title/icon/upper profile photo below
sharp system clock/battery icons.

The isolated AB4-1 page first looked sharp in browser mode (Home Screen: no). Its
corrected installed run reports Home Screen: yes, with Relative, Sticky and Fixed all
blurry. The sample has no MCU code, data, login, cache or header blur declaration.
This reproduces installed-mode top-edge rendering independently of the app and shows
that changing positioning alone does not remove it on this phone.

The separate AB4-2 clearance test changes only additional top space. Craig now reports
**32px** in response to the smallest-sharp-value request. Treat this as the owner-reported
diagnostic measurement, not an approval to build. The exact internal iOS compositor is
not inspected. Light-theme and Search results were not separately supplied. The full
app's updated rendering and installed bundle version are not yet verified.

## Recommended scope for approval

Add **32 CSS pixels below the existing top safe area**, before phone-header controls.
Use the same extra clearance for the Search sheet's own controls. Keep a solid themed
background behind the empty area, so the system effect can fall over that area instead
of the title, assistant button, avatar or Search input.

Apply the clearance only when Apple's `navigator.standalone` signal is true, the phone
layout is active (below the existing 1024px desktop breakpoint), and the top safe-area
inset is non-zero. It returns to zero when the top inset is zero, including the usual
landscape case. Browser tabs, Android installations and the desktop layout get no extra
clearance. Do not use the generic standalone media query alone, which includes Android.

**Scope cost:** this deliberately covers Apple Home Screen apps using the phone layout,
including older Apple OS versions. It is not an iOS-27-only detector. It consumes 32px of
vertical content area wherever it applies. No new device setting, server preference,
API/schema, account, provider, fee, hosting configuration or credential is proposed.

The gap is a shared chrome value, set before the app renders and used by the existing
header and Search padding. Keep the existing relative header, flex layout, safe areas,
theme colours, keyboard focus, modal dimming, z-index order and bottom navigation.
The main scroll area naturally becomes 32px shorter; controls and content must not overlap.
Login screens and unrelated dialogs do not acquire the gap.

## Alternatives considered

| Option | Evidence / cost | Recommendation |
|---|---|---|
| 32px shared clearance | Owner measured this in the installed test; costs 32px of visible content | Proceed after approval |
| Fixed/sticky header alone | Both still blurred in the installed test | Reject as a demonstrated repair |
| Change status-bar/viewport metadata | Not tested here; could alter installation, themes and safe-area behaviour | Do not combine with this repair |
| Version-based targeting or new device setting | Adds a detection/configuration decision beyond the measured condition | Keep out of this narrow repair |

These are the proposed design decisions Craig can overrule: one measured 32px value;
one value for header and Search; Apple-standalone/phone-layout/non-zero-inset targeting;
older Apple installations included; no status-bar metadata, positioning or launch rewrite.

## Verification and release boundary

- Prove the targeting matrix and actual computed geometry at positive and zero safe-area
  insets, phone and desktop widths, both themes and Search closed/open. Simulated browser
  conditions verify layout only; they do not render the native iOS blur.
- Exercise Search focus and keyboard paths, viewport changes/rotation, scrolling, short
  screens, back/deep links, login return, offline behaviour and normal page resumption.
  Retain existing route/access inventories and expectations; no weakening to reach green.
- Run every `batch-verify.md` command and the normal browser/jobs E2E against disposable
  Postgres, then exact-head seven-job CI and production SHA/readiness under the project
  procedure. Do not point tests at production. Record every failure and repair.
- Obtain actual affected-iPhone app before/after in both themes and Search states.
  The 32px diagnostic result is not full-app acceptance; keep unobserved criteria open.
  Do not strike AB4 or call the sitting complete while required acceptance is unresolved.

If the full app still blurs, stop and investigate the difference; do not keep adding
unmeasured pixels or label the CSS tests as phone proof. A source rollback removes the
marker/gap without a database or hosting rollback.

## Launch remains a separate device checkpoint

The original app still opens Archive after Craig deliberately leaves it on Home,
swipes it away and reopens its icon. The old manifest used /movies; current production
uses /. A retained installation target is consistent with that evidence, but has not
been directly read. No navigation or foreground-to-Home handler is proposed.

After this repair decision, plan the real-app re-add comparison separately. Before any
removal, verify the original phone is online with no pending/blocked local changes and
preserve anything else stored only on it. The app's offline banner names pending changes
and offers Show changes/Sync now, but its absence in an old screenshot is not a fresh
local-state clearance. Removal can require PIN sign-in and notification re-enablement
and can discard local state; obtain the owner's decision on that exact action then.
Do not treat approval of the 32px repair as approval to delete/re-add the installation.

## Current source and production baseline

30 Oct: fetched origin/main remains f341d1084cc75863c7c00d3830a93347fc265436; latest main
CI 40891874070 succeeded. Public API health and web version both serve that exact SHA;
readiness reports db ok and all reported integrations configured. The existing branch
fix/ab4-iphone-diagnosis started this update clean and holds only diagnosis documents
and isolated diagnostic sources. No full app gate or new deployment is claimed for this
proposal. Detailed observations and both diagnostic sources/deployments remain in
ab4-device-checkpoint-2026-10-29.md and ab4-diagnostic-2026-10-29/.
