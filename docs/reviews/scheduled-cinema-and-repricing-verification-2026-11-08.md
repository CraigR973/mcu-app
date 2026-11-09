# Scheduled cinema and collection re-pricing verification — 8 Nov 2026

## Result and boundary

The main read-only database snapshot was taken at **00:44–00:49 GMT on 8 Nov**, before the expected **08:00 UTC / GMT** cinema run. The scheduled re-pricing campaign finished on **1 Nov**. Cinema acceptance remains open: no post-deployment scheduled refresh or digest evaluation has occurred yet.

This session only reads production. No implementation batch, provider request, refresh, valuation, notification, trip, calendar subscription or token rotation was triggered. No hosting, credential, schema or live-data change was made. This report is the only checkout addition; status/ledger corrections below are proposals, not applied edits. No commit, push, merge or deployment is authorised or performed.

## Current checkout, CI and production

| Check | Observed result |
|---|---|
| Checkout | Existing checkout on `main`; initially clean; no worktree, stash or discard |
| Local HEAD / local `origin/main` | `417471a167c4b1469a300cfe8124e5f7c1dbe39c` |
| Remote main, queried directly with `git ls-remote` | Same full SHA; no fetch/pull required |
| Latest CI, including latest main CI | [42402887825](https://github.com/CraigR973/mcu-app/actions/runs/42402887825), exact SHA above, completed successfully |
| CI jobs | All seven succeed: API static checks; API/Postgres tests; migration reversal; production image boot; web checks; dependency audits; Chromium/Firefox/WebKit/jobs E2E |
| CI completion | Last job completed 7 Nov, 19:08:51 UTC; E2E ran successfully, rather than being skipped on a feature push |
| API health | `status: ok`, `commitSha: 417471a167c4b1469a300cfe8124e5f7c1dbe39c` |
| Web version | `commit: 417471a167c4b1469a300cfe8124e5f7c1dbe39c` |
| Full readiness | `status: ready`; `db: ok`; `push`, `ai`, `ebay`, `tmdb`, `brave`: all `configured` |
| Database | Established `src.scripts.live_sql` tooling, existing secret loaded without printing it; `current_user: mcu_readonly`; migration `073` |

Read-only endpoints: [API health](https://api-production-a8fe.up.railway.app/api/v1/health), [full readiness](https://api-production-a8fe.up.railway.app/api/v1/health/ready), [web version](https://mcu-app-fawn.vercel.app/version.json).

The 7 Nov handoff names the repair code SHA `7c536d9`; current production serves the later documentation SHA `417471a`. The handoff CI uncertainty is resolved: its exact-SHA seven-job run is green. This does not supply scheduled-digest or real-phone evidence.

No local test suite was rerun: there is no application change. Current exact-SHA CI and read-only production evidence were inspected. Hosting configuration was not changed or independently reconciled; the expected schedules below come from the established repository configuration and observed run timestamps.

## 1. Daily cinema digest — AC6

### First post-deployment scheduled run

**Not yet due at this session's observation time.** AC6 deployed on 7 Nov after that morning's cinema refresh. The next expected pass is 8 Nov at 08:00 UTC, through `cron-reminders`. The command runs cinema refresh/evaluation after its other reminder work, so the cinema timestamp need not be exactly 08:00.

At **00:48:58 UTC**, production contains:

| Durable evidence | Count |
|---|---:|
| Cron cinema refreshes since the 7 Nov 16:46 deployment read-back | 0 |
| Cinema refreshes dated 8 Nov | 0 |
| Evaluated digest days | 0 |
| Qualifying appearances | 0 |
| Cinema outbox rows, all statuses | 0 |
| Committed daily delivery claims, all outcomes | 0 |
| Silent baseline listing aliases / identities | 278 / 23 |

Therefore there is **no evaluated day, positive qualifying result, held payload or delivery attempt to read back**. This is an unrun schedule, not an empty successful evaluation and not evidence of delivery failure. An eventual empty evaluation would prove only no-new-film silence, not positive transport or phone receipt.

### Latest available refresh — before AC6 deployment

Run `a07f612e-0dd3-417e-a491-25a23a2640af`, trigger `cron`, started **7 Nov 08:03:27**, finished **08:05:13 UTC**, status **partial**. It cannot stand in for the required post-deployment AC6 run.

Its retained report records all **9 venues** with `failed: false`, **1,608 collected showing rows**, and **99 requests**. Metadata enrichment is separately partial: **48 requests, 48 successful requests, 18 lookups, 31 cached records, 55 pending, no metadata errors**. Source date coverage is partial; only Vue reports any complete dates, 7–8 Nov. A terminal `partial` refresh does not mean nine failed venues or an empty programme, and it does not establish complete programme coverage.

### Outcome distinctions for the next read-back

| State | What must support it |
|---|---|
| Failed refresh | Recorded failed/abandoned outcome or failed venue provenance; absence of an outbox alone is insufficient |
| Partial refresh | Actual terminal refresh status, venue outcomes and coverage; evaluate only eligible successful observations |
| Empty digest | A persisted evaluated day/report with no qualifying appearances, distinct from no evaluation |
| Held delivery | Existing queued cinema outbox rows with their quiet-hours/digest target and reason; no send claim yet |
| Attempted delivery | Committed delivery claim, its outcome/counts, and corresponding outbox status; `claimed` or `unknown` does not prove a completed send |

At this snapshot, both Craig and Mark have Cinemas **on**, Older films only **off**, digest mode **off**, and no configured quiet-hours interval. These preferences do not prove that a usable device subscription or phone receipt exists; credential-bearing push subscriptions were not read.

**Acceptance:** AC6 stays unstruck. Read the first natural post-deployment run and its frozen day, appearance IDs, cinema outbox rows, claims, payload/target and transport outcomes. If it is empty, keep positive delivery acceptance open until a genuine qualifying run. Push-service acceptance still does not prove real-phone receipt or the tap into **Movie night → At the cinema → New this week**; those remain Craig's observations.

## 2. Cinema reruns — AC3

**The expected 8 Nov run has not happened at this snapshot.** No post-8-Nov claim can be made. No identity was inferred, linked, repaired or reclassified during verification.

### Current future programme

Scope: non-deleted cinema films, showings and venues, with showing start after the database observation time. The counts cover all retained future dates, not an arbitrary one-week window. Source-film rows are source aliases, not unique verified film identities.

| Stored category / confirmation | Showings | Source-film rows |
|---|---:|---:|
| First run / confirmed | 979 | 75 |
| Rerun / confirmed or unconfirmed | 0 | 0 |
| Unclassified / confirmed | 343 | 77 |
| Unclassified / unconfirmed | 15 | 9 |

Total: **1,337 future showings**. The authenticated production filter UI was not exercised; these are stored classification counts. No future rerun result can be demonstrated from them.

There is **one retained historical `olderFilm` row**: **Pan's Labyrinth (20th Anniversary)**, Vue Glasgow St Enoch, **3 Nov 19:30**, verified TMDB **1417**, last observed 3 Nov 17:09:56. Its reason is the existing source anniversary/reissue evidence (`run: returning`), not an AC3 UK-release `runReason`. This proves a historical stored rerun category exists in production. It does **not** prove that AC3's pending films have been classified by the 8 Nov run or that the current future rerun filter has a result.

### Remaining identity work

| Stored identity status | Source-film rows | Future showings |
|---|---:|---:|
| Verified | 76 | 993 |
| Review | 9 | 9 |
| Unverified | 49 | 245 |
| Event | 18 | 90 |

The **9 review rows** are **Tabby McTat: 6 showings** and **The Devils: 3 showings**, all Cinematimes aliases. Review grouping is by identity evidence, so two source title strings do not necessarily mean exactly two admin review groups. They need evidence-based review; no candidate selection was attempted here.

The **49 unverified source rows** represent **46 distinct source title strings**. These remain unresolved; event-like wording is not enough to change their stored status. Existing `event` rows are separately excluded from film matching.

Examples from the originally expected reruns remain unverified and unclassified:

| Source title | Future showings | Next showing |
|---|---:|---|
| Rocky — Cinematimes | 8 | 8 Nov 17:00 |
| Throwback: Rocky (50th Anniversary) — Everyman | 2 | 8 Nov 18:40 |
| Hunger Games: The Ballad of Songbirds and Snakes — Cineworld | 2 | 11 Nov 13:00 |
| Prisoners — Cineworld | 1 | 13 Nov 19:15 |
| Cliffhanger — Cineworld | 1 | 14 Nov 19:45 |
| Elf — Everyman | 1 | 15 Nov 16:45 |

By contrast, **I Play Rocky**, TMDB **1286656**, has **82 future first-run showings** across Cineworld, Vue, Cinematimes and Everyman, with stored reason **UK release 6 Nov 2026 · first run**. It is not the unresolved **Rocky** identity.

Full unverified source-title inventory, grouped by source (names are retained source text, not proposed matches):

- **Cineworld:** A Talent for Murder Unlimited Screening; Being Heumann; Cliffhanger; Fjord Unlimited Screening; GIANT - The Play; Hunger Games: Sunrise on the Reaping; Hunger Games: The Ballad of Songbirds and Snakes; Instruktorius; Marie Antoinette (20th Anniversary); Momo and the Time Thieves; Monster Mia; Prima Facie; Prisoners; Ramayana: Rise of A Legend; Ramayana: Rise of a Legend (English Dubbed); Sicario; You Can See Everything.
- **Cinematimes:** Animol; Heart of the Beast; I Love Boosters; Kiri and Lou Go Raaa!; Merry Christmas Aubrey Flint; One in a Million; Onwards and Sideways; Other Mommy; Raise the Red Lantern; Ramayana; Resident Evil; Rocky; Spider-Man: Brand New Day; The Incomer; Your Mother Your Mother Your Mother.
- **Everyman:** Elf; Fatherland; GIANT - The Play; Members' Preview: A Talent for Murder; Sense and Sensibility; The Hunger Games: Sunrise on the Reaping; Throwback: Almost Famous (25th Anniversary); Throwback: Rocky (50th Anniversary); Toddler Club: Arthur Christmas (15th Anniversary); Toddler Club: Festive Fun with Peppa; You Can See Everything.
- **GFT:** A Woman Under the Influence + discussion; Cocoon + Q&A; Samurai Ballerina; We Are Aliens.
- **Science Centre:** The Hunger Games: Sunrise on the Reaping - IMAX 2D (12A).

**Acceptance:** preserve Craig's earlier AC3 close-out under decision #340, but leave its explicitly owed scheduled rerun read-back unresolved. The previous dry run's 18 rerun showings are not substituted for new production evidence.

## 3. Collection re-pricing — AA10b

### Completion is recorded, not inferred from elapsed time

| Run | Stored result |
|---|---|
| Owner start, 23 Oct 14:19:40–14:30:48 | `d222ed2f-040f-46fc-b0c8-2c9f920aa5e4`; `admin`, `budget_spent`; 748 calls, 675 priced pairs, 73 not priced, **0 failed, 719 remaining** |
| Scheduled continuation, 1 Nov 04:04:18–04:13:58 | `7583a503-f344-4ce0-aa13-48a65512e8d8`; `job`, **finished**; budget 750, **724 calls**, 635 priced pairs, 89 not priced, **0 failed, 0 remaining**, no error |

Both runs retain `priceRule: used_quartile`. The scheduled campaign completed for its then-current eligible film-format scope. No later valuation run row exists in this period. A command that finds nothing due need not create a run row; absence of a 2 Nov row is not evidence of failure.

### Current Home calculation — 8 Nov

This was calculated with SELECT queries matching Home's source predicates and effective-value rule. The Home valuation service/endpoint was **not invoked**, because its nominal read can mark stale running runs abandoned.

| Measure | Current result |
|---|---:|
| Owned physical copies | 1,473 |
| Distinct owned film-format pairs | 1,471 |
| Priced copies | 1,309 |
| Checked but unpriced copies | 162 |
| Unchecked copies | 2 |
| Total copies without a usable value | 164 |
| Sales-backed copies, included in priced copies | 61 |
| Current Home collection value | **£14,739.54** |
| Currently due film-format pairs | 2 |
| Failed pairs in the completion run | 0 |

The two due pairs are **Contagion — 4K UHD**, added 4 Nov, and **Titanic — Blu-ray**, added 5 Nov. Both have no valuation row. They were added after the 1 Nov completion; they are not failures left over from that run. The next configured valuation slot is **15 Nov, 04:00 UTC**, followed by 16 Nov. No fresh search was requested.

The recorded before total was **£16,867.11**, covering **1,469 physical copies**, **1,290 priced**, **0 sales-backed**. Current Home is **£2,127.57 lower (12.61%)**, but this is a comparison of Home totals over time, **not a controlled re-pricing-only difference**.

### Scope reconciliation

The definition is unchanged between the pre-AA10b source and current source:

1. Include non-deleted copies whose listing status is `in_collection` or `listed_for_sale`, with a non-deleted film.
2. Include physical formats only; downloads contribute no resale value.
3. Choose one best physical format per copy: 4K UHD, then Blu-ray, then DVD. Combo packs count once; separate copies count separately. The collection is shared, not restricted to one profile.
4. Require a current-rule valuation (`used_count` non-null). Three or more observed sold listings with a stored sales price take precedence; otherwise use the stored asking-value figure. Unpriced copies contribute no guessed value.

**Membership and formats have changed:** audit records show **5 current physical additions**, **1 original physical copy removed**, and original-copy format upgrades. Thus **1,469 + 5 − 1 = 1,473**. The five additions are The Hunt for Red October, The Sum of All Fears, Jack Ryan: Shadow Recruit, Contagion and Titanic. The first three contribute **£55.09**; the last two remain unchecked. The original Contagion Blu-ray copy was soft-deleted on 5 Nov. Shutter Island and original Patriot Games/Clear and Present Danger copies also changed from Blu-ray to 4K. Temporary Contagion format toggles were reversed before removal.

An audit-assisted reconstruction restores original formats from the first subsequent format change and includes the later soft-deleted original copy. It recovers **1,469 copies / 1,467 pairs**. There are no recorded ownership-status changes in the inspected interval. The original cohort, valued at current retained stored figures, has **1,307 priced, 162 unpriced, 0 unchecked, 61 sales-backed**, totalling **£14,653.03**, **£2,214.08 lower (13.13%)** than the recorded before total.

**Limit:** that reconstructed figure is not the historical Home total at completion and not a fully fresh comparison under one price rule. Its obsolete **Shutter Island Blu-ray** pair retains a **16 Oct £4.38 `used`** value; the actual copy had changed to 4K and its old pair was no longer eligible for the campaign. Later sales evidence also changes effective prices. No per-copy before-price snapshot or completion-time Home snapshot was supplied. Therefore:

- The scheduled campaign's recorded completion and current Home value are proved.
- The current and before totals use the same definition, but different actual copy/format scopes.
- The reconstructed original scope is explicitly qualified; neither monetary delta isolates the causal effect of AA10b alone.

**AA10c is not started.** Decision #290 and its ledger criterion still say **from 25 Nov**, with sufficient recorded-sales evidence required at that time. Today's 61 sales-backed copies do not establish that the comparison is ready. No sufficiency threshold, comparator result or valuation switch was invented.

## Proposed exact status and ledger corrections — not applied

Historical dated log entries and decisions should remain history. Apply current-state corrections in a separately authorised documentation action; no strike, close-out or commit occurs here.

### STATUS.md — Now

Replace the current present-tense verification paragraphs with this text, retaining the historical implementation evidence elsewhere:

> **8 Nov, 00:49 GMT: verification only.** Main, remote main and production API/web match `417471a167c4b1469a300cfe8124e5f7c1dbe39c`; latest exact-SHA CI 42402887825 passes all seven jobs including E2E, and every readiness field passes. The final 7 Nov documentation CI uncertainty is resolved.
>
> **Cinema acceptance remains open.** The 8 Nov 08:00 scheduled pass has not yet occurred. There are 0 post-deployment cron refreshes, evaluated digest days, appearances, cinema outbox rows and delivery claims. No-run is not an empty evaluated day. Future programme: 979 first-run showings, 0 reruns and 358 unclassified. AC3's owed post-8-Nov rerun read-back and AC6's natural positive digest/phone receipt/tap remain unverified. One historical source-labelled rerun predates this check and does not satisfy either gate.
>
> **AA10b's scheduled campaign finished 1 Nov at 04:13:58 UTC:** 724 calls, 635 priced pairs, 89 not priced, 0 failed, 0 remaining. Current Home is £14,739.54 across 1,473 copies: 1,309 priced, 162 checked-unpriced, 2 unchecked, 61 sales-backed. Two later-added pairs are due; the next configured slot is 15 Nov. The £16,867.11 before total covered 1,469 copies, so the £2,127.57 fall includes scope and sales-evidence changes. The report contains the qualified original-scope calculation. AA10c remains unstarted, from 25 Nov and evidence-gated.
>
> **Next:** bounded read-only cinema follow-up after the 8 Nov scheduled command finishes. No manual job, send, provider call or new implementation batch. Report: `docs/reviews/scheduled-cinema-and-repricing-verification-2026-11-08.md`.

Prepend a dated Log entry with those verification facts and the report link; do not rewrite the earlier dated totals as if they were mistaken.

### OWNER-ACTIONS.md — AA10b item

Replace the stale forecast beginning “The scheduled valuation job next runs 1 Nov…” and the obsolete “Sitting 2 remains closed…” sentence with:

> **Read back 8 Nov:** the scheduled continuation finished 1 Nov at 04:13:58 UTC with 0 failed and 0 remaining pairs. No second press is needed. Current Home is £14,739.54: 1,309 of 1,473 physical copies priced, 162 checked-unpriced, 2 unchecked, 61 sales-backed. The 2 due pairs were added after completion. The before £16,867.11 covered 1,469 copies; additions, removal, format changes and later sales evidence mean the difference is not solely re-pricing. See the 8 Nov verification report for the qualified original-scope readback. No further owner press or implementation is requested by this verification. AA10c remains from 25 Nov and requires a fresh evidence check.

The AC6 owner item remains open. Its waiting instruction should say the 8 Nov run was **not yet due at the 00:49 check**, rather than implying a run has already succeeded. AC5's first real trip and phone checks remain separate.

### docs/phase-batches.md — AA10b row and Group AA summary

Replace the present-tense “719 due / after-total pending after 1–2 Nov” wording in both the AA10b row and Group AA summary with:

> **Scheduled campaign complete, read back 8 Nov:** 1 Nov job finished with 724 calls, 635 priced pairs, 89 not priced, 0 failed and 0 remaining. Current Home £14,739.54; 1,309 priced / 162 checked-unpriced / 2 unchecked / 61 sales-backed copies across 1,473 physical copies. The 2 current due pairs are post-completion additions. Before £16,867.11 covered 1,469 copies; comparison is scope-qualified in `docs/reviews/scheduled-cinema-and-repricing-verification-2026-11-08.md`. No AA10c or further sitting started.

Do not silently convert the reconstructed old-scope value into an unqualified “final repricing total”. Do not strike the batch during this session.

### docs/phase-batches.md — AC3 and AC6 rows

Append to AC3's existing read-back commitment:

> **8 Nov 00:49 verification:** the expected 08:00 run has not occurred. Future showings contain 0 reruns; 49 source-film rows remain unverified and 9 remain in review. A retained 3 Nov source-labelled Pan's Labyrinth rerun is historical evidence only. The post-8-Nov scheduled read-back remains owed; Craig's #340 close-out is unchanged.

Append to AC6's deployed/open acceptance record:

> **8 Nov 00:49 verification:** current main/API/web `417471a`, exact-SHA CI 42402887825 all seven green, full readiness passes. No post-deployment scheduled refresh or evaluated digest day exists yet; appearances/outbox/claims remain 0. Keep unstruck pending genuine qualifying scheduled evidence and Craig's phone receipt/tap.

The AC6 implementation/calendar repair reports' 7 Nov snapshots and decisions #340/#349/#350 remain historical evidence; this dated follow-up supplies current state. No new design decision is proposed.

## What is now proved

- Current checkout/main/production SHA parity, exact-SHA seven-job CI and full readiness.
- The 1 Nov AA10b continuation finished with zero failures and zero remaining pairs; today's two due pairs are later additions.
- Current Home value and copy counts, unchanged scope definition, actual scope changes and qualified original-scope reconstruction.
- Actual cinema records at this observation time: no post-deployment run/evaluation/delivery, zero future reruns, explicit unresolved identity counts and examples.

## What remains unverified or blocked

- AC6's first natural scheduled evaluation, then a qualifying appearance/outbox/claim and actual transport outcome. It is too early for the expected run; there is no observed scheduler failure.
- AC3's promised read-back after the 8 Nov run, and positive future rerun filter evidence. The 55-pending metadata report is a 7 Nov run snapshot, not a measured 8 Nov backlog.
- Real-phone receipt and the tap into New this week; independently, AC5's first real trip/phone acceptance and other existing owner checkpoints.
- A pure before/after causal monetary effect for AA10b: historical scope changed and no completion-time Home snapshot was retained. The original-scope reconstruction includes one obsolete-format old-rule value.
- AA10c's later readiness/comparison, deliberately outside this session and not authorised before 25 Nov.

## Craig's observations or decisions

1. **AC6 phone observation, when a real qualifying digest arrives:** confirm receipt and that tapping opens New this week. No test push is requested; this costs only the observation when a natural message exists.
2. **Identity review, when taken as a separate task:** Tabby McTat and The Devils need review of stored candidate/evidence groups before any mapping decision. This report supplies no candidate recommendation and authorises no mapping write.

No hosting, credential, scheduling or valuation decision is needed to account for this snapshot. No further Home Update values press is recommended.

## Recommended next task and stop

**One bounded read-only cinema follow-up after 8 Nov's 08:00 scheduled command has finished.** Prerequisites: a naturally recorded terminal run, current SHA/CI/readiness check, and the same safe database access. If the run has not occurred or is unfinished, report that state rather than invoking it. Read refresh/venue/metadata outcomes; current rerun counts and named examples; persisted digest day and qualifying appearances; then cinema outbox/claims, held targets and completed/failed/uncertain outcomes. Leave positive acceptance open for an empty run; leave phone receipt/tap to Craig.

Estimated agent time: **15–25 minutes**, with no extra source/provider spend or production mutation. Separate authorisation is required for implementation, identity repairs or a documentation close-out. AA10c stays outside scope until 25 Nov and a fresh sufficient-sales check.

**Stop here.** This report does not schedule another session, run a batch, apply the proposed ledger corrections or start close-out.
