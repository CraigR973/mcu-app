# AD1 release blocker: Firefox loses Add a copy navigation — 8 Nov 2026

> **Follow-up complete 9 Nov:** the 36 px asynchronous movie-night insertion is proved
> and repaired. All runnable local checks pass; release remains unauthorised.
> See `ad1-navigation-follow-up-2026-11-08-2326.md`. The original timed failure evidence
> below is retained as history; it is superseded for current local verification.

## Verdict

**The full local gate is red. Do not release AD1.** Mark's new three-review flow passes in
both Chromium and Firefox, including the signed-out redirect, administrator assignment,
private responses, stale targets and source resolution. A separate existing film-page
flow failed in Firefox. Its exact cause has not been proved, and no repair, assertion
change, timeout increase, force-click or blind retry was made.

Craig approved the three review cards, while the earlier instruction says “Do not start
another implementation batch.” This report is the bounded diagnosis/next-scope checkpoint;
it does not authorise another batch or lift the no-commit/push/merge/deploy/live-write boundary.

## Final verification result

| Gate | Result |
|---|---|
| API lint/format/mypy | Pass |
| Real local Postgres API suite | 2,754 passed, zero skips |
| Shared/web suites | 200 / 898 passed |
| Shared/web lint/type/build; browser-suite types | Pass; web lint retains 11 existing warnings |
| Migration reversal | Fresh upgrade head → downgrade base → upgrade head passes; populated review-history downgrade refuses |
| Chromium, complete valid seed | 95 passed |
| Firefox, complete valid seed | 93 passed, 1 existing allowed dictation skip, **1 failed** |
| Fake jobs | 8 passed |
| Exact candidate CI/WebKit, production release, real phone | Unrun; not implied by the local results |

The full browser run used the verified template: 70 owned films, 8 configured shops,
0 leaked reviews after the focused test. Earlier incomplete-template failures and their
remedy are retained in the implementation report. They do not explain away this final
Firefox failure.

## What actually failed

Existing test: `apps/e2e/specs/offline.spec.ts`, the lost-answer replay case. The failure is
at its **first** `chooseFilm('Paper Lantern', …)` call, immediately after pressing the film
page's **Add a copy** link. The case has **not yet switched offline or replayed a write**.
Do not describe this evidence as a failed replay algorithm or a duplicate saved disc.

The retained Firefox trace establishes:

1. Paper Lantern's film page and its heading loaded. Its **Add a copy** link had
   `href="/collection/add"`.
2. Playwright found the link visible, enabled and stable, then performed one normal click
   at **x=769, y=686**. The action reported completion and no scheduled navigation.
3. The next **Search title** tab was absent for the unchanged **10-second** locator wait.
4. The failure snapshot still showed **Paper Lantern**, its Owned copies tab and the focused
   Add a copy link. It was not the add form.

Click action: monotonic **492532.417–492673.124 ms**. The following tab action timed out at
**502681.817 ms**. Extracted frames at 492588.216, 492641.665 and 492694.989 were inspected.
They show the film page around the click; they do **not** establish a causal layout movement.
There is insufficient evidence to choose between event loss, remount/navigation recovery,
service-worker timing or another cause. Do not preselect a repair.

The film detail implementation and this offline test are unchanged in AD1. That narrows the
affected path; it does not prove the cause is independent of the new build or that the same
failure occurs on the pre-AD1 build. Current main CI remains green. This is an observed
candidate verification blocker, not a claim that production is known broken.

## Retained local evidence

- Full run: `scratchpad/ad1-valid-template-e2e.log`; result JSON records exit **1**.
- Original trace copied to `scratchpad/ad1-firefox-offline-blocker-trace.zip` before any
  possible later test-output reset. It contains fake test-session material and stays ignored.
- Extracted frame files: `scratchpad/ad1-firefox-click-<timestamp>.jpeg`.
- Playwright error context remains under the Firefox lost-answer case's test-results folder.
- The new review flow passed at case 51 in both browsers; its corrected 375 px preview is
  retained with the implementation report and explicitly labelled as fake test data.

No real diary contents, credentials, authenticated production captures or tokens are copied
into this report. Never publish the raw trace/session material.

## Bounded follow-up — approved by Craig on 8 Nov

**Reproduce and repair the Add a copy click loss, then complete local verification.**
Craig replied “approve”; decision 352 records the scope and retained boundaries.
Estimate **60–90 minutes**, including a focused controlled reproduction and full local
checks; extra time may be needed if the cause crosses worker/navigation boundaries. No new
service/provider fee, production write, hosting change or credential change is proposed.

Scope and prerequisites:

- Start from this preserved checkout/branch and re-read current status, owner actions,
  decision 351, the AD1 implementation report and this blocker. Verify the current app
  fingerprint and main/CI/deployment again; preserve every existing edit and report.
- Instrument pointer down/up/click, route/location changes and relevant film/copy/poster
  readiness in a disposable browser run. Use controlled delayed responses to reproduce
  causally; compare snapshots and request timing. Establish whether a real app defect or a
  harness sequencing error exists before changing code.
- Fix only the confirmed cause. Retain the original route/content expectations, normal
  click and 10-second wait. No force clicks, retries, relaxed assertions, added skips,
  unproved “wait longer” changes or replay/data-contract changes as a route to green.
- Add a meaningful deterministic regression, then run the appropriate full gate. A
  successful focused retry alone cannot erase the failed full-run evidence.
- Keep AD1's production release, actual assignments, Mark's Letterboxd enable/backfill,
  cinema/provider actions and AA10c outside this follow-up unless separately authorised.
  If a proposed repair changes data/auth/contracts or broadens scope, stop with concrete
  evidence and a new checkpoint.

After that gate is green, the next separate release checkpoint covers the exact commit,
all seven CI jobs including WebKit, API/web SHA/full readiness, migration/role read-back and
the three explicit review assignments. No release is authorised by this report.
