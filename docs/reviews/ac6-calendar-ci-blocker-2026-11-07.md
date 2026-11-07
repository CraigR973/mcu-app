# AC6 final CI blocker: calendar subscription click race — 7 Nov

## Verdict

AC6 is deployed in PR #136. Implementation PR CI 42391299778 and implementation main CI
42392858508 passed all seven jobs at `46aaba5309bca4d5b4b62ef4a9ec5786f594b5be`.
The documentation handoff `196f2d65df7403cb12bbdb0a84c0be7bd3c1bb68` is served by both
production API and web with full readiness, but its final main CI 42393261032 is **red**:
6 jobs pass; Firefox's existing calendar subscription case fails. Do not report all checks
green or full acceptance. AC6 passes in all three browsers and all eight jobs cases pass.

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

## Repair implementation and verification in progress

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
feed/token action runs. Complete local clean-tree gates, browser suites, PR/main CI and
actual production SHA/readiness still need their final evidence.

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

Draft repair PR #137 / CI 42399647416 supplies independent exact-commit evidence. It must
remain draft and unmerged until the complete local and exact-commit gates are green.
