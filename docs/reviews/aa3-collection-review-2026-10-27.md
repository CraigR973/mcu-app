# Home's collection section — review for Craig (AA3)

27 Oct 2026 · source baseline `c4545186df73d43880d69de0b96d50db62df64d2`

**Recommendation: Compact summary.** Keep titles, copies and estimated used value visible
without swiping. Put the charts behind an in-place “Collection breakdown” disclosure.
Remove watched and identified from this collection summary. Correct the count definitions
and value explanation whichever layout Craig picks.

**Checkpoint: waiting for Craig's picks.** This is a review and mock-ups only. No product
code, build plan, data write, merge or deployment. AA3 remains open. AA9 has not started;
sitting 6 remains excluded. The three layouts are proposals, not decisions taken for Craig.

## Acceptance criterion, verbatim

> A UI/UX review of Home's collection row as its own report (`docs/reviews/`), with mock-ups, sent
> to Craig; the build is planned from his picks. No code before his picks.

The review/report/mock-up stage is complete when delivered. The owner-picks checkpoint and
any resulting build remain outstanding; the batch must not be struck or closed out yet.

## What the section does today

Home shows the collection after its authenticated artwork, before the film shelves.
It has **five number cards**, in order: Films owned, Copies, Worth, You've watched,
Identified. A second sideways row contains Formats, Where they live, Genres and Decades,
plus Spend over time when dated purchase prices exist. “Browse the archive” sits beside the
heading. The 20 Oct snag's “two number cards” description is dated, not the current UI.

The numbers come from the stats response and a separate stored-valuation response.
They use different units and populations. Home never starts a valuation; its controls stay
in Admin. Both people see the collection; watched is personal to the signed-in person.

At 375 px, two 160 px cards plus their gap occupy 332 px. Worth, the third card, is mostly
off-screen initially. The charts are 288 px each on a phone. These dimensions and the
swipe behaviour are verified in source, not measured on a physical phone in this review.

## Findings, in decision order

1. **The physical-copy split is wrong for mixed formats.** Live stats report 1,927 copies
   and 589 copies tagged download. Home subtracts them and says 1,338 discs. A separate
   read-only count finds 1,472 physical copies: **134 copies have physical and download
   formats**, so they belong to both groups. Valuation correctly uses 1,472 physical copies
   as its denominator. Proposed display: “1,927 copies · 1,472 physical · 589 download;
   134 include both”. These are catalogue-copy rows, not a count of individual discs
   inside every box set. A future fix needs a physical-copy count from the same definition
   used by valuation; rearranging the current subtraction would preserve the error.

2. **The first screen hides its most useful summary.** Worth is behind a swipe, and the
   second swipe row asks people to explore charts before Home reaches film choices.
   Number cards and charts have different reading jobs from poster shelves. Keep film
   shelves as sideways rows; make this one section readable without sideways navigation.
   This is a proposed exception to decision #249, not an unapproved redesign of every row.

3. **“You've watched” looks like collection progress but counts the whole diary.** Craig's
   card is 500; 482 of those titles are currently owned. Mark's is 879; 878 are owned.
   Never divide these existing card values by titles owned to create a progress percentage.
   Recommendation: remove this card from the collection summary. Keep the diary intact.
   If Craig wants collection progress here, it must explicitly use watched-owned titles
   and say whose; that is a separate pick, not an automatic semantic change to the API.

4. **The labels promise more certainty than the data provides.** “Films owned” includes
   TV-series rows; use “Titles owned”, with “Films and TV series” beneath it. “Identified”
   means a TMDB film or TV ID exists, not that a person verified the match. Today 1,902
   of 1,903 owned titles have one. This does not mean only one doubtful identification
   remains: the “In doubt” review queue is separate. Remove this aggregate from the summary;
   keep identification work in its existing queue and Needs attention.

5. **Value and chart explanations need to stay beside the thing they explain.** The
   section heading currently carries the older blanket asking-price warning. AA10b's
   rule uses observed sales where available, otherwise a used asking-price stand-in.
   Put “Estimated used value”, priced/physical-copy coverage and observed-sale coverage
   with the value. Retain the advertised-price/Best Offer caveat in the detailed explanation:
   an observed disappearance is not proof of the final amount paid. Charts need their own
   units: formats count overlapping copy tags; genres overlap too; decades count titles
   with a year. Do not turn either overlapping breakdown into an adding-to-100% doughnut.
   Place labels currently truncate at 96 px. Spend bars use hover titles without a visible
   touch detail; the detailed version should expose those values on tap as well.

## Three layouts to choose from

Open [the interactive mock-ups](aa3-collection-mockups-2026-10-27.html). The carousel has
Compact summary, Browse first and Open ledger. Numbers are the 27 Oct snapshot, not invented
examples. The shell is schematic; the authenticated hero above this section is outside scope.
The Archive button only demonstrates its intended destination. The expanded panel models
Formats; the other breakdown names mark retained content, not implemented chart screens.

| Layout | What stays visible | Cost / compromise |
|---|---|---|
| **Compact summary — recommended** | Titles and copies beside each other; full-width estimated value; Archive action | Charts take one tap; more Home space than Browse first |
| Browse first | Titles and copies in one line; large Archive action | Value and charts take one tap; least Home space |
| Open ledger | All count definitions on separate labelled lines; estimated value | Longest section; comparison is easiest |

All three remove the two horizontal stats rows, keep charts reachable in this section,
and leave other Home shelves alone. Existing data can support most of the presentation;
the physical-copy count needs correcting. None requires hosting changes, a migration,
a re-price or a provider request. Preliminary effort is roughly one engineering sitting
plus the normal full gate/CI/deployment, with substantial uncertainty until Craig picks.
This is an option-cost estimate, not a build plan or a delivery promise.

## Picks requested

1. **Layout:** Compact summary (recommended), Browse first, Open ledger, or retain the
   sideways layout. Compact keeps the summary visible and makes the Archive action clear.
   Choosing a non-sideways layout approves an exception to #249 **for this section only**.
   The current test explicitly requires every Home section to contain a sideways row;
   its expectation must only change with that owner decision, never to force green.
2. **Meaning:** approve the count/label/value-explanation corrections (recommended).
   This changes the displayed physical count to include the 134 mixed-format copies;
   it changes no collection records and no stored prices. A later API field addition
   would need to preserve existing clients and shared-schema validation.
3. **Personal and maintenance numbers:** remove watched and identified from the collection
   summary (recommended), or retain a clearly labelled watched-owned measure and an
   identification measure. Removal costs information on this screen; it keeps collection
   size distinct from personal viewing and catalogue maintenance. No diary records move.

No follow-up chart-to-filter navigation is assumed. The main Archive page restores local
filter state rather than reading arbitrary URL filter parameters; clickable charts would
therefore be extra behaviour to decide, not a free link. No new stats route is proposed.

## Evidence and limits

- **Baseline:** clean `main`, fetched and equal to `origin/main`; all seven jobs passed on
  [CI 40480668409](https://github.com/CraigR973/mcu-app/actions/runs/40480668409), including
  Chromium, Firefox, WebKit and jobs. API health and web version both served the exact
  baseline SHA; readiness was `db: ok` and all integrations configured.
- **Fresh production reads:** the stats router's own function ran against a connection with
  `default_transaction_read_only=on`. Additional SELECTs counted physical/download overlap,
  watched-owned titles and the stored value using valuation's own copy/eligibility helpers.
  Only profile IDs and display names were selected to identify callers; no credential columns.
  The valuation GET was deliberately not called: its service may mark a stale run abandoned.
  No eBay/TMDB/retailer requests, valuation start, live mutation or synthetic account session.
- **27 Oct snapshot:** 1,903 owned titles; 1,927 copies; 1,472 physical; 589 download; 134 in
  both. Formats: 383 4K UHD, 885 Blu-ray, 208 DVD, 589 download; the physical-format counts
  also overlap. Estimated stored value £15,939.38, 1,311 of 1,472 priced, 0 sales-backed.
  **This is an interim read, not AA10b's final after-total checkpoint.** That remains open.
  Only 16 copies have purchase prices, so recorded spending must not imply lifetime spend.
- **Source audit:** `CollectionShelf.tsx`, `Shelf.tsx`, `DashboardPage.tsx` and its existing
  tests; `stats.py`, the owned-copy predicates, valuation selection and pricing rules;
  `MoviesPage.tsx` and theme tokens. Relevant decisions #249–251 and AA10b's #289–290
  were read. Open owner actions stay open.
- **Visual verification:** the three illustrative mock-ups were opened in the in-app
  browser; carousel and disclosure interaction checked. Compact summary and Browse first
  inspected at 375 px, Open ledger at 320 px. A physical phone and an authenticated
  production Home session were not exercised. Product source is unchanged; the full local
  implementation gate has not run and no build acceptance is claimed.

## Resume point

Wait for Craig's three picks. Only then plan AA3's build and its acceptance checks.
Complete AA3's authorised cycle before starting AA9's separate review; stop again for
Craig's assistant-page picks. Do not start sitting 6.
