# AB6 free-source gap investigation — 2 Nov

## Result and checkpoint

The approved report-only investigation (#329) is complete. Vue returned 73 dated
showings for 2–3 Nov, then HTTP 401 for 4 Nov; requests to Vue stopped immediately.
TMDB returned metadata for all three examples. Its official FAQ confirms free
non-commercial API use with attribution. No implementation, database, credential,
hosting or subscription change was made. No production database was connected.

Some programme data has now been observed for all nine venues across separate research
passes. This is **not a fresh eligible all-nine artifact**, proof of recurring access,
or proof of Vue's full 14-day coverage. The eight-venue artifact from #328 remains
ineligible. The Vue research snapshot must not be spliced into it or imported.

Implementation remains stopped at the revised-build checkpoint below. AB7, AA10c and
all other sittings remain unstarted. PR #125 stays draft/unmerged; main/production
remain at 6b4199f. No production merge/deployment/import/enable is authorised here.

## Approved scope and actual use

Craig's latest “proceed” accepted the exact proposal in
[the preceding dry-run report](ab6-live-dry-run-2026-11-02.md): at most 14 ordinary
Vue date GETs plus 12 existing-TMDB/documentation GETs, 26 combined/five minutes,
15 seconds/request, 2 MiB/response, 64 MiB total, at most two concurrent, and at least
one second between starts per host. Refusal stops that host with no retry or alternate.
Only already configured credentials were allowed, and only for the existing TMDB API.
No writes, paid service, model calls, new credentials or hosting changes were approved.

The pass on clean 64df3063902fc0000645e4a5639dd21c23f2061a finished at
17:10:31 UTC: 13 GETs, 634,850 decoded bytes, 12.921 seconds. It used three Vue GETs
and ten TMDB/documentation GETs, sequentially. All successful responses stayed within
the response cap; non-200 bodies were not ingested. No retry, redirect follow or
additional pass followed. Unused numerical quota does not authorise another experiment.

The local evidence directory is `scratchpad/ab6/gap-2026-11-02T171018Z/`.
The portable [JSON evidence and request audit](ab6-free-gap-investigation-2026-11-02.json)
contains the public request URLs, successful response digests/decoded counts and status
sequence, but no credentials, auth headers, copied plots or image files. It also preserves
the unmodified research result's candidate uncertainty. The offline corroboration below
is a separate evidence layer; it does not silently apply a global mapping.

## Vue: ordinary request format helps, but does not resolve access

The new experiment used the previously recorded ordinary public request format:
literal ISO-time colons, an identifying private-app user agent and ordinary Accept
headers. These differ from the collector's encoded-colon request; more than one factor
changed, so query encoding is not a proved cause of the earlier refusal.

| Requested London date | Response | Interpretation |
|---|---|---|
| 2 Nov | 200 | Parsed programme date. |
| 3 Nov | 200 | Parsed programme date. |
| 4 Nov | 401 | Stop Vue; no later date requested. |

The parser emitted 73 showings, no parse errors, and marked 2–3 Nov observed/complete
for these particular responses. This does not prove all sessions in Vue's system were
published or that the same requests will work tomorrow. No login, browser, proxy,
impersonation, authentication workaround or provider switch was attempted.

**Recommended scope amendment:** request only today and tomorrow for Vue, with the
observed ordinary public format. Keep the application's 14-day selectable window,
but explicitly mark later Vue dates “Programme not checked for this date”. All nine
venues remain represented. A future refusal on either requested date still fails the
venue snapshot and disables its showing actions under the existing failure policy.
Never hide a refusal by publishing the successful prefix as a healthy venue. No fresh
request is authorised by this recommendation; a future acceptance pass needs its exact go.

A 14-day Vue collector is rejected for now because 4 Nov refused. A reduced eight-venue
build is rejected because all nine remain the owner's scope. This shorter horizon is
a proposed limit, not a finding that Vue deliberately offers a two-day API.

## TMDB: free metadata exists; current-run proof remains a separate problem

[TMDB's official FAQ](https://developer.themoviedb.org/docs/faq) was checked first.
It confirms “free to use for non-commercial” use, subject to attribution. This private,
non-commercial app can use the existing integration on that basis. Source fees are £0;
existing network, compute, quota and storage consumption remain unpriced. Retain the
required TMDB attribution and the app's existing attribution treatment; do not imply
TMDB endorsement or guaranteed completeness.

The subsequent nine API GETs were one search, one movie detail with credits and one
release-history request for each example. Search generates candidates, not identity.
No application mapping, year, run category, catalogue or diary row was written.

| Captured example | Candidate release history | Remaining uncertainty |
|---|---|---|
| Clayface — 1400940 / tt34890576 | GB limited 19 Oct 2026; GB wide 23 Oct 2026; James Watkins. | Recent dates do not establish this showing's first-run status. |
| Interstellar — 157336 / tt0816692 | GB wide 7 Nov 2014; explicit IMAX anniversary re-release 20 Sep 2024; Christopher Nolan. | A 2024 event does not establish the nature of a 2026 showing. |
| Pan's Labyrinth — 1417 / tt0457430 | GB wide 24 Nov 2006; Guillermo del Toro; no 2026 GB event recorded. | Missing 2026 history does not disprove a current reissue. |

Premiere/festival, digital and physical release events remain distinct from limited/wide
theatrical events. The earliest recorded GB theatrical event is evidence from an incomplete
database, not necessarily the first ever GB release. A recent primary/global release date
cannot stand in for an original year or a current first UK run.

### Independent source identity evidence inspected offline

Cineworld's saved movie objects have null runtime/director/release fields for these
examples. Its Pan's Labyrinth original programme title includes Guillermo del Toro and
its current programme title explicitly says “20th Anniversary 4K Restoration”. Interstellar
has no equally strong inspected director/year corroboration in that source sample.

The full saved Vue response from 31 Oct contains more metadata than the minimal fixture:
Clayface (HO00020288) names James Watkins; Pan's Labyrinth (HO00021545) gives original title
El Laberinto del Fauno and director Guillermo del Toro. These agree with the TMDB candidates
independently of title search. Vue's runtimes are 108/119 minutes versus TMDB's 109/118;
these differences are retained, not silently rounded into exact matches. Vue release dates
are 23/30 Oct 2026; the Pan's Labyrinth anniversary proves why that source date must not
be treated as its original year. The shared numeric filmStatus value also occurs on new
films and anniversary screenings, so it is not an evidenced first-run classifier.

CinemaTimes' saved Clayface card has 108 minutes and a TMDB-hosted poster path that differs
from TMDB's current primary poster. Neither a copied poster path nor its difference verifies
or disproves identity. No image request was made. The 31 Oct Vue evidence is historical;
it does not establish the identities or classifications of every row fetched on 2 Nov.

This supports a reviewed, corroborated matching path for some films, while Interstellar
and source records lacking corroboration stay unresolved. No title-only linking, automatic
poster-key linking, catalogue creation or cross-provider grouping is justified by this pass.

## Proposed revised build contract — not accepted or implemented

This is an amendment to the accepted #327 contract, within AB6 on its existing branch/PR.
AB7 remains its own later branch/PR. All unchanged coverage, privacy, failure, retention,
request-budget, navigation and owner-checkpoint requirements in #327 remain in force.

1. **Vue coverage:** adopt the two-date request limit described above. Preserve all nine
   venues and honest per-date coverage; leave other adapters' observed horizons unchanged.
2. **Metadata:** add bounded TMDB search/detail-with-credits/GB-release-history enrichment
   to the existing cinema child phase, after programme collection. Programme collection
   has priority. At most 12 metadata GETs per daily pass, within the existing combined
   120 GET/five-minute/64-MiB ceiling, rate/timeout/size limits and refusal-stop rules.
   No searches on authenticated programme GETs or page views. No provider fallback,
   model calls, images or plots. Remaining backlog is explicit, never a claim that every
   source title was enriched. Up to four simple three-call candidates fit the sub-cap;
   ambiguous search results can consume budget without yielding a resolved identity.
3. **Cache and review:** store bounded provenance, source identity fields, candidate IDs,
   fetched dates and relevant GB theatrical events in the cinema domain's existing
   evidence fields. Reuse positive metadata for 30 days and negative/ambiguous results
   for seven days; a changed source identity/title invalidates its candidate cache.
   No new table, catalogue writes or browser schema expansion is proposed. Source refresh
   must preserve reviewed identity/metadata rather than overwrite it with null fields.
   Explicit global IDs and previously verified mappings can be reused. New search matches
   remain candidates until a dry-run mapping report is reviewed: source title plus an
   independent identity fact such as director/original title, conflicts and provenance must
   be visible. The owner approves exact source-key/global-ID mappings before any import.
   Title-only and poster-only matches never become verified. Conflicting evidence clears
   active grouping/classification until resolved. The current three candidates are not
   pre-approved mappings.
4. **Run categories:** retain the accepted strict definitions: New releases needs current
   first UK theatrical-run evidence; Older films needs a corroborated returning/repertory/
   reissue showing of any age. An explicit anniversary/restoration label plus verified
   identity and earlier theatrical history can support Older. A past unrelated reissue
   cannot label the current showing. Dates, missing reissue tags and numeric source status
   alone cannot support New. Unknown stays Unclassified. This pass cannot promise populated
   New releases results; no 90-day, one-year or ten-year proxy replaces the accepted meaning.
5. **Credential/configuration boundary:** the tracked Railway configuration gives the API
   the existing TMDB read token, but declares no token reference for cron-reminders.
   Automatic metadata therefore needs one proposed reference from that same existing API
   secret into that existing job only. No new secret/provider/service/schedule/paid tier is
   proposed. This has not been applied, and the live job's variables have not been inspected.
   Acceptance of this build amendment permits preparing the exact configuration diff and
   read-only plan; an actual Railway change waits for separate explicit approval of that
   plan. Do not print the token. Missing credentials mean metadata unavailable, not a
   notifications failure or a reason to configure production silently.
6. **Validation and later gates:** add real-specimen regressions for ordinary Vue formatting,
   two-date coverage and refusal atomicity; candidate-versus-verified identity, conflicting
   metadata, persistent mappings, cache expiry, budget exhaustion and disabled/no-token job
   isolation; anniversary/first-run/unknown categorisation. Run the complete local gate,
   exact-head seven-job CI, browser/jobs and migration checks after implementation. Update
   the architecture map with the proposed metadata path. Only then propose a fresh bounded
   all-nine acceptance read. Review its actual rows/horizons/categories/mappings; exact
   deployment, production import and nine-row enabling remain separate owner decisions.

Manual local metadata enrichment is the alternative: it avoids changing the job's token
reference but needs repeated operator runs and cannot keep metadata automatic with the
accepted morning refresh. Recommend the existing-job reference, with the explicit apply
checkpoint above. A new service/API background timer is rejected because it adds architecture
and operations without solving unreliable source evidence.

Engineering cost is an additional AB6 implementation and full verification cycle, followed
by fresh acceptance evidence and continued source maintenance. No reliable completion-time
estimate or zero hosting-bill guarantee is established. Wrong identity could group different
films and mislabel screenings; failed access could leave dates unavailable. These risks are
why candidate review, unknown states, refusal stops and the exact production gates remain.

## Decision needed

1. Accept the proposed amendment as a whole: Vue today/tomorrow, capped free TMDB metadata,
   reviewed corroborated mappings, unchanged strict New/Older rules, and preparation of the
   existing-job token-reference diff/plan. Recommended because it preserves nine venues,
   £0 source fees and evidence quality. Cost: the extra implementation/gate cycle, metadata
   backlog and potentially many Unclassified films. This does not authorise a new live
   source pass, production configuration apply, deployment/import/enable or AB7 start.

If rejected, keep the current draft unchanged and do not substitute a smaller or differently
labelled build. This report closes only the authorised investigation.
