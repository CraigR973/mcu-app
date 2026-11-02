# AB6 metadata amendment — 2 Nov

## Accepted scope and implementation

Craig accepted the complete free-gap amendment with “proceed” (#330). AB6 continues on
feat/ab6-cinema-ingestion / draft PR #125. This is implementation under review, not a
deployed or accepted cinema service. No new live cinema/TMDB acceptance pass, production
database connection, configuration apply, schema deployment, import or enabling was run.
AB7, AA10c and all other sittings remain unstarted.

Vue now requests only today/tomorrow inside the selected civil-date window. URLs retain
literal ISO time colons and the observed ordinary identifying/Accept headers. Later dates
remain unchecked. A refusal on either day fails the entire venue snapshot; successful
prefix rows cannot replace accepted data. This is an evidence-based limit, not a claim
that Vue formally supports a two-day API or that recurring access has been proved.

After programme requests, optional TMDB enrichment uses at most 12 GETs inside the same
120-GET/five-minute/64-MiB budget, 15-second timeout, 2-MiB response cap and host rate limits.
No credentials means no metadata HTTP; disabled cinema collection constructs no HTTP
client. API reads make no provider requests. Authentication is sent only to the exact
TMDB API host; no redirect is followed. Metadata failure cannot undo programmes or the
already committed reminders. Refusal pauses metadata in subsequent passes until an
owner-approved new dry-run and reviewed artifact clears it; no automatic provider switch.

Search produces source-scoped candidates. Positive metadata is reused for 30 days,
negative/ambiguous results for seven; transient HTTP/parser errors aren't negative matches.
Source title/director/original-title/runtime/release-date changes invalidate that source's
cache fingerprint. Provider plots/images/auth headers are never stored. Cold-cache requests prioritise explicit returning programmes with source identity facts,
then other evidence-bearing programmes, within the same cap. This does not exclude any
programme or apply a mapping/category automatically. Candidate details
include bounded director/runtime/IMDb evidence and GB limited/wide theatrical events;
festival/premiere/digital/disc events are not cinema-history substitutes.

No new table or browser contract was added. Cinema evidence JSON holds bounded metadata,
source facts and reviewed mapping provenance; existing cinema retention applies. New
search matches need explicit source-key/TMDB-ID selection and independently corroborated
director or distinct original-title evidence. Runtime/poster/title alone cannot verify a
mapping. Prior reviewed identities/metadata survive normal refreshes without being erased
by missing provider fields. Changed/conflicting identities lose active grouping and
classification. No catalogue/diary rows are created or rewritten. Original year stays
unverified unless existing verified catalogue data supplies it; a primary TMDB date is not
silently promoted to an original-year guarantee or first-ever UK release.

The accepted strict New/Older rules remain. A current explicit anniversary/restoration
label, verified identity and earlier GB theatrical history can support Older. Numeric
source film status, a recent date or absent reissue label cannot establish New. Older
metadata about a different reissue cannot classify an unlabelled current showing. Unproved
runs stay Unclassified; a populated New releases filter remains unproved.

## Mapping review and import controls

The saved dry-run artifact now includes typed bounded candidate metadata, source facts,
corroboration and per-pass metadata counters/backlog. It remains bound to the exact artifact
hash and showing count, all nine fresh observed venues, existing admin actor and locks/fences.
Candidate metadata cannot contain duplicate/out-of-scope identities, mismatched source
fingerprints or future fetch times. Old adapter-version artifacts are not eligible for
this changed build.

Import without mapping selections leaves new candidates unverified. To accept selected
mappings in a later owner-approved import, provide a JSON array of `source`, `film_key`
and `tmdb_id` objects through `--reviewed-mappings`, plus the exact
`--confirm-mapping-count` and SHA-256 `--confirm-mapping-digest`; the existing `--confirm-digest`, `--confirm-count` and
`--actor-profile-id` remain required. Each selected candidate must still be fresh, bound
to its observed source facts and independently corroborated. Duplicate/missing/conflicting
or title-only selections refuse before a write. The bulk-import audit records the admin
and exact selected mappings. No mapping selection is approved by the build go.

`--resume-metadata` is valid only with a separately owner-approved new `--dry-run` after a
metadata refusal. It permits that explicit experiment, not an unattended retry or live
configuration change. The unchanged all-nine write/enable checkpoints still apply.

## Railway plan prepared, never applied

The only authored infrastructure diff references the existing API TMDB read token into
the existing cron-reminders job. It adds no secret, service, schedule or paid tier. The
installed CLI could not evaluate the installed railway/iac SDK: minimum CLI 5.42.1.
An isolated `pnpm dlx @railway/cli@5.42.1` invocation under Node 22 successfully produced
the read-only plan; no global CLI upgrade or application dependency change was made.

Plan: **0 to add, 2 to change, 0 to destroy**:

- cron-reminders: add the existing API TMDB token reference.
- api: existing restartPolicyType null → ON_FAILURE drift already documented in the
  Railway runbook; not introduced by the metadata diff.

[Sanitised plan evidence](ab6-metadata-railway-plan-2026-11-02.json) records only counts,
field names and the reference, never the token or full environment. Source fees stay £0
under TMDB's confirmed private non-commercial/attribution basis. Existing compute/network/
quota/storage usage remains unpriced. Actual config apply remains a separate explicit
owner decision on this exact plan; no apply has run.

## Verification record

Focused cinema regressions: 56 passed before the final bare-title guard regression;
full gate and exact-head CI results are appended below once complete. Full-source mypy
passes (262 modules). Fixtures preserve recorded provenance: exact Vue identity fields
from the saved 31 Oct response and normalised metadata from the approved #329 sample.
Test mock envelopes wrap those captured fields; they are not represented as original
full HTTP bodies. No new source sample was taken to construct fixtures.

Failures found and fixed: initial long-line/import formatting and optional-candidate type
narrowing; test helper shifted a fixture start but not its end (both now shift together);
initial infrastructure plan rejected an old CLI (compatible isolated CLI succeeds).
Review additionally tightened the restoration-label guard so a film named Restoration or
Reissue is not itself an edition marker. A later review found explicit global-ID changes
also needed cache fingerprint invalidation and candidate/global-ID agreement; both are
now guarded. The in-progress e0a8d85 gate was deliberately terminated as superseded,
not counted as a pass; final clean-code gates must cover the corrected tree. Exact mapping
selection files also require their own reviewed SHA-256, preventing a same-count file swap.
Final review also quarantines wrong-day Vue groups/sessions instead of filtering them into
an apparently complete empty date. The first 7809d40 local gate is superseded by this
additional source-response guard. That commit subsequently passed all ten local checks
(API 2,608/no skips, shared 167/web 737), but cold-cache review then found metadata budget
could be consumed by uncorroborated CinemaTimes candidates before reaching Vue anniversary
films. Evidence-bearing returning programmes are now prioritised within the unchanged cap.
Its local browser run/CI were superseded by this priority fix; final verification must
cover the resulting tree. Existing assertions, auth, pinned routes and
skip policy remain unchanged.

## Remaining owner checkpoints

After the amended clean full local gate, browser/jobs, migration proof and exact-head
seven-job CI, propose one fresh all-nine bounded acceptance read. Do not execute it without
its exact go. Its actual rows, horizons, categories, independent mapping evidence and
backlog must be reviewed before production actions. Vue may refuse again; all nine observed
in earlier separate experiments does not satisfy that acceptance gate.

Configuration apply, disabled deployment if needed, exact reviewed production import,
mapping selections and nine-row enable remain separately explicit. No merge/close AB6 or
start AB7 while those gates are unresolved. See the current STATUS/OWNER-ACTIONS/ledger.
