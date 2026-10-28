# AB1 — actionable attention: build and verification, 28 Oct

## Authorisation and base

Group AB sitting 1 only: AB1 then AB2 review/build, sequentially; no sitting 2 or AA10c.
Planning commits 00e1c0b, 09b8c90 and dc2f046 preserved by merge PR #117, d413b4d.
Full documentation diff reviewed; PR CI 40747824022 and main CI 40751226004 passed all seven jobs.
Production API/web matched d413b4d; db ready and push/AI/eBay/TMDB/Brave configured.
Implementation started from clean main. Ledger setting: Deep/High.

## Batch title, goal and acceptance criteria (verbatim)

### AB1 — Needs attention must describe something actionable

- Reproduce the reported 1 waiting proposal and 48 year disagreements with zero actionable
  queue/doubts. Health checks use the destination's current ownership, identity and
  unresolved-state rules. Never delete historical evidence just to hide warnings.
- Regress resolved/kept/moved/binned/sold cases, still-owned unresolved cases and a genuine
  old proposal. A resolved old lookup cannot keep a warning alive.
- Resolution refreshes attention. Reconcile/refresh the server's saved daily result as
  needed; browser invalidation alone cannot fix a false saved warning. Preserve operational
  checks and once-per-new-problem push behaviour; no fabricated live check or notification.
- Links reach the correct settings tab/list: eBay, assistant, identification and jobs.
  Owner-only issues give guidance. Another person's device warning must not imply that
  Craig's own device settings repair it. Test the destination's content, not just hrefs.
- Full local gate/E2E, exact-head seven-job PR/main CI and production SHA/readiness;
  read-only live comparison of attention versus its actionable lists.


## Verified starting discrepancy

Read-only live application functions: waiting queue 0, open-doubt films 0, but both calculated
and saved identification checks reported 1 waiting proposal and 48 year disagreements.
No historical rows were deleted, check recorded or notification queued.

## Design decisions

- Daily identification checks share current queue ownership/identity and actionable-doubt rules.
- Home reconciles identification warnings against current lists on every read, retaining the
  daily snapshot and freshness signal for operational checks. The GET does not write, run
  providers or queue pushes. The next genuine daily check updates its saved results normally.
- Resolution and successful collection writes invalidate attention; replay refresh does too.
- Destinations select existing Settings tabs and identification sections. There is no Admin
  jobs screen: existing controls get honest labels; Railway-only failures get owner guidance.
- Another profile's phone warning instructs that person to use their own device/account.
  PIN lock history has no repair in generic Settings and receives honest guidance.
- Craig approved the scoped obsolete test-expectation corrections in this chat before code.
  Regression coverage is retained and extended; route/access assertions remain unchanged.

## Verification

Focused checks: 46 API cases and 8 web cases passed; API lint/format/mypy and web/E2E
TypeScript checks passed. The live database was queried read-only with the corrected local
functions: queue 0, open-doubt films 0, both calculated warnings clear, reconciled attention
empty. The saved daily snapshot remains 1/48 and its timestamp is unchanged. This is local
query verification against live rows, not a deployed authenticated browser observation.

The focused Chromium flow proves a real Keep clears Home's cached warning on client
navigation, without another daily run or lost historical evidence. The completed full
gate/E2E, exact-head CI and deployment verification are recorded below.

## Failures and repairs

- GitHub connector PR creation returned 403; authenticated gh created planning PR #117.
- First read-only probe passed sslmode directly to asyncpg; connection option translation
  fixed it before the successful live query. No database write occurred.
- Disposable pgserver initially refused the host locale; en_US.UTF-8 fixed initialisation.
- Planning baseline's socket URL skipped nine localhost-only collection tests: loopback was
  enabled on that throwaway server and all nine passed. No production connection used.

- Ruff caught one long sort expression and then the attention router's docstring wrapping;
  both were reformatted/wrapped, with no ignored rule. Final lint/format passed.
- First focused browser run: the new card selector omitted the displayed year; the new
  destination assertion selected hidden sidebar text. Corrected the exact title and scoped
  destination content to main. Second run: the valuation page's mobile-hidden duplicate
  heading was still matched; the test now asserts its visible Used-sale tracking control.
  These repair new test selectors; no pre-existing assertion was weakened.


Focused Chromium rerun: both flows passed (no retry/skip). Inspected 375 px screenshots of
attention in dark/light and the mixed destinations/guidance. Existing collection content
was not redesigned. React review found no hook-order, role/accessibility, unsafe rendering,
new dependency or bundle concern in the changed components. Manual replay also refreshes
attention, alongside automatic replay and successful mutations.


## Completed gate and close-out

All ten local checks passed on clean `65ccf0ee5483550428e7144428b3e8ce408344d9`.
API: 2,519 passed, zero skips (all 16 derived-field trigger cases); shared 157; web 729.
Full local E2E: Chromium 49; Firefox 48 plus the existing documented dictation skip; cron 6.
WebKit is unavailable on this Mac's macOS 13, so its evidence is CI, not a local claim.

PR #118 exact-head CI 40755436621 passed all seven jobs. Merge `ad2c992` has exactly the
same Git tree as the clean local gate commit; merge CI 40757500111 passed all seven jobs.
CI browsers: Chromium 49, Firefox 48 plus one documented skip, WebKit 47 plus two documented
skips; cron 6. No new skip or retry. Both new AB1 flows passed in all three CI browsers.
API and web served the full merge SHA with db ready and push/AI/eBay/TMDB/Brave configured.

### Acceptance outcome

1. Reproduction: live application reads reproduced saved/calculated 1/48 against 0 queue and
   0 open-doubt films. Corrected shared predicates return no identification warning.
2. Regression: resolved film/series, skipped/set-aside, kept/corrected/moved doubts,
   copy move/bin/sale/donation, deleted film, still-owned open doubt and genuine old proposal
   are covered against real disposable Postgres; historical rows survive.
3. Freshness: a real Keep clears cached Home on client navigation; successful mutation and
   manual/automatic replay refresh attention. Read reconciliation neither mutates the saved
   rows nor queues a notification; existing daily-record/push-once tests and cron flow pass.
4. Destinations: browser tests open real eBay/Assistant/Notifications panels, Disc specs,
   Collection value and identification content. Other-person devices and Railway-only jobs
   show guidance. There is no fictional Admin jobs screen and no route-inventory change.
5. Gate/deployment: full local, exact-head PR/main seven-job CI and API/web SHA/readiness
   passed. Read-only live comparison is queue 0, doubt films 0 and attention response empty,
   with the historical saved 1/48 and daily timestamp unchanged.

The live-data comparison invokes the merged application's real functions/attention handler
inside a read-only transaction. It is not a production browser sign-in or an authenticated
HTTP attention response. Browser → API → Postgres behaviour is established by the complete
fixture-backed E2E suite. No live collection/evidence write, provider/model request or push.

Additional workflow repair: gh pr edit hit GitHub's retired Projects API; the exact PR body
was updated via the supported REST endpoint. No product or gate change was needed.

AB1 is complete. AB2 starts with review only and stops for layout/exact stats-contract picks.
Sitting 2, AA10c and the existing valuation/device checkpoints remain outside this close-out.
