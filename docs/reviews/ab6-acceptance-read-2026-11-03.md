# Fresh AB6 acceptance read — 3 Nov: all-nine gate unmet

Craig's “approve” authorised exactly one pass under ab6-next-acceptance-read.md, not any
production action. It ran once on clean a038709ce65c62d219354005a8e975500b630154 after
exact-head CI 41550182406 passed all seven jobs. The source/build/strict categories remain
accepted (#330); this new feasibility result is not acceptance of a changed build.

## Result and limits

The pass completed at 09:08 UTC in **60.197 seconds**: 62 GETs, including 12 existing-token
TMDB GETs; 6,135,897 decoded bytes (5.85 MiB). The largest response was 1,686,536 bytes,
below 2 MiB. Counts/time/body caps held; all requests were GETs to the approved families.
There were 61 HTTP 200 responses and one HTTP 401. No redirect, retry, alternate provider,
browser, new credential, hosting/configuration change or production database connection.

The build's unchanged throttle reserves request starts one second apart, with two global
slots (this run was sequential). Audit hooks occur later in client construction; their
smallest observed gap was 0.998727 seconds. This is not a proof of exact wire cadence;
the audit retains the timings rather than declaring an exact transport-rate pass or
running again. No rate-related code change was made.

A new owned disposable localhost database was migrated to head first. Every table count
and all nine disabled flags are identical before/after the dry-run. No programme, catalogue,
diary, mapping, run/audit or enable rows were created by the source pass. Local database
setup itself created only the normal migration/seed data. No production writes occurred.

## Coverage and categories

Eight venues completed their selected observations: 1,800 future screenings at preparation.
Vue retained 49 diagnostic rows from its successful 3 Nov prefix, then failed on 4 Nov.
Those 49 are quarantined and excluded from the 1,800/non-failed counts and all proposed
changes. No row is approved for import from this failed all-nine artifact.

| Venue | Non-failed rows | Observed dates in Nov |
|---|---:|---|
| ODEON Kilmarnock | 167 | 3–9 |
| ODEON Glasgow Quay | 335 | 3–9 |
| ODEON Braehead | 323 | 3–9 |
| ODEON East Kilbride | 253 | 3–9 |
| Cineworld Silverburn | 553 | 3–16 |
| Everyman Glasgow | 135 | 3–12, 14–16 |
| Glasgow Film Theatre | 20 | 3–4 |
| Science Centre IMAX | 14 | 3, 5–8, 12–15 |
| Vue St Enoch | 0; 49 quarantined | 3 succeeded; 4 refused |

Every complete-date set is empty: no empty day, complete future horizon or cancellation
is established by this sample. The requested review window was 3–16 Nov; absent observed
dates remain unchecked, not “nothing showing”. Booking/identity/date-strength provenance
is retained in the artifact; nothing is asserted about real ticket availability/purchase.

All 1,800 non-failed rows are **Unclassified**: zero proven New releases, zero proven Older
films, zero verified global film identities. Explicit anniversary/restoration labels exist
in some source titles, but a label alone cannot verify the film identity. Original year
confidence is not manufactured from primary/source/reissue dates. No mappings were picked.

## Vue refusal and metadata backlog

Vue's 3 Nov request returned 200/49 rows. Its 4 Nov request returned 401; the host stopped
immediately and no further Vue request followed. The accepted today/tomorrow assumption
is therefore unproved on this date too. This does not prove a reliable today-only window:
the same 3 Nov date was already reachable in yesterday's experiment.

All 12 TMDB requests returned 200. The cap produced three positive, unapproved candidates
(Clayface, Ghosts: The Possession of Button House, Kiri and Lou Go Raaa!), one ambiguous
record (Forgotten Island), and a reported backlog of 143 source-film keys. The final
Other Mommy sequence did not finish within the 12-GET sub-cap; the recorded SourceError
is a budget limit, not a TMDB HTTP refusal. No extra metadata call followed it.

All three positive candidates are CinemaTimes source keys with no independent source
facts/corroboration. The successful Vue prefix contains director/original-title/runtime
facts, but the entire Vue snapshot failed and is not silently eligible enrichment input.
Current first UK run is not proved by the returned GB release dates; metadata is not a
mapping approval and no first-run or original-year guarantee follows. More title-only
TMDB lookups would not by themselves solve the missing corroboration.

## Artifact and actual import refusal

The complete normalised artifact is preserved as ab6-acceptance-snapshot-2026-11-03.json.gz
(44,512 bytes); decompression reproduces the original 1,238,526-byte JSON exactly.
Original JSON SHA-256:
`fcc8e42c6031357901359d8e83a3a3eae72870650de2b04f5e6434767d595d3f`.

A read-only call to the real artifact loader using that exact digest and count 1,800 refuses:
“vue-st-enoch: source acceptance unresolved; no reduced-coverage write”. No write/import
function was invoked. The full sanitised audit, scope, all coverage dates, candidate facts,
limits, database before/after counts and compressed/raw digests are in
ab6-acceptance-read-2026-11-03.json. Raw local logs remain in the path recorded there.

The initial local runner had an unterminated string and failed at parse time before any
source or database operation. It was corrected before execution. There was one source
pass, not a repeated sample. Two guessed source-file inspection paths also did not exist;
tree lookup located the real modules. Neither read-only error contacted a source.

## Stop and re-plan before implementation

No all-nine source acceptance, production configuration apply/deployment/import/mapping/
enable, AB6 close-out, AB7, AA10c or other sitting follows. Main and production remain the
separately verified assistant repair 6d0f676. Existing code/fixture/CI success cannot clear
this live acceptance failure. Keep draft PR #125; do not reduce to eight venues, loosen
categories or admit the failed prefix without a separately approved new contract.

Recommend only the two-GET/45-second **report-only** anonymous public-page/session
investigation in ab6-vue-session-plan-2026-11-03.md. Ordinary page-session state is a
hypothesis, not an established cause; the proposed experiment is not approved or run.
It keeps all nine/£0 source fees and changes no implementation. Its finding must precede
any revised build contract, further fresh acceptance or production action. Existing
resource use remains unpriced; no guarantee of zero hosting-invoice increase is made.
