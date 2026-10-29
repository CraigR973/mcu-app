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
| Theme and Search state | Not yet supplied |
| Cold-launch versus resume destination | Not yet supplied |
| Installed app served version | Unconfirmed |
| Screenshot/recording of affected surface | Not yet supplied |

The region description narrows where to inspect; it does not prove which rendered
layer is affected or why. No re-add since the launch change makes a retained installation
a diagnostic lead, not an established cause. No affected-iPhone session has been operated
or visually inspected by the agent. Neither reported problem is reproduced yet.

## Next owner observation

Preserve the affected installation first. Capture the blurred region with Search closed
and open, identifying the active theme. Include the clock/battery area and app header in
the image so those layers can be distinguished. Establish the exact iOS version.

Compare tapping the Home Screen icon after swiping the app away with returning after a
brief app switch. Record Home/Archive/other destination in each case, including the page
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
