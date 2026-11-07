# AC6 final CI blocker: calendar subscription click race — 7 Nov

## Verdict

The separately approved repair is deployed in PR #137 at
`7c536d9c99ebd0102a875f099e4bbc29bbbefc06` (#350). At **18:43 UTC**, production API and
web serve that exact SHA and every readiness field passes. The clean-tree local gate and
all seven exact-head PR CI jobs (42400083769) pass. Final main/handoff CI and served-SHA
verification are stamped in PR #137 before session completion.

The original final AC6 documentation CI at `196f2d6` failed the pre-existing calendar click
race described below; that failure is retained as history. AC6 itself remains deployed with
acceptance open: no naturally scheduled qualifying digest or phone receipt/tap is proved.

[Failed run](https://github.com/CraigR973/mcu-app/actions/runs/42393261032) and
[AC6 PR / live verification record](https://github.com/CraigR973/mcu-app/pull/136).

## Cause, established before proposing a repair

The calendar page renders an enabled Get my calendar links button beneath independently
loading month/Coming soon content. The Coming soon component initially renders its empty
panel before its data arrives. The successful responses replace that short panel with
programme cards, moving the button during a real pointer gesture.

The retained Firefox trace shows Get my calendar links visible/enabled/stable at pointer
selection, an empty programme at the input snapshot, programme cards in the after-click
snapshot, and no browser POST to `/calendar/subscribe`. The final error snapshot retains
the button and contains no generated feed links. All programme GETs returned 200; this was
not a calendar-subscription API failure, a slow POST, or an AC6 identity/push failure.

A controlled local Firefox reproduction held the programme GETs until pointer-down, released
them, then performed pointer-up at the original point. The button moved from **y=587** to
**y=1128.5** (541.5 px), and **0 subscription POSTs** were sent. The single diagnostic case
passed its exact movement/no-POST assertions in 10.8 seconds (56 seconds including harness).
It used disposable Postgres and fake providers only. Temporary diagnostic source and its
output remain in ignored scratchpad; the temporary spec was removed from the suite.

The same application source passed earlier PR/main CI; the failure depends on the ordering
of asynchronous content settlement and pointer-up. No blind rerun, force click, test delay,
extra retry, skip or relaxed assertion was used to reach green.

## Separate repair approved — 7 Nov (#350)

Craig replied **“approve”** to the separate calendar repair proposal on 7 Nov; #350 records
that scope decision before implementation. The AC6-only boundary remains in force for
anything beyond the following calendar readiness repair.

1. Use a separate `fix/` branch and PR in this checkout, preserving the AC6 implementation.
2. Gate the calendar subscription button on settlement of the initial layout-producing
   programme queries, using the existing shared query cache and native disabled semantics.
   Preserve page order, one subscription press, all three feeds and token rotation behaviour.
3. Render an honest loading state instead of an empty Coming soon result while pending.
   Loading/error settlement must not leave the button permanently disabled or issue duplicate
   programme reads. Keep cached reads, month changes and both calendar views working.
4. Add a deterministic held-response/pointer regression. Retain all existing one-press,
   three-feed, old-token rejection and browser assertions, with zero added retries or skips.
5. Run the full local gate/E2E, all seven exact-commit PR/main CI jobs, and API/web/full
   readiness verification. Do not rotate a production calendar token or create a live feed
   as a test. No hosting, credential, schema or live-domain-data change is proposed.

Estimated cost: **60–90 minutes**, mainly full local/CI gates; no new service or provider cost.
The rejected shortcut is a delay/retry/force-click in the test: it would hide a lost real
pointer click and leave the user-facing cause intact. Stopping instead leaves AC6 deployed
with a known final CI failure. Neither choice closes the still-pending natural digest/phone
acceptance; AC3's rerun read-back and AC5's phone/trip observations remain separate.

Read-only recheck at **17:20 UTC**: production API/web still serve `196f2d6`, full readiness
passes, migration/grants/defaults are unchanged, and appearances/days/claims/cinema outbox
remain zero. No manual production refresh, digest, trip or calendar-subscription action ran.

## Repair acceptance criteria (approved proposal, restated before code)

The five numbered recommendations above are the repair contract. In particular, the button
must use native disabled semantics until relevant initial layout queries settle; all three
feed/rotation assertions remain; cached/offline/error states and both calendar views must
work without duplicate programme reads. A controlled pointer regression must fail on the
old enabled-during-loading behaviour. Two existing unit cases that click immediately after
render will now wait for the approved enabled state before their single click; their feed
assertions remain unchanged. Full gates, exact seven-job PR/main CI and served-SHA/readiness
are required. No manual live calendar, digest or refresh action is authorised.

## Approved repair implementation

The approved repair is on `fix/calendar-subscribe-readiness`, independently of the AC6
feature work. Four shared query hooks preserve the exact keys, enabled scopes and stale
windows. The page observes the same cache as Month view, Coming soon and Coming to disc,
deriving readiness during render without an effect/state handshake. Only the relevant
calendar's queries gate the native subscription button. Pending/fetching holds it; a
terminal failure or offline pause settles it, and reconnect/refetch holds it again. Coming
soon now states loading/offline rather than prematurely claiming an empty programme.
The existing subscription endpoint, three feed URLs and token rotation are untouched.

Five new held-source unit regressions failed on the old enabled-during-loading control
before implementation (5 failed, 11 passed). After repair, all **19** focused unit cases pass:
each independent hold, one request per relevant source, terminal errors, paused offline /
reconnect, cache reuse, and the original feed/navigation assertions. E2E typecheck passes.
Two existing unit cases wait for the newly approved native enabled state before their one
click; every feed/order/rotation assertion stays unchanged. No browser assertion, retry,
skip, timeout or configuration was relaxed.

Four focused Firefox real-pointer cases pass at 375 px, both themes and both calendars.
Held programme responses arrive between down/up; native disabled state sends no POST, then
one enabled click creates all three feed groups. The layouts move **393.5 px** for discs
and **708.5 px** for cinema, and each programme endpoint is read exactly once. No production
feed/token action runs. Complete local clean-tree gates and exact PR CI now pass; production SHA/readiness is verified below. Final main/handoff CI is stamped in PR #137.

## First complete local run: host contention and fixture cleanup failure

The clean `7a85021` tree passed API 2,741 (zero skips), shared 200, web 891 and all static /
type/build checks. Chromium passed 94. Firefox passed every calendar case, but ended 91
passed, 2 failed, 1 permitted dictation skip during severe Mac host contention: load average
159.69 on 4 logical CPUs, later 120.08. The photo case exhausted its whole 60-second budget
after successful upload/blob checks; trace includes an 8-second blank-page creation and a
10.6-second reload. The box-set POST and its following GET both returned ownedCount=1, but
the renderer missed the existing 10-second assertion deadline. Their traces are preserved;
no photo/box-set application code, assertion or timeout is changed. An unchanged full Firefox
run after load recovery and independent Linux CI remain required; a passing retry alone is
not described as a code repair.

Jobs ended 7 passed / 1 failed. The AC5 reminder's two real commands, exact dedupe/status and
decrypted push body/URL assertions all passed. Its finally block reused an HTTP connection
that went idle while Node synchronously ran the commands and failed with ECONNRESET. As a
necessary verification-fixture correction, cleanup now restores the four saved preference
fields directly in disposable Postgres, just as the existing cinema digest fixture does.
It additionally verifies that the snapshot is restored. No business assertion, production
code, retry, skip or timeout is changed. No production trip/preferences/feed/token is touched.

Independent application-code PR CI 42399647416 passed all seven jobs at `7a85021`. The complete local and exact-head PR gates then passed before PR #137 was marked ready and fast-forwarded to main.


## Completed local and release verification

- Clean `7a85021`: API **2,741 passed, zero skips**; shared 200; web 891; Ruff, formatting,
  mypy (278 files), lint, typechecks and builds pass. Existing warnings were not suppressed.
  Chromium 94 passed; four 375 px screenshots were visually inspected in both themes/calendars.
- Clean `7c536d9`: all eight real-command jobs pass, including the corrected reminder cleanup
  and snapshot-equality check. Complete unchanged Firefox passes **93 + 1 permitted dictation
  skip** in 17.8 minutes. Its photo case takes 14.1 seconds and box-set case 2.1 seconds.
  The run began after load fell to 6.91 (from a peak of 196 on four logical CPUs), and load
  fluctuated again during it. Retained failed traces plus independent Linux CI distinguish
  this scheduling evidence from the calendar repair; no photo/box-set production fix is claimed.
- Application/API/shared source, dependencies and CI configuration are byte-identical from
  `7a85021` to `7c536d9`; the latter changes only reminder-fixture cleanup and this report.
  E2E typecheck passes. No additional retry, delay, force click, skip or timeout was introduced.
- Exact-head PR CI **42400083769** passes all seven jobs at `7c536d9`: C94 / F93+1 / W92+2 /
  jobs8. Independent **42399647416** has identical counts. The three skips are the documented
  Firefox dictation and WebKit live-match/lost-replay-answer limitations. WebKit cannot run on
  this Mac; CI supplies its browser evidence.
- PR #137 fast-forwarded to main only after these gates passed. Main code CI **42402584704**
  and final documentation CI are checked to completion, with exact-SHA/parity results recorded
  in PR #137. A feature-branch run with E2E skipped is never counted as browser evidence.

| Approved repair criterion | Evidence | Result |
|---|---|---|
| Separate fix/PR and scope | PR #137; #350 recorded before code | Met |
| Native readiness, shared cache | 19 unit cases; all relevant GETs exactly once in pointer cases | Met |
| Honest loading, cache/error/offline/reconnect | Independent held-source, settled error, remount and reconnect cases | Met |
| Same one press, three feeds, token rotation | Original browser assertions unchanged; four held-response pointer cases in every browser | Met |
| Full gates and actual deploy | Local/PR gates above; 18:43 API/web parity and full readiness; final CI stamp in PR #137 | Release verified; final stamp required before completion |

Read-only production check at **18:43 UTC** confirms migration 073, all five tables and both
preference columns readable by both guarded roles, credentials withheld, Cinemas on /
Older films only off / Movie night on for both existing people. Silent baseline remains
278 listings / 23 identities; appearances, days, claims and cinema outbox rows remain **zero**.
No manual production source refresh, digest, trip, feed creation or token rotation ran.

To inspect the repair: Releases → Disc releases or Cinema releases. Get my calendar links is
busy/disabled while programme layout loads, then one press creates the existing three links.
A real press rotates a calendar token; production testing did not press it. The approved
implementation choices are shared query hooks, render-derived readiness, native controls and
terminal-error/offline-pause settlement. No subscription contract or page order changed.

AC6 stays **unstruck** until the first naturally scheduled qualifying day/appearance/outbox/
claim read-back. An empty scheduled run does not prove positive delivery. Real-phone receipt
and tap remain Craig's observation. AC3's 8 Nov rerun read-back and AC5's real trip/phone checks
are separate. No next batch is started.
