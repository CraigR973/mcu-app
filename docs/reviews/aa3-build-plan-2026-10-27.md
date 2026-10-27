# Collection summary — build plan from Craig's picks (AA3)

27 Oct 2026 · baseline `c454518` · review commit `38619f2`

**Picked by Craig:** Compact summary; count, label and value-explanation corrections;
**keep both watched and identified, with clearer definitions**. The review's recommendation
to remove them was rejected. This plan follows his picks, not that recommendation.

**Approved by Craig before implementation, 27 Oct:** two additional counts in the existing
stats API response: physical copies, and copies with both physical and download formats.
This is a data-shape change under Craig's “Before anything consequential” rule.
Craig explicitly answered “Approve and build AA3”. No data migration or live data operation is needed.

## How the chosen layout will work

The section keeps five numbers. Two fixed columns show Titles owned and Copies catalogued;
the estimated value spans the width; two more columns retain You've watched and Matched on
TMDB. All five are readable without swiping. On smaller phones the text wraps; the page
scrolls vertically. Other Home shelves keep their existing sideways layout and order.

The Archive action opens the same Archive screen. “Collection breakdown” expands in place
to show the existing format, place, genre, decade and recorded-spending information. Its
charts stack on phones and may use two columns on wider screens. No new route or chart-to-
filter navigation is included. Long place names wrap; purchase-month values are available
on tap/keyboard, not only hover. Recorded spending explains its limited purchase-price
coverage and is distinct from estimated used value.

Open [the selected layout](aa3-collection-selected-2026-10-27.html).
The numbers are the review's 27 Oct production snapshot, not new measurements or final
AA10b acceptance. The shell above and below the section is schematic. The preview models
the summary and disclosure interaction; the build retains the complete current breakdowns.

## Definitions and wording chosen on Craig's behalf

| Display | Meaning / proposed supporting text |
|---|---|
| Titles owned | Distinct currently owned catalogue titles; “Films and TV series” |
| Copies catalogued | Currently owned catalogue-copy rows; physical and download counts may overlap |
| Estimated used value | Stored used-copy estimate, priced/physical-copy coverage and observed-sale coverage |
| You've watched | Existing personal count unchanged; “Distinct titles in your diary, including titles you don't own” |
| Matched on TMDB | Existing identified count unchanged; “Of [owned total] owned titles. A match can still need checking” |

The supporting text prevents personal watches being read as collection progress, and a
TMDB ID being read as human verification. No watch percentage is introduced. The value
explainer retains AA10b's advertised-price and inferred-sale limits; no stored price or
valuation algorithm changes. Snapshot examples: Craig watches 500, not a replacement with
482 owned watches; Mark watches 879, not 878. Identification remains 1,902 of 1,903.

## Approved data change

Add `physicalCopies` and `physicalAndDownloadCopies` to `GET /api/v1/collection/stats`
and the shared response schema. Both count owned catalogue-copy rows, not discs inside a
box set. A physical copy has at least one supported physical format (4K UHD, Blu-ray, DVD),
counted once even when it has several. The overlap also carries the download format.
Use the same physical-format eligibility as valuation and preserve owned/sold/trash rules.
Calculate total copies, downloads, physical copies and overlap in one aggregate SELECT,
so the four counts describe one database snapshot.
No table, column, role grant, new endpoint, credential, provider request or scheduled job.

Existing response fields keep their meaning and values. Old web clients continue to parse
the response with the additional fields. During deployment skew, the new web accepts
their absence and explicitly omits the unavailable physical split; it must never infer it
by subtraction or default missing counts to zero. The value continues to use its own priced
coverage. An independent valuation failure must not remove correct copy counts.

Rejected alternative: derive physical counts and overlap from the separate valuation
response. It avoids the two response fields but couples basic catalogue counts to a
valuation request and combines potentially different snapshots. Summing format bars also
fails because combo copies can have two physical formats. The additional counts are the
correct option; their cost is backend/schema work and compatibility tests.

If this API extension fails, the main risks are wrong totals or response parsing preventing
the summary loading. Additive fields, preserved old fields and an explicit missing-field
state bound that risk. No existing records or prices are rewritten. Reverting the batch
restores the current layout; no database rollback would be required.

## Build and proof, after that decision

1. Add the two independently computed counts and shared schemas together. Exercise physical-
   only, download-only, physical/download overlap, multiple physical formats, sold/trash,
   empty collections and both people against disposable Postgres. Keep every existing
   response field and route/access assertion. Update the contract snapshot only for these
   agreed fields; retain its exact comparison.
2. Replace only this section's horizontal number/chart containers with the chosen summary
   and disclosure. Preserve the other shelves. Keep both personal/identification numbers
   and their current semantics. Cover available, loading, offline, stats-failed, valuation-
   failed, no-value, pricing-running and partial-value cases for both roles.
3. Replace the existing “every Home section is sideways” expectation with a precise
   owner-approved exception for this collection section; continue to assert every other
   relevant shelf is sideways. Add positive assertions for all five visible numbers,
   breakdown reachability and no horizontal overflow. No route-inventory change is needed.
4. Run every `batch-verify.md` command and the complete local E2E suite on disposable
   Postgres. Browser proof covers both roles and themes at 375 px, a 320 px overflow check
   and a desktop view. Preserve CI-only WebKit coverage and the existing documented skips.
   Local failures, repairs and unverified physical-phone behaviour must be reported.
5. Commit and open one AA3 PR. Wait for all seven PR jobs, merge with a merge commit, wait
   for exact-SHA main CI, verify API/web exact SHA and full readiness, and exercise the
   changed Home section with production-backed read-only data. Then complete the ledger,
   architecture reconciliation and session-log close-out from the command procedure.

The work stays on AA3's existing local checkout/branch; it will not absorb unrelated edits.
No production synthetic account, notification, provider scan, valuation refresh or database
write is part of verification. An authenticated production UI session may need Craig;
otherwise report the remaining observation instead of claiming it passed.

## Cost, boundaries and acceptance

Provisional cost: **2–4 agent hours**, including implementation and the full local/CI gates,
if checks pass on the first attempt. CI failures can extend this; the group's stop rules
still apply. No extra hosting charge or paid provider calls. Retaining both numbers adds
one row to Compact summary, making the Home section taller than the review's first mock-up.

The build is accepted only when all five meanings are visible, copy overlap is accurate,
value coverage is honest, every existing breakdown remains reachable, failures are explicit,
other shelves remain unchanged, and required gates/deployment checks pass. Craig's selected
layout authorises the collection-only exception to decision #249, not a redesign elsewhere.

AA9 starts only after AA3's completed cycle and clean local main. AA9 is its own review and
stops for Craig's picks before any assistant build plan. Sitting 6 remains excluded.

**Current state: API extension and build approved; implementation and verification in progress.**

Planning checks: main's latest seven-job run still green at `c454518`; selected mock-up
opened at 375 px and 320 px, with disclosure interaction checked and no horizontal
overflow at 320 px. Documentation diff whitespace check passed. Full implementation
gate has not run because product implementation has not started.
