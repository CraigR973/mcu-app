# Next owner checkpoint: fresh AB6 acceptance read

Status: **approved and completed once on 3 Nov (#332); permission spent.**
Craig said “approve”. Clean a038709 exact-head PR CI 41550182406 passed all seven jobs
before execution. Result: 62 GETs/12 metadata/60.197s, eight venues/1,800 rows; Vue's
4 Nov 401 fails the all-nine gate and quarantines its 49-row prefix. No retry/alternate
or production action. Complete report/audit/snapshot: ab6-acceptance-read-2026-11-03.md/JSON.
The separate repair and integrated build remain verified; live acceptance is unmet.
The following is the approved historical scope, not permission for another pass.
New report-only proposal ab6-vue-session-plan-2026-11-03.md is UNAPPROVED and unrun.

The approved proposal was one fresh, anonymous programme pass across the existing nine selected venues,
using the accepted six HTTP source families and £0 source subscriptions. London civil
window: execution day through +13 days; Vue execution day/tomorrow only. Later Vue dates
remain explicitly unchecked. No alternate provider, browser or access-control bypass.

At most 120 GETs total, including at most 12 optional TMDB metadata GETs using the existing
read token. Five minutes total; 15 seconds and 2 MiB per response; 64 MiB total; two global
requests in flight; at most one request start per second per host. A refusal stops that
host without retry or switching. Metadata remains candidates for later review, never
implicitly accepted film mappings. No resume-after-refusal flag is implied by this note.

Run against an owned disposable localhost database only. Save the normalised artifact,
SHA-256, exact counts, venue/date horizons, omissions/refusals, category/year/mapping
confidence and metadata backlog for owner review. New/Older retain the strict accepted
run-based rules; Unclassified and any zero New count remain explicit, not guessed away.

This approval authorised only this completed read experiment, with zero production writes,
configuration apply, deployment, imports, mapping selections or enables. Source fees £0;
existing compute/network/quota use is unpriced. The saved rows/hashes/counts and exact
mapping/config/import/nine-row enable remain separate owner decisions. Re-plan before
implementation if new feasibility evidence changes the accepted scope. AB7, AA10c and
all other sittings stay excluded.
