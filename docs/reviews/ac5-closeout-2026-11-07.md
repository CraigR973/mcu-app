# AC5 close-out — 7 Nov 2026

Cinema trips shipped in [PR #135](https://github.com/CraigR973/mcu-app/pull/135), fast-forward
merge `6384c61c4aa0528ca5c7152d8ba55d9ce9699d2e`, to Craig's approved eight-point contract (#345).
Implementation and design choices are recorded in #346. This session completed the production
verification, live read-back and documentation left by the implementation session.

## Remaining owner observations

Phone rendering and receipt/opening of a genuine trip push remain Craig's observations.
No production trip, push, reminder run or sign-in was manufactured for acceptance. Empty-state
reads prove the deployed schema and read services; they do not prove a real invitation has
arrived on either phone. The first real trip is Craig's to propose when wanted.
AC6's new Cinemas preference and wording remain at their separate owner checkpoint.
AC3's rerun read-back remains due after the 8 Nov scheduled run.

## Gate evidence

- Before AC5, main `d988b65` was green: CI 42280363025.
- [PR CI 42375136720](https://github.com/CraigR973/mcu-app/actions/runs/42375136720) and
  [main CI 42376631323](https://github.com/CraigR973/mcu-app/actions/runs/42376631323)
  both passed all seven jobs at the exact merged commit.
- API: 2,702 passed, no skips, including all 16 derived-field trigger tests against Postgres 17.
  Image build/migrate/boot, migration upgrade/downgrade, dependency audits and web checks passed.
- Shared: 200 passed; web: 877 passed. Existing 11 web lint warnings remain.
- E2E: Chromium 89; Firefox 88 + its allowed dictation skip; WebKit 87 + its two allowed
  offline-replay/live-match skips; jobs 7. All three new AC5 browser cases passed on all three
  browsers, including both themes at 375px. No AC5 case skipped.

The inherited local gate logs were inspected, not re-run for this documentation-only close-out:
ruff, format, mypy, recursive shared/web tests, shared/web typechecks and builds, local Postgres
pytest, Chromium/Firefox and jobs all passed after the invitation-ordering test fix.

## Acceptance checklist

| Criterion | Evidence and outcome |
|---|---|
| Owner checkpoint before build | Approved all eight recommendations, #345; built contract in #346. |
| Proposer, showing snapshot, any active invitees and four reply states | API tests cover proposal validation, snapshot persistence, profile eligibility and three people on one trip. Passed. |
| Shared replies, accept/reset, move, keep, invite more, cancel, source flags | API regressions cover each transition, old revisions, cancellation and withdrawn/moved/deleted showings. Two-person E2E covers propose, suggest, accept and cancel. Passed. |
| Six pushes, existing switch, outbox and retry safety | Wording, suppression, duplicate writes and revision keys covered by API tests; E2E reads decrypted fake pushes. Morning-of job case passed. Real-phone receipt unverified. |
| Trip page, film page, Movie night, Needs you and Home | Browser flow covers these surfaces at 375px in both themes; past trips and withdrawn showing included. Passed in the suite; phone rendering unverified. |
| Two additive tables, reversible migration and guarded grants | Postgres migration reversal passed; downgrade refuses existing trips. Live migration is 072; both tables and both role grants confirmed. No credential columns in these tables. |
| Concurrent replies, reply after cancellation, simultaneous suggestions, accepted suggestion, withdrawn showing, three profiles | API regressions and the separate two-connection row-lock regression passed. |
| Full gate, two signed-in people | Seven-job exact-commit PR/main gates passed; two-person browser flows passed. Owner observations remain explicit above. |

## Production read-back

At 13:53 UTC on 7 Nov, the API health and web version both reported the full merged SHA.
Readiness reported `db: ok`; push, AI, eBay, TMDB and Brave all reported `configured`.
A read-only-role transaction, rolled back after SELECTs, confirmed:

- Alembic 072; zero rows in each new table.
- SELECT granted on both tables to both `mcu_readonly` and `mcu_backup`.
- Expected columns, ten indexes, nine check constraints and both update triggers present.
- For Craig and Mark, the app's trip read services return zero upcoming/past trips, no
  Needs you trip items and no next trip. These were direct service reads, not authenticated
  HTTP requests.
- 137 confirmed future Wild Horse Nine showings available.

Separate catalogue-only privilege checks confirmed neither role can SELECT the whole
`profiles` table or its `pin_hash` column. No credential values were selected.
Raw read-back and gate evidence remain in the ignored `scratchpad/ac5` directory.

## Failures and limits

The implementation session fixed a JSON-null/SQL-NULL mismatch that would have broken keep
and move, and an ordering assumption in one new invitation test; the full API rerun passed.
Existing whole-answer tests gained the two additive empty fields, and page mocks gained the
trip read. No assertions were weakened to match faulty behaviour. No code, infrastructure,
credentials or live data were changed by this close-out session.
