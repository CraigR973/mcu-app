# AA11 verification — 26 Oct 2026

## Outcome

AA11 shipped in [PR #112](https://github.com/CraigR973/mcu-app/pull/112), merge `b1075ec948455e5b8aecdd734ebb78ac0b31ba26`. All seven PR CI jobs pass
([run 40388842106](https://github.com/CraigR973/mcu-app/actions/runs/40388842106)).
Production API and web both served that exact merge SHA; db ready and all five integrations
configured. Read-only checks preserved all four old loans and their copy places. AA7 shipped
separately in PR #111 (`e6e5e16`). Sitting 4 is complete; sitting 5 has not started.

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
