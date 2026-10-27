# AA11 verification — 26 Oct 2026

## Outcome

AA11 shipped in [PR #112](https://github.com/CraigR973/mcu-app/pull/112), merge
`b1075ec948455e5b8aecdd734ebb78ac0b31ba26`. Separate navigation repairs shipped in
PR #113 (`30f3607`) and [PR #114](https://github.com/CraigR973/mcu-app/pull/114)
(`0b4a4167128b7a17d3c3d8f7b133ac720c9563cb`). The latter passes all seven PR and merge CI jobs
(40414279164, 40479165450). Production API/web exact merge SHA, full readiness and read-only
four-loan/grant/credential preservation are verified. AA7 shipped separately in PR #111.
Both previous CI stops are preserved below. Sitting 4 is complete; sitting 5 has not started.

Craig approved the four-state story before implementation, then the single pinned path
`/api/v1/loans/{loan_id}` before its inventory expectation changed. The previous three-attempt
browser stop was honoured; Craig explicitly resumed AA11 before the label fix and further runs.
Main baseline `d19b7d82b36f36f671486b8e664eb4734e7746d9`, CI 40304689184: seven green jobs.

## Acceptance evidence

| Criterion | Evidence | Status |
|---|---|---|
| Asked for with needed-by and push to Mark | Real API/outbox, decrypted fake push and both browser journeys; no lent date until Taken | Pass |
| Direct taking starts Out; Taken records handover | Existing lending/borrowing API and UI tests retained; full request → handover browser flow | Pass |
| Either person records Back, not shelved | Actor stored as returned-by; home position unchanged; API and browser evidence | Pass |
| To put back and shelf confirmation/change | Current returns only; explicit confirmation preserves or atomically changes copy location and audit | Pass |
| State shown on Loans and film | Chromium and Firefox flows, including final Shelved and revised home position | Pass |
| Existing four loans preserved as Out | Read-only baseline and repeat preflight identical; migration has no row backfill | Pass after deploy |
| Compatible migration and read-role grants | Local upgrade 069; CI reversal/image boot and live privilege checks passed | Pass in CI and production |
| Tests and complete gate | Ten local checks, full Chromium/Firefox and six cron cases pass | Pass, all seven CI jobs |

## Complete local gate

Clean source commit: `75adafe23ab7b167012a4bb8afce38656d174c19`.
All ten `batch-verify.md` commands pass; logs and exact source digest are saved outside tracked
files in `/tmp/mcu-aa11-gate-stamp.json`. Documentation updates after this gate change no source.

- API: **2,480 passed, 9 known Unix-socket skips**, 30 existing deprecation warnings.
  The 16 derived-field trigger tests run. Postgres 17 CI ran all 2,489 tests with zero skips, including all 16 derived-field trigger tests.
- Shared: 156 tests; web: 700 tests across 102 files. Lint, types and production builds pass.
  Web lint reports 11 existing React-refresh warnings, zero errors; existing dependency/build
  annotation and bundle warnings are retained rather than suppressed.
- Chromium: 38 passed. Firefox: 37 passed, one documented no-dictation skip.
- Cron jobs: six passed. All providers are faked and unexpected outbound calls fail closed.
- The resumed focused Chromium loan journey passed on its first run with the exact original
  behaviour assertions intact. Full Chromium and Firefox also passed it.
- Mac WebKit is unavailable on macOS 13. CI WebKit passed 36 cases with its two documented skips; Chromium passed 38, Firefox 37 plus the documented dictation skip, and cron jobs six.

The 375 px requested-copy and shelf-change screens were visually inspected: state, needed-by,
Section, shelf and confirmation controls fit without clipping. Screenshots and the stopped-run
trace are preserved under ignored `scratchpad/aa11-verification/`. Fixture poster assets are not
production image evidence.

## Implementation choices

Migration 069 adds nullable state, needed-by, returned-by and shelved-at, and allows no lent date
until handover. Existing open NULL-state loans read Out; old closed history remains closed.
Needed-by and optional return-due stay separate. No date or job advances a state; overdue
reminders only apply to Out copies. The downgrade refuses unresolved requests instead of
inventing dates or deleting them.

Both people may confirm a shelf action, preserving existing copy-edit access; Mark has the
To put back list. Reborrowing from the return pile preserves older history without reviving
its put-back task. Every mutation locks the copy first, then its loan; stale transitions fail.
Shelf changes and their loan/audit records commit together. Request pushes use the existing
outbox, preferences, quiet hours and retry path. Shared response fields remain compatible with
old cached responses. No hosting, credential or external service configuration changed.

## Production baseline and limits

Read-only preflight: revision 068, four loans, all Out; immutable loan fields and copy places
match the saved baseline on the resumed run. Movies 1,943; copies 3,797; watches 1,591;
movie nights 9. Both read roles cannot read PIN hashes or invite tokens.

No synthetic production loan, shelf change, notification or agent-run backfill is authorised or
performed. Real-phone push receipt and physical handovers remain owner observations; AA7's
real-phone picture selection also remains unverified. These cannot be replaced with a green CI.
The existing device criteria 6.2, 5.6, 9.5 and 8.4 remain with the owner.

## Every failure encountered

- Old Git lacks `branch --show-current`; used `symbolic-ref --short HEAD`.
- Initial lint/format caught long lines and import order; formatted and corrected them.
- Initial mypy caught redundant nullable copy/movie reloads after locked loading; removed them.
- OpenAPI snapshot export preceded a final handler-docstring change; regenerated it and passed
  the unchanged snapshot comparison.
- First browser setup used PATCH for notification preferences; the existing contract is PUT.
  Corrected setup, retaining the journey assertions.
- Second browser run reached Back correctly, but state text shared a node with borrower/date.
  Gave state its own visible span; retained the exact state-text assertion.
- Third browser run could not find Section by its exact label, although its accessibility
  snapshot exposed Section and Back. Stopped at the command's three-attempt limit and saved
  the handoff. Craig resumed; separate explicit label/control associations fixed the lookup.
- There was no existing dedicated browser loan case to extend. The new complete loan journey
  supplies the required coverage without changing the required behaviour.

## Shipment record

PR #112 merged `b1075ec948455e5b8aecdd734ebb78ac0b31ba26` after seven green jobs on exact head `c2509ead4818497d7e833359018230aeb146f304`.
API/web served the exact merge SHA and readiness read db ok, push/AI/eBay/TMDB/Brave configured.
Database revision 069; all four existing loan/copy snapshots equal the baseline. All four new
metadata fields remain NULL on the four old Out loans. Both mcu_readonly and mcu_backup can
read all new columns; neither can read PIN hashes or invite tokens. Anonymous loan PATCH is 401.
Production counts: movies 1,943, copies 3,797, watches
1,591, movie nights 9. No live test write occurred.

The source tree matches the verified PR tree. The final documentation-only close-out receives
its own exact-head CI/deployment checks before the session ends. Do not start sitting 5.


## Final exact-head CI failure — stop point

Production serves `0d757ed052642983424d25e3b1c7b847c3fbe8a6` on both hosts, with full readiness.
The read-only loan/grant/credential checks were repeated after the CI failure: all four old
loans/places remain identical and all new metadata remains NULL. The source digest matches
the green PR; merge CI 40390679557 also passed all seven jobs.

[Final CI 40390928359](https://github.com/CraigR973/mcu-app/actions/runs/40390928359)
failed its E2E job; the other six jobs passed. Chromium 38 passed, Firefox 37 passed plus
its documented skip, WebKit 35 passed / one failed / two documented skips, cron six passed.
AA11's exact loan journey passed in Chromium, Firefox and WebKit on this final run too.

Failure: the unchanged `login.spec.ts` sign-out case signed in and reached the dashboard URL,
then `page.goto('/you')` failed with **WebKit encountered an internal error**, before the
Sign out button was clicked. The root cause has not been established. Earlier green runs do
not justify treating it as harmless or rerunning to hide it. No assertion, skip, retry or
timeout was altered. Downloaded report, context, trace and logs are retained under ignored
`scratchpad/aa11-verification/final-ci-failure/`.

`group-start.md` says CI not green is an absolute stop: stop the group, report and wait.
The handoff is committed locally, without pushing a new run/deployment. On Craig's resume,
keep this checkout, investigate the navigation trace and fix main's pre-existing red on a
separate narrow fix branch before completing AA11's final proof. Do not start sitting 5.

## Final CI repair resumed — 26 Oct

Craig explicitly resumed AA11 close-out after the final red main run. The separate
`fix/login-navigation-readiness` branch preserves the local handoff. The failed trace
shows the dashboard URL assertion finishing before Home starts its API requests; the
next full-document navigation to `/you` aborts alongside those requests. `/sw.js` was
also installing in this context. The trace does not establish a production sign-out
failure: Sign out was never reached.

The login suite now uses the same worker-blocked context isolation as `signedIn()`;
the dedicated offline suite continues to enable and test the real worker. Both login
journeys wait for the Home heading before navigating away. Every original outcome
assertion, browser project, timeout and zero-retry setting is retained. Verification
passed locally at clean source `345ad19d6eeaf2ec85e7d245158ff1ff2797c3d1`: all ten gate
commands, E2E typecheck, eight focused login cases, Chromium 38, Firefox 37 plus its
documented dictation skip, and six cron cases. API 2,480 passed with nine known local
socket skips; shared 156 and web 700 passed. No new local failure occurred during this
repair. WebKit must be proved in CI because this Mac cannot run it.

## Resumed shipment verified before the second CI stop — 26 Oct

Separate [PR #113](https://github.com/CraigR973/mcu-app/pull/113) merged `30f3607805bd94bc6441c88d1b783e6cb7e49dbf`
after all seven jobs passed on its exact PR head
([CI 40407597236](https://github.com/CraigR973/mcu-app/actions/runs/40407597236)).
The CI result and full logs are retained locally. WebKit proves the original sign-out
and access-boundary assertions; the dedicated offline cases still test worker behaviour.
No retry, extra skip, timeout increase or expected-result weakening was introduced.

Production API and web served that exact merge SHA with db ok and push/AI/eBay/TMDB/Brave
configured. Read-only checks again preserve all four legacy Out loans and their copy places,
leave all new metadata NULL, verify both read-role grants and withhold PIN/invite credentials.
The final documentation-only head receives exact-head seven-job CI and production checks
before the session ends. Group AA sitting 4 was subsequently blocked by the merge-CI failure below; sitting 5 remains excluded.
The owner-only phone and physical checks remain unverified.

Repair CI details: API 2,489 passed without skips, including all 16 derived-field trigger
tests; Chromium 38, Firefox 37 plus its documented dictation skip, WebKit 36 plus its
two documented skips, cron six. Both sign-out and AA11 loan cases passed in every browser.
Attempting to fetch a completed API job's log before the entire run finished returned
“logs will be available when it is complete”; the complete logs were then retrieved
after the run finished. No repair test failure or waived check occurred.

## Second CI stop — Firefox offline navigation

[Merge CI 40409200298](https://github.com/CraigR973/mcu-app/actions/runs/40409200298)
failed one of seven jobs, end-to-end, on merge `30f3607805bd94bc6441c88d1b783e6cb7e49dbf`.
Firefox's unchanged worker-enabled lost-answer replay case failed at `offline.spec.ts:81`,
its first film-page navigation, with `page.goto: NS_BINDING_ABORTED`, before the replay
scenario. Root cause is not established. Chromium 38, Firefox 36 / one failure / one
documented skip, WebKit 36 / two documented skips, cron six. All sign-out and loan
journeys passed in all three browsers. All six other CI jobs passed.

The group stopped immediately after detecting the red. No offline-test edit, assertion
change, retry, extra skip, rerun or further batch was started. Failed logs are saved in
`/tmp/mcu-aa11-ci-fix-merge-failed.log`; downloaded failure artifacts are under ignored
`scratchpad/aa11-verification/ci-fix-merge-failure/`. Keep this checkout and its local
handoff. A separately authorised resume must investigate the Firefox trace and fix
the defect on its own narrow branch before finishing close-out.

The final documentation-only run 40409482751 was already running on
`65abd7e1e4e20cd4332e91e6cb5d329531d62d7a`; its outcome cannot waive this failure.
Both production hosts served that exact final SHA with full readiness. Read-only
checks preserve all four old loans and locations, new metadata NULL, read-role grants
and withheld credentials. This handoff is local only; no new deployment is triggered.
Sitting 5 has not started. Real-phone observations remain open.

## Offline-navigation repair resumed — 26 Oct

Craig explicitly resumed after the second CI stop. Latest main documentation CI
40409482751 completed all seven jobs successfully at `65abd7e`, but that does not waive
the observed merge failure. The existing checkout and local handoff are preserved on
separate `fix/offline-navigation-readiness`.

The Firefox trace shows `workerInControl` returning after reload and controller presence,
while the reloaded Add a disc screen still imports its lazy dependencies. Navigation
starts while CopyForm is pending; that chunk and the target film navigation both abort.
The existing app handles failed lazy imports by reloading. The test now waits for the
Add a disc heading, which renders after that screen's imports resolve, before leaving.
The real worker, lost-answer interception, queue-state and one-copy assertions remain
unchanged; no retries, extra skips or timeout changes.

The clean repair source `123f24b8b44a394c7ca9c0542df7f12f77931d12` passes all ten local
gate commands and E2E typecheck. API 2,480 passed / nine known local socket skips,
shared 156 and web 700 passed. Both focused offline cases passed in Chromium and
Firefox; full Chromium 38, Firefox 37 plus its documented dictation skip, cron six.
No local test failure occurred on this repair. CI must prove WebKit and Postgres 17.

## Offline repair and resumed close-out completed — 27 Oct

PR #114 merged `0b4a4167128b7a17d3c3d8f7b133ac720c9563cb` after exact-head [PR CI 40414279164](https://github.com/CraigR973/mcu-app/actions/runs/40414279164)
passed all seven jobs. [Merge CI 40479165450](https://github.com/CraigR973/mcu-app/actions/runs/40479165450)
also passed all seven before the final close-out documentation was pushed. Chromium 38,
Firefox 37 plus its documented dictation skip, WebKit 36 plus its two documented skips,
cron six. Both repaired navigation cases and the complete loan flow pass. API 2,489
passed without skips, including all 16 derived-field trigger cases.

The production API and web served the exact merge SHA; db ok and all five integrations
configured. Read-only checks preserve all four old Out loans and copy places, leave all
new metadata NULL, verify both read-role grants and withhold PIN/invite credentials.
The final documentation head receives the same exact-SHA seven-job CI and deployment
checks before this session ends. No live synthetic mutation or backfill occurred.
Real-phone observations remain unverified. Sitting 5 has not started.

PR CI browser installation took 46 min 32 sec before the suite ran and passed. The
existing 90-minute job limit was retained; no workflow/configuration change or rerun
was used. Merge CI subsequently completed all seven jobs in its ordinary run. The
resumed offline repair introduced no local or CI test failure.
