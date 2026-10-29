# AB4 — affected-iPhone evidence checkpoint

29 Oct. Sitting 3 is authorised; diagnosis and acceptance remain incomplete.
No repair is proposed. Sitting 4 and AA10c are excluded.

## Evidence received from Craig

| Observation | Status |
|---|---|
| Launch mode | Home Screen app |
| Device | iPhone 16 Pro Max |
| iOS | Owner says “latest ios”; exact version unconfirmed |
| Remove/re-add since launch change | No |
| Affected region | Owner says “just below the clock and batter area” |
| Theme and Search state | Dark theme; blur “always visible”; individual Search states not separately described |
| Cold-launch versus resume destination | Owner answers reopen question: “it opens archive”; separate brief-app-switch result not supplied |
| Installed app served version | Unconfirmed |
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
phone's OS, installed bundle or appropriate repair. No workaround is proposed for MCU.
Apple's [scroll-view guidance](https://developer.apple.com/design/human-interface-guidelines/scroll-views)
explains native scroll-edge effects; native controls are not a web-app opt-out contract.

Next comparison requested from Craig: open the same `/movies` screen in Safari on the
same phone in dark theme and report sharp/blurred, and supply the exact iOS version from
Settings → General → About. A difference narrows the fault to installation/mode-specific
behaviour; it does not by itself exclude an installed stale bundle. Keep the installation
in place. Light theme, Search-open and separate app-switch resume observations remain open.

## Next owner observation

The dark/Search-closed before image is captured. Preserve the affected installation while
comparing the same screen in Safari and establishing the exact iOS version. Capture the
Search-open and light-theme states when the diagnostic comparison calls for them.

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
Branch: `fix/ab4-iphone-diagnosis`, documents only. No PR, push or deployment.
The batch row stays open. No architecture change or new product decision was made.
Resume at the outstanding affected-device observations, establish cause, then present
the repair checkpoint. Device before/after remains open even if later source tests pass.
