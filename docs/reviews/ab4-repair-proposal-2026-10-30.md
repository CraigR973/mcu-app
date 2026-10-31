# AB4 — measured header clearance: proposed repair

30 Oct. **Craig approved the exact 32px scope (#308); implementation authorised.**
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
diagnostic measurement; the later explicit “Approve 32px repair” authorises this scope. The exact internal iOS compositor is
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

## Original-installation comparison, 31 Oct — approved (#309), Home results confirmed (#310)

Craig confirms the original MCU preserves Home on normal resume after briefly switching
apps without swiping MCU away. He separately reports no pending/Needs attention changes,
unfinished Add/edit forms or Move tray contents while online. These are fresh owner
observations, not an agent inspection of the phone's storage. Cold launch after deliberately
leaving Home still returns Archive. Source history shows the 23 Oct change from /movies
to /; 31 Oct 00:14 UTC public readback confirms start_url / and web f341d10. The original
installed bundle version and internal launch target have not been read. A retained old
installation target is consistent with the cold/resume distinction, not a proven cause.

**Recommendation:** approve one removal/re-add comparison of the original MCU Home Screen
app using https://mcu-app-fawn.vercel.app/ in Safari. Replacing navigation with a forced Home
redirect is rejected because normal resume already works and the launcher target remains
unconfirmed; it could disrupt deep links, login returns and page resumption.

Scope and cost: about 3–5 minutes, possible PIN sign-in and notification re-enablement,
and possible loss of local caches/settings. The owner reports no queued writes, drafts or
Move tray items to preserve. This action targets only the phone installation; no server
account/collection deletion, Safari website-data clearing, hosting change or sample-preview
promotion. Approval of the 32px repair does not authorise this separate action.

After explicit approval, the owner performs the comparison:

1. If any new pending/blocked change, unfinished form or tray item appears, stop and
   sync/preserve it before removal. Ensure the PIN is available and note whether push is enabled.
2. Remove only the original MCU Home Screen app. Keep the separate MCU Header Check preview.
   Do not clear Safari website data or delete anything through MCU's account/collection UI.
3. Open the production root URL in Safari and add it to the Home Screen as a web app.
   Open its icon, sign in if requested and observe the first page after sign-in settles.
4. Select Home, swipe the app away, reopen its icon and report Home or Archive. Then
   select Home, briefly switch apps and return without swiping it away; report the resumed page.
5. Restore notifications if previously enabled. Stop and report any login/sync/notification
   problem; do not repeat reinstall attempts or change navigation without new evidence.

If the new installation cold-launches Home and resumes normally, record the before/after
as an installation-refresh resolution; do not invent a code repair or claim the exact
internal iOS mechanism was inspected. If it still cold-launches Archive, retain the open
launch criterion and investigate the new evidence. The production header remains unrepaired
at this point; the installed sample preview's accepted sharpness is a separate result.

### Owner decision, 31 Oct

Craig explicitly chose “Approve removal/re-add comparison” in response to the exact
one-time scope and 3–5 minute/PIN/push/local-cache costs above. This resolves the separate
approval gate (#309); do not request it again. The earlier online/no-local-work report
stands, with a stop if new work appears. The owner performs the phone steps above and
reports first settled page, cold launch, normal resume and any login/sync/notification
problem. No result or production header acceptance follows from approval alone.

### Named result, 31 Oct

Craig explicitly confirms yes: cold-launch Home, resumed Home, no login/sync/notification
problems. Record installation-refresh resolution (#310), without claiming the old saved
target or exact internal iOS mechanism was inspected. No launch/navigation repair or
further reinstall is needed. Native repaired sample appearance/keyboard is accepted;
production-phone header-after remains for deployment. Sitting 4 and AA10c remain excluded.
