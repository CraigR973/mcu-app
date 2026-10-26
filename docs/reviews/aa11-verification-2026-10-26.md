# AA11 verification — 26 Oct 2026

## Scope and owner decisions

Group AA sitting 4 only. AA7 shipped in PR #111 (`e6e5e16`); AA11 follows on its own branch.
Craig approved the four-state story before implementation, then the single pinned path
`/api/v1/loans/{loan_id}` before changing its inventory assertion. Optional teachback skipped.
Main baseline `d19b7d82b36f36f671486b8e664eb4734e7746d9`, CI 40304689184: seven green jobs.

## Acceptance checklist

- Requested copy + needed-by queues a push to the other person; no fictitious lent date.
- Taken records the actual handover; direct borrowing begins at Out.
- Either person records Back, not shelved, with returned-by; the copy's home position stays.
- To put back includes current returned copies only. Confirm preserves or changes the shelf.
- Loans and film copy cards show the four states. Named friends and both people's lending remain.
- Existing open NULL-state loans read Out, without a backfill; needed-by and return-due separate.
- Compatible migration, both read roles granted, credential grants withheld.
- API/shared/web full gate and browser/cron journeys green before normal close-out.

**Stopped, unshipped.** `group-start.md` says "Three attempts exhausted on the same failing
check" is an absolute stop. Three Chromium loan-journey runs failed; no fourth attempt made.
The implementation is committed locally; no AA11 push, PR, merge or deployment occurred.

## Implementation choices

Both people may confirm a physical shelf action, preserving their existing copy-edit access.
Reborrowing from the return pile is supported; old returned history remains Back but is no
longer current, so it never becomes an extra put-back task. Copy locks serialise all mutations.
New response fields are optional in shared parsing for old cached responses; the API emits them.
No timer or scheduled job advances state. Quiet hours and disabled notifications remain honoured.

## Observations and limits

Read-only production baseline: revision 068, four loans, all four Out. Immutable loan/copy
fields saved outside tracked files for comparison after deploy. Movies 1,943; copies 3,797;
watches 1,591; movie nights 9. Both read roles cannot read PIN hashes or invite tokens.

There was no existing dedicated browser loan case to extend. The new full loan journey supplies
that coverage without changing the required behaviour. Real-phone push receipt and physical
handovers remain owner observations; no live synthetic loan, shelf change or push will be made.
Mac WebKit is unavailable on macOS 13; CI must cover WebKit. Nine pre-existing collection-refresh
tests skip on the local Unix-socket database URL; real Postgres 17 CI must run them without skips.

## Failures encountered

- Old Git lacks `branch --show-current`; used `symbolic-ref --short HEAD`.
- Initial formatting/lint caught long lines and import order; formatted and corrected them.
- Initial mypy caught redundant nullable copy/movie reloads after locked loading; removed them.
- OpenAPI snapshot check caught an export preceding a final handler-docstring change; regenerated it.
- First browser setup used PATCH for notification preferences; the existing contract is PUT. Corrected the test setup.
- Second browser run reached Back with correct data, but the state shared an unlabelled text node with borrower/date. Gave the state its own visible span; retained the exact visible-state assertion.

- Third browser run reached shelf confirmation but exact Section label lookup timed out.
  Its accessibility snapshot exposes a combobox named Section and the Back option. The
  control uses a wrapping label containing all options; explicit label/control association
  is the next investigation. The behaviour assertion has not been removed or loosened.

## Evidence at stop

- Local full API: **2,480 passed, 9 known Unix-socket skips**, 30 warnings, 187.83 seconds.
  The 16 derived-field trigger tests run. CI Postgres 17 verification is still outstanding.
- API ruff, format and mypy pass. OpenAPI/authentication focused suite: 17 passed.
- Shared: 156 passed. Focused loan UI: 16 passed. An earlier workspace run passed 696 web
  tests before the four new LoanActions tests were added; it is not the final full gate.
- Current clean-tree full-gate runner was interrupted after the browser stop; remaining
  workspace/build checks are not claimed. CI and final browser/cron gate have not run.
- Browser proved request with no lent date, one decrypted fake push to Mark, Taken, and
  Craig's return to Back, not shelved. Shelf change/confirmation remains unproved in-browser.
- Preserved third-run trace, context and requested-state mobile screenshot in ignored
  `scratchpad/aa11-verification/stopped-browser-3/`. No invented production data.

## Resume point

Reuse the existing branch and commits. Correct the exact Section label lookup, preserve the
four-state and shelf assertions, rerun the full local gate plus Chromium/Firefox/jobs, then
seven-job PR CI including WebKit. Only green gates authorise normal close-out. Verify exact
API/web SHA, readiness, migration/grants and all four pre-existing loans unchanged via the
read-only baseline comparison. No sitting 5 work and no real synthetic loan/push/backfill.
