# AB6 — Cinema programme ingestion

> Current checkpoint update (#329): Craig approved the report-only free-gap investigation
> below; it is now complete. Vue yielded two dates then refused; TMDB supplied three
> metadata candidates. See [the current evidence and revised-build decision](ab6-free-gap-investigation-2026-11-02.md).
> Historical “not authorised” statements below describe the preceding stage. No further
> implementation/new live pass/production action is approved by this result.

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

Implementation is local, with all nine seeds disabled. No production source/write/enable
acceptance is claimed. AB7 and AA10c have not started.

## How the ingestion works

The existing morning command commits reminder delivery and its heartbeat before starting
an independent cinema phase. Disabled seeds make zero HTTP requests. Enabled passes use
bounded anonymous HTTP, preserve per-date coverage and promote each venue atomically under
a dedicated advisory lock plus fenced lease. Run failure cannot turn an old success into
a new observation. A separate cinema heartbeat cannot roll back a published run outcome.

The programme endpoint reads stored observations only. It joins explicit TMDB/IMDb IDs
to the existing local catalogue; it never searches providers or matches titles. Source
film resources stay source-scoped/unverified; a missing source film resource or GFT's
showing-only HTML remains showing-scoped. Remakes and combined programmes are not guessed.
Original cached year, source release date, evidenced first/returning run and evidenced
reissue flag are separate. Unverified classification remains Unclassified.

Booking actions require a confirmed, non-expired, recent observation, an enabled venue,
and no stale evidenced upstream timestamp or newer failed refresh. Missing future rows
from partial dates become Unconfirmed; only proved complete absence withdraws them.

## Verification and known limitations

The focused suite passes 43 checks against isolated localhost Postgres: all twelve redacted
real-source fixtures/hashes; 869 CinemaTimes HTML rows beyond the capped JSON-LD; Vue 19,
Everyman 6, Cineworld 19, GFT 20 and Science Centre's six structured event dates; DST gaps/
folds and offset corroboration; replay/rescheduling; four real future Braehead disappearances;
stale/failed/empty/partial/cancelled/expired observations; atomic rollback and expired writers;
actual advisory-lock/lease exclusion and recovery; nine-venue fixture promotion; exact enable
counts; separate heartbeat and reminder outcome; authentication, personal watched isolation,
unknown remakes, cross-source explicit-ID grouping and all release-category cases.

Eight shared-schema tests pass. OpenAPI response compatibility is checked before AB7 adds
its screen. The existing E2E reminder case also checks nine disabled seeds, zero cinema
runs and zero cinema HTTP calls. Full gate and exact-head CI results are recorded in the
PR description and local verification artifacts before requesting live acceptance.

**Observed metadata limitation:** saved real specimens currently produce no verified run
classifications and no explicit catalogue/global identity matches. Everyman/Cineworld's
scheduled records have null source release dates. The source date/year/category values
remain unknown instead of using title/year heuristics. Synthetic category tests prove the
contract and isolation, not real classification availability. Live dry-run must report
actual category counts and unresolved identities; useful New/Older filtering is unproved
until evidence exists. AB7 acceptance cannot claim this is solved by green tests.

Initial failures retained: new-test assumptions that real release dates were populated
(they are null), CollectionItem's formats field and retention result key corrected; source
resource validation initially excluded valid showings without a film link, fixed by keeping
them showing-scoped (original row-count assertions retained). Ruff formatting/import/line
length and one mypy variable-name conflict corrected. OpenAPI export initially refused the
inherited job role; rerun with the documented PROCESS_ROLE=web. No existing gate assertion
was loosened. The route inventory adds exactly the GET approved in #327.
Review additionally found a state-transition gap: a later complete absence must withdraw
an already-Unconfirmed showing. Promotion and exact dry-run counts now agree, with the
extended regression suite passing all 43 checks. The disposable migration proof also
passes fresh/repeat upgrade, nine disabled seeds, both roles' access to all five tables,
PIN/token privilege withholding, populated downgrade refusal and empty downgrade base.
Draft PR #125 holds final gate/CI results; it remains unmerged pending live acceptance.

### Final code verification, 2 Nov

Code commit `483c1f6f57bd96afd38612824591dd91f5734c7c` passes all ten batch-verify
commands from a clean tree: API **2,592 passed, zero skips**, shared 167, web 737, both
Python static checks/format and all shared/web lint, types and builds. Verification uses
only the owned disposable localhost Postgres, with data_directory checked before use.

Exact-head seven-job PR CI **41464465764** passes, including real Postgres 17, migration
reversal, production-image import/migrate/readiness, dependency audit and all three browser
projects plus jobs. Local browser run: Chromium 61 pass, Firefox 60 pass/one documented
dictation skip, jobs six pass. WebKit runs in CI because this Mac has no supported build.
The local browser run began at parent `20b81be`; the final disabled-job case ran after the
absence fix. Final-head CI, the final local full API suite and focused transition/count
regression cover that fix; no local active-cinema browser acceptance is claimed.

The superseded parent gate was interrupted after the absence fix; its terminated pytest/
pnpm checks are not passes. Its old CI run was cancelled after six successful jobs. Final
verification restarts on the clean final code commit and passes. A fresh disposable database
was migrated with both roles already present, so privilege checks do not pass by absence
of production roles. Local evidence: scratchpad/ab6/implementation-gate/result.json,
migration-proof.json, e2e.log and final-pr-ci-483c.log (gitignored; PR description carries
the portable results). No test/assertion/skip was weakened.

The final handoff documentation's exact-head CI is linked in PR #125. Main/production are
unchanged at `6b4199f`; this is a verified draft, not a shipped or accepted AB6 batch.

## Next owner checkpoint: bounded live read, no production writes

Recommend one local CLI dry-run using the owned disposable Postgres, not production. Select
today through 13 days ahead in Europe/London, all nine approved venues, six existing public
source families. At most 120 GETs, 15 seconds per request, five minutes total, 2 MiB decoded
per response/64 MiB run limit, one request per host per second, at most two concurrent.
401/403/429/challenge stops that host without retries, proxy/browser/provider switching.
Only public programme HTML/metadata JSON and discovered Science Centre event pages; no
scripts/images, credentials, checkout, messages, payment or hosting changes.

The CLI saves a new normalised artifact and digest locally and prints request/byte/venue/
category/change counts. It creates no run, heartbeat, programme or catalogue records in
production. Data fee £0; existing network/compute usage unpriced. No production schema is
required for this local dry-run. Review the actual scope/horizon/category gaps before the
later disabled-deployment, production write-count and nine-row enable checkpoints.

Do not merge/strike AB6 or begin AB7 with these acceptance gates unresolved. Owner approval
of a staged disabled deployment is required if real import acceptance needs the additive
schema deployed before final AB6 acceptance; do not treat a green PR as that approval.

## Approved live dry-run result — 2 Nov (#328)

The exact live-read checkpoint above was approved and executed once on clean 1cfd9b9.
It is complete, not awaiting another approval. Full report/audit and proposed re-plan:
docs/reviews/ab6-live-dry-run-2026-11-02.md and .json.

Actual 2–15 Nov result: 49 GETs, 5,307,435 decoded bytes, 55.122 seconds; eight venues
return 1,185 dated records, of which 1,102 were future/non-expired/non-cancelled at
preparation. Vue St Enoch returns 401; no further Vue request, retry or alternate. No
adapter proves complete dates, all classifications/global identities remain unverified.
Before/after disposable DB counts and nine disabled flags match. The exact hashed
artifact is independently refused by the all-nine import gate. No production DB access,
deployment/write/enable, further implementation or AB7.

Keep all nine/£0 and stop for a new, concrete report-only free-gap investigation decision:
Vue ordinary public request-format comparison (hypothesis, not a diagnosis), and a small
existing-TMDB classification-evidence feasibility sample. Extra metadata requests and a
new experiment after refusal require the owner go described in the new report. Do not
attempt a partial import or silently change the approved category meaning.
