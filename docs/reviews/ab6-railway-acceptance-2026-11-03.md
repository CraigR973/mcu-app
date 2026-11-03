# AB6 production programme acceptance — 3 Nov

Ingestion PR125 merged normally at72ff0bd after all ten clean local gates and all seven
exact PR CI41678065707 jobs passed. The disabled deployment serves that exact API/web
SHA, db ok and all five integrations configured. Migration071 adds five isolated tables
and seeds nine disabled venues. No source run happens in a person's programme GET.
Main code CI41681152577 passes all seven jobs/API2621/no skips/C63/F62+1/W61+2/jobs6.
All AB6 production criteria are met at merge72ff0bd. Final handoff354f34c passes exact seven-job main CI41683888744; exact API/web/full
readiness was freshly rechecked23:20UTC before the separate authorised AB7 branch.

## Existing Railway runtime source proof

One standing-approved #334 read ran17:09 UTC inside the existing API container, using its
real source code/settings, ordinary anonymous HTTP and the existing TMDB token. No new
service, browser, credential or schedule. 63GET, all200,12 optional metadata GET,
57.076sec,6,573,527 decoded bytes, within all accepted request/time/body/rate bounds.
Vue page and both today/tomorrow dates succeed in this same pass. No retry/alternate.

The fresh ab6-3 artifact passes the real all-nine loader:1,838 rows,1,739 future at review.
Five rows absent from the earlier local1,843-row sample all started before this observation:
Cineworld16:30/16:40×2; Vue16:25/16:45. No new or future removal. This is a fresh complete
artifact, not an earlier failed prefix plus later rows. Actual horizons below; no blanket
14-day completeness. Vue's two selected dates are complete; other complete-date sets empty.

| Venue source key | Rows | Observed days in Nov |
|---|---:|---|
| odeon-kilmarnock | 167 | 03, 04, 05, 06, 07, 08, 09 |
| odeon-glasgow-quay | 335 | 03, 04, 05, 06, 07, 08, 09 |
| odeon-braehead | 323 | 03, 04, 05, 06, 07, 08, 09 |
| odeon-east-kilbride | 253 | 03, 04, 05, 06, 07, 08, 09 |
| cineworld-silverburn | 526 | 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| vue-st-enoch | 70 | 03, 04 |
| everyman-glasgow | 130 | 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 14, 15, 16 |
| gft | 20 | 03, 04 |
| science-centre-imax | 14 | 03, 05, 06, 07, 08, 12, 13, 14, 15 |

Raw snapshot SHA256 `5c1c31317fdfbf70683f0eea50ec54f64409a23acbf5e777450842fb6b8ed71d`; immutable compressed snapshot and exact
scope/request audit/body hashes/counts are retained with this report. Cookie/auth-header/
key values and raw provider bodies are absent. Collector process peak RSS122,535,936bytes;
this is not whole-container peak, a capacity allowance or invoice proof.
The read left every cinema count/all nine disabled flags and all measured core counts
unchanged. No catalogue/diary/auth data write occurred.

## Exact reviewed write and enable

Standing #334 authorises the known exact programme-only import and nine enable flags.
The fresher Railway artifact was reviewed/validated before the write:1,838 raw rows,
three exact Vue source-key mappings (Pan's Labyrinth→1417,Wicker→1195803,Ghosts→1643567),
independent source directors/fingerprints, Pan's Labyrinth also distinct original title.
Mapping count3/SHA256 `de1744b74c5008eb8e3c5eebdb87b668afe92d2351a1fa49f87fd4895a230f37`.
The earlier larger1,843-row exact CLI rehearsal passed locally. Fresh runtime loader and
mapping validation also pass; no review timestamp or row facts were reset.

One exact guarded CLI import then enable9 completed17:13 UTC:1,838 screenings,163 source
film identities,3verified/160unverified. Older1,Unclassified1,837,New0. Source requests
were forbidden during the write; no external data was fetched. Stable source keys,
per-venue atomic promotion, fenced run and the normal audit/heartbeat boundaries apply.
The authenticated Craig admin actor was checked against the existing profile. No replay,
catalogue/diary/auth change or destructive history/schema operation.

Core movies/copies/diary/profiles/refresh-token counts match immediately before/after.
Both read/backup roles can SELECT all five programme tables; catalogue privilege functions
prove PIN-hash and refresh-token credentials remain withheld, without selecting credentials.
Disabled programme reads first returned zero films/nine disabled venues for both people.

## Authenticated production read proof

Eight enabled GETs (Craig/Mark × All/New/Older/Unclassified) all200; unauthenticated401.
All-films14-day reads return1,739 future showings/152 programme groups/1,738 validated booking
links, three verified film identities, no truncation, selectionComplete=false. Per-filter
counts remain independent of category selection:New0/Older1/Unclassified1,738. Older
returns Pan's Labyrinth's19:30 anniversary showing. Original year/ownership/watch remain
unknown where no verified catalogue match exists; no date/age heuristic fills them.

Read checks used60-second bearer tokens only in server memory, no PIN attempt/login/
refresh record/key output. Core and cinema counts stayed unchanged. Fixtures separately
prove differing personal watch histories; identical live nulls are not claimed as a
live personal-history difference. Actual source/booking access is not a ticket purchase
or availability guarantee.

Production pg_database_size112,304,128→113,737,728bytes since pre-schema baseline:
+1,433,600bytes including schema/import. Existing compute/storage/bandwidth remains
unpriced; source subscriptions£0, no new paid tier/service/spending-limit change. Only the
existing morning-job API token reference was applied with skip-deploys; fresh plan0/1/0
leaves unrelated API restart drift unapplied.

## Acceptance criteria and limits

| Criterion | Proof and retained limit |
|---|---|
| Approved sources/coverage and separate domain | All nine pass independently on local/Railway; five isolated tables; actual horizons explicit. No catalogue/diary import. |
| Identity/bookings/dedupe/time | Real specimens, exact mappings/directors/fingerprints, stable source IDs, UTC/London/DST/conflict/cancellation tests; current source booking provenance. No title-only merge or availability claim. |
| Failure/stale/partial/bounds/retention | Real prior failures preserved; failed prefixes never promoted; source limits/age/unchecked dates explicit. Fixture/real-Postgres fencing/lease/refusal/retention tests pass. |
| Auth/shared schema/migration/grants/jobs | Authenticated shared-zod API, route inventory, migration round-trip and populated downgrade refusal; actual071/role/credential checks, existing job phase isolated after reminders. |
| Full gate and live acceptance | Local API2621/no skips/shared167/web738; exact PR C63/F62+1/W61+2/jobs6, production exact SHA/readiness, two source passes, exact write and16 filtered reads. Main CI41681152577 also all seven; final handoff CI/readiness is the remaining close-out check. |

Recurring scheduled refresh has not run since enablement; tomorrow's08:00UTC pass is not
claimed observed. Future access/reuse/completeness is not guaranteed; refusals stop/disable
the affected host and require review. New category population is unproved and is not
inferred from recent release dates. Original-year uncertainty remains distinct. Those
accepted data limitations stay visible in AB7; no owner evidence is fabricated. AB7 and
all other sittings have not started.

Failure record: prior source401/403 samples remain failed/non-importable; the changed Vue
protocol was explicitly re-planned/approved before implementation. Earlier assistant and
WebKit movie-night blockers were repaired causally in separate PR126/127 and integrated
only after full gates/deploy proof. No failing run, assertion, skip or source sample was
waived. The Vue fixture initially needed a line-length/format correction; no suppression.
The latest local/PR/main/source/import/read checks encountered no new product failure.
