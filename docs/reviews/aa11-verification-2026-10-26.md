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

Verification is in progress; no shipment claimed yet.

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
