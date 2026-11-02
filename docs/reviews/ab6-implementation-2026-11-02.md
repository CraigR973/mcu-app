# AB6 — Cinema programme ingestion

Accepted contract: docs/reviews/ab-cinema-build-contract-2026-11-02.md (#327).

## Ledger acceptance criteria, verbatim

**Contract accepted 2 Nov (#327).** Complete source/build basis:
`docs/reviews/ab-cinema-build-contract-2026-11-02.md`, including #326 release-category filters.
Start after planning integration on clean green main. Real all-nine coverage/dry-run/count/
write/enable checkpoints remain; historic evidence does not prove complete horizons.
Re-plan if source feasibility changes scope. No new paid service, hosting or credential.

- Implement approved sources/coverage from approved real specimens. Programmes are separate
  from the release calendar and owned catalogue; browsing creates no copies or diary entries.
- Preserve stable identity/bookings, deduplicate ingestion/source overlap and handle
  cancellations. UTC storage and Europe/London display/DST must agree. Original release
  year, reissue date and missing identity/year remain distinct; ambiguous film matches stay
  unresolved rather than being linked to the wrong catalogue title.
- Failed/empty/stale/partial/healthy refreshes have distinct coverage/timestamps. Bound
  requests and retention. A stale screening cannot masquerade as bookable; a fetch failure
  cannot mean “nothing showing”. Follow approved licence, rate and attribution conditions.
- Authenticated shared-zod API, approved route-inventory additions, guarded read/backup
  grants and reversible migration. Reuse existing jobs only if suitable; hosting/variables/
  credentials need owner approval. Update the architecture map when the pipeline changes.
- Real-Postgres/provider-fixture/job/DST/failure regressions, full gate/exact-head seven-job
  CI and production SHA/readiness. Stop before approved live acceptance runs; report actual
  venue coverage and freshness without a blanket “nine cinemas work” assertion.


## Verification record

Planning PR #124 merged 6b4199fea20a22f2c631f19634add46317c2669c after clean local
gate and seven-job PR CI 41443729954. Exact-head main CI 41445893500 also passes all seven
jobs; production API/web serve that SHA, db ok and all five integrations configured.
AB6 starts from this clean green main on feat/ab6-cinema-ingestion. Tier: Extra High.
AB7 remains excluded until AB6 acceptance.

Local baseline: 2,549 API tests without skips, shared 159/web 736 tests and all remaining
batch-verify checks pass. Initial initdb locale failure corrected by UTF-8 environment;
initial Unix-socket run skipped nine localhost-only tests, then actual isolated localhost
Postgres verified by data_directory and full API suite rerun without skips. No weakened
assertions. CI browser skips are the three existing documented platform limits.

Implementation is now starting; verification below must be updated before close-out.
No production source/write/enable acceptance is claimed.
