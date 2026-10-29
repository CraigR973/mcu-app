# AB4 — affected-iPhone evidence checkpoint

29 Oct. Sitting 3 is authorised; diagnosis and acceptance remain incomplete.
No repair is proposed. Sitting 4 and AA10c are excluded.

## Evidence received from Craig

| Observation | Status |
|---|---|
| Launch mode | Home Screen app |
| Device | iPhone 16 Pro Max |
| iOS | 27.0.1, supplied by Craig |
| Remove/re-add since launch change | No |
| Affected region | Owner says “just below the clock and batter area” |
| Theme and Search state | Dark theme; blur “always visible”; individual Search states not separately described |
| Cold-launch versus resume destination | Owner answers reopen question: “it opens archive”; separate brief-app-switch result not supplied |
| Installed app served version | Unconfirmed |
| Same-phone Safari comparison | Craig confirms dark Archive header is not blurred |
| Screenshot/recording of affected surface | Received and inspected: Photo 1.jpg, dark Archive, Search closed |

The region description narrows where to inspect; it does not prove which rendered
layer is affected or why. No re-add since the launch change makes a retained installation
a diagnostic lead, not an established cause. The screenshot now supplies visual evidence of the affected app header. The agent has
not operated the iPhone or independently reproduced the symptoms. Neither cause is established.

## Source comparison after the latest owner observation

The AA1 implementation merge `4cc207d9a1c04e8e99746f3de47c5664c59125d7` changed
manifest start_url from `/movies` to `/` on 23 Oct. The current root route sends an
authenticated person to `/dashboard`; `/movies` is the collection route. These facts
make a retained installation launch target consistent with Craig's Archive report,
but they do not prove what this installation has retained. No code repair follows yet.
The screenshot identifies the app header as affected; layer attribution still requires a
controlled comparison.
A source lookup initially used components/layout rather than components/layouts;
the path was corrected through rg --files. No product file changed.

## Screenshot inspection and diagnostic status

Craig supplied Photo 1.jpg on 29 Oct. The image shows dark theme, Archive selected,
Search closed and no visible modal. The app title/assistant icon and upper part of the
profile photo appear softened; the clock/battery and collection list appear sharper.
This places the reported effect on visible app-header content, below the system icons.
It is a still image, not evidence about scrolling, a Safari tab, a light theme or Search open.

An unmodified local copy is retained under gitignored
`scratchpad/ab4/affected-header-before.jpg`; the original remains the conversation
attachment. SHA-256: `e9ed586032be86ffc1a99710b21a78f313492f1fad02e4e7d90ae6c0ecd59ab1`. The personal image is not committed.

Current source inspection at the recorded baseline finds:

- The header is relative, outside the scrolling main area, with an opaque background,
  border and safe-area padding. It has no declared filter or backdrop-filter.
- Search's blur overlay is conditional on Search being open; this screenshot shows it closed.
- The bottom bar has its own intentional backdrop blur; it is a separate rendered surface.
- The document requests black-translucent iOS status-bar treatment and viewport-fit=cover.
- Existing header tests assert class tokens; they do not inspect iOS compositor output.

The leading hypothesis is an iOS status-bar/scroll-edge overlay extending into the header.
This is an inference from the image and source, not an established MCU-device cause.
First-hand reports in [Actual issue 8899](https://github.com/actualbudget/actual/issues/8899)
and [MeshMonitor issue 5286](https://github.com/Yeraze/meshmonitor/issues/5286) describe
similar iOS 27 PWA symptoms. MeshMonitor's
[initial investigation](https://github.com/Yeraze/meshmonitor/pull/5309) reports on-device
comparisons, but that project later revised its approach. Neither report proves this
phone's OS, installed bundle or appropriate repair. No product repair is proposed for MCU before the controlled test below.
Apple's [scroll-view guidance](https://developer.apple.com/design/human-interface-guidelines/scroll-views)
explains native scroll-edge effects; native controls are not a web-app opt-out contract.

Craig has now supplied that comparison: the dark Archive header is not blurred in Safari,
and iOS is 27.0.1. This establishes the installation/mode-specific difference on the affected
phone. It strengthens the system-overlay diagnosis but does not by itself exclude an
installed stale bundle or establish which layout change will remove the effect.
Keep the original installation in place. Light theme, Search-open and separate app-switch
resume observations remain open.

## Controlled phone experiment AB4-1 — all modes reported sharp; baseline not reproduced

The next step establishes the layout mechanism before proposing a product repair.
A separate static diagnostic page reconstructs the relevant shell: 100dvh flex column,
non-scrolling header with safe-area padding, independently scrolling main area, opaque
surface and the same black-translucent metadata. It contains sample text and a striped
circle, not collection/profile data. It has no MCU login/API, push, analytics or service worker.
It does not change the original app or its installation.

On the same page/build, Relative, Sticky and Fixed controls change only header positioning.
Fixed mode reserves the measured header height, so title height stays constant. Both
colour themes and a separate Search sheet are available. The measurement panel reports
Home Screen mode and geometry. The experiment is not a reconstruction of the full app or
proof of its installed bundle version.

Why test these modes: [WebKit's LocalFrameView.cpp](https://github.com/WebKit/WebKit/blob/main/Source/WebCore/page/LocalFrameView.cpp)
`fixedContainerEdges` accepts fixed/sticky candidates and excludes relative positioning
from its edge-container classification, then samples eligible background colours. The
MCU header is relative. This is engine-source support for a mechanism, not proof that
this current WebKit main revision is the exact implementation shipped in iOS 27.0.1.
MeshMonitor's [later layout investigation](https://github.com/Yeraze/meshmonitor/pull/5328)
revised its earlier blanket claim that fixed bars behave the same; do not copy its first
padding workaround or treat another project's checks as MCU phone acceptance.

**Owner test:** open the preview in Safari, Add to Home Screen as **AB4 Test** (Open as Web
App enabled), then open the new test icon. Leave the real MCU installation in place.
Compare Relative → Sticky → Fixed and report which are sharp/blurred, first in dark theme,
then light if practical. This costs one temporary icon and three comparisons per theme;
no original-app removal, account change or collection write. If protection prompts again
inside the test icon, report that; do not disable project protection.

If Relative reproduces blur and Sticky/Fixed clears it in the same installed test process,
that supplies controlled layout evidence for the repair checkpoint. If Relative stays sharp
or all modes blur, the mechanism is not established: retain the result and continue diagnosis.
A working diagnostic mode still needs a concrete app repair review, full app gates and
actual app before/after in both themes/Search states; this test cannot close AB4 acceptance.

Preview: https://mcu-cs0wuuuu4-craigr973s-projects.vercel.app
Deployment `dpl_9nYYXk3kta54rvg2CH6Vs3bmeHSQ`, READY, target preview (API target null),
no aliases. A 23-hour share link was supplied in chat through Vercel's protected-preview
access tool. Its access token is not stored in this repository; obtain another temporary
link if it expires. The original production version/API health remain `f341d10`, with full
readiness. Project build/root/output/install/framework/node/protection settings were compared
before/after and are unchanged. No domains, environment variables or paid service changed.
**Never promote this diagnostic deployment to production.**

Reproducible static sources: `docs/reviews/ab4-diagnostic-2026-10-29/`.
The index/manifest were copied unchanged into a separate local .vercel/output/static;
output-config.json became .vercel/output/config.json. Existing project identity was linked
locally; CLI --prebuilt --target preview published only those static outputs. The connector
can create source deployments but does not expose the prebuilt option, so CLI was used.
No application build, PR, branch push, production deployment or repair was made.

Verification: six desktop geometry combinations (three modes × two themes), equal header
position/height and no main overlap/horizontal overflow; Search focus/close and zero JS
errors. The actual protected preview renders the expected page, all three controls switch,
and its authenticated manifest read returns 200 with standalone mode/name AB4 Test.
These checks validate the experiment controls, not iPhone rendering or installation.

Original deployment failure: CLI rejected --skip-domain because it is only valid with
production. No deployment was created by that attempt. Retrying without that flag while
retaining --target preview succeeded. No production flag, protection change or gate weakening.

## AB4-1 owner result and its limit

Craig replied **“sharp for all”** to the Relative → Sticky → Fixed comparison.
The requested test was in the temporary Home Screen app, dark theme first; no separate
status-panel reading, screenshot or theme confirmation accompanied the reply. Record the
result as reported, without inventing those missing observations.

The relative baseline did not reproduce the affected MCU header's blur. Consequently,
this experiment supplies no evidence that changing MCU's header positioning would repair
it. It does not prove positioning is irrelevant to the full app; the simplified page and
new installation differ from the affected full app and its retained installation state.
The iOS-overlay/edge-classification lead remains unestablished. No production repair is
proposed and no app code is changed. Do not turn three sharp modes into AB4 acceptance.

Two non-destructive observations were requested next:

1. Does AB4 Test's status panel show **Home Screen: yes**? If no, the result is a Safari
   comparison, not a standalone reproduction; use the actual test icon before interpreting it.
2. In the original MCU app, tap Home, swipe the app away, then reopen its icon: Home or
   Archive? This controls the page left before closing without deleting local state.

Keep both observations separate from the still-unverified installed bundle version.
No new diagnostic deployment, app repair or re-add of the real app was performed. Re-add remains conditional on local-state/login/push safeguards and owner review.

## Next owner observation

Dark/Search-closed before image, same-phone sharp Safari header and exact iOS 27.0.1 are
captured. AB4-1 reports all modes sharp and has not reproduced the baseline. Confirm its
Home Screen status and the original app Home → close → reopen destination before deciding
the next comparison. Capture Search-open/light-theme states when the diagnosis calls for them.

Craig reports Archive in response to the swipe-away/reopen question. The separate
brief-app-switch comparison remains outstanding: record its destination and the page
left before switching away. A force-close/reopen is an operational comparison, not proof
that iOS discarded all restoration state. Do not erase that distinction in the diagnosis.

The public version below is the server baseline, not proof of the installed client's
bundle. Correlate installed version through evidence available on the affected device;
do not assume that opening version.json in separate Safari proves the PWA's cached bundle.

After these observations, decide which diagnostic comparison is needed. If re-add is
used, explain its local-state/login/push implications before the owner acts. If re-add
alone fixes launch, record the before/after and do not invent a code repair. Show an
evidenced cause and concrete proposed repair before any launch/navigation/iOS-chrome edit.

## Fresh baseline, 29 Oct

Fetched local main and origin/main both: `f341d1084cc75863c7c00d3830a93347fc265436`.
The starting working tree was clean. Main CI [40891874070](https://github.com/CraigR973/mcu-app/actions/runs/40891874070)
passed all seven jobs, including Chromium/Firefox/WebKit/jobs E2E.

Read-only public requests returned:

- API health: status ok and the exact baseline SHA.
- Web version.json: the exact baseline SHA.
- Readiness: db ok; push, ai, ebay, tmdb and brave configured.
- Manifest: start_url `/`, scope `/`, display `standalone`.

These observations establish a healthy current server baseline only. They do not identify
the installed phone's version or close either phone criterion. No desktop token tests,
new full AB4 gate, device tests, live writes, provider calls or push tests were run.
The initial CI lookup used an incorrect repository name and returned 404; the lookup
was corrected to the verified Git remote CraigR973/mcu-app and succeeded.

## Acceptance criteria, ledger verbatim

- Establish affected phone/browser mode, served version, re-add history, theme, Search
  state and cold launch versus page resumption. Live `/` manifest and opaque CSS already
  exist; neither is a successful reproduction of the reported problem.
- **Checkpoint:** obtain affected-device observations, then show the cause and proposed
  repair before changing launch/navigation/iOS chrome. If re-adding fixes launch, record
  that without inventing a code repair. If evidence is unavailable, report the open criterion.
- Preserve login returns, notification/deep links, back/offline behaviour, normal resume
  state, safe areas and search keyboard focus. Never force every foreground/navigation
  event to Home. Separate the app header from the iOS clock/battery region and modal dimming.
- Compare actual device before/after, both themes and Search states. Any code repair gets
  full gate/E2E/exact-head CI and production SHA/readiness. Keep device acceptance open
  until observed; token-level tests cannot close a real-iPhone appearance report.

## Handoff

AB4 is yellow; the ledger setting is Opus 5 high / GPT-5.6 Sol High. No delegation.
Branch: `fix/ab4-iphone-diagnosis`, checkpoint documents and isolated diagnostic sources.
No product repair, PR, push or production deployment; only the static AB4-1 preview above.
The batch row stays open. No architecture change or new product decision was made.
Resume with AB4 Test standalone confirmation and the original app Home → close → reopen
result; the reported all-sharp experiment did not establish a layout cause. Establish
cause before presenting the repair checkpoint; launch remains a separate re-add comparison after local-state safeguards. Device before/after remains open even if later source tests pass.
