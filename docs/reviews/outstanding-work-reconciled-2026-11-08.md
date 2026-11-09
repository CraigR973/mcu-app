# Outstanding work reconciled against production — 8 Nov 2026

## Result

The current records have been reconciled locally at Craig's “proceed with next steps to see what is outstanding”. No implementation, provider request, live write, commit, push, merge or deployment is included.

The most pressing outstanding work is **Mark's watch-history setup and the saved diary backfill/correction plans**. Price-history charts now pass the numerical data gate, but the documented Dead Man's Shoes identity discrepancy remains. The catalogue's old hundreds-of-identifications checklist is obsolete: the current owned catalogue has **1 unmatched title and 1 visible doubt**. Disc specs have **419 owner-review items**.

## Evidence and preservation

Read-only production observations were collected **11:52–11:57 GMT on 8 Nov** through the existing `src.scripts.live_sql` tooling and `mcu_readonly` role. No secret was printed. Local, tracking and remote main remain `417471a167c4b1469a300cfe8124e5f7c1dbe39c`; the production API/web serve that SHA with full readiness. The latest code CI is still **42402887825**, successful; the newer **42472268641** is a successful Backup workflow, not a replacement code gate.

All three earlier reports in this chat are preserved unchanged. Their time-qualified snapshots remain history. This report and the local status/owner/ledger corrections are the new work. No batch was started and no acceptance criterion or owner checkpoint was relaxed.

## 1. Watch history — genuinely outstanding

| Person | Current production evidence |
|---|---|
| Craig | Username stored; 622 non-deleted watch rows. Cron sync completed 8 Nov 08:02:44–08:02:46: 50 entries read, 50 already imported, 0 written, no error. Weekly cron records also exist on 18 Oct, 25 Oct and 1 Nov. |
| Mark | Username **null**; **no sync record**; 972 non-deleted watch rows, none created since 14 Oct. His automated sync is inactive because it selects people with a stored username. |

The old instruction that a weekly cron is impossible is superseded by deployed code and Craig's actual successful runs. The old instruction that both usernames are already stored is also wrong for Mark.

### Compare saved plans with stored viewing IDs

The existing 14 Oct plans were inspected without running their commands. The comparison uses each plan's person and Letterboxd viewing ID, including soft-deleted watch rows, matching the backfill's idempotency check. It does not call Letterboxd or TMDB and is **not** a new live-write dry run.

| Saved non-doubtful plan entries | Already present by viewing ID | Absent by viewing ID |
|---|---:|---:|
| Craig: 493 | 13 | 480 |
| Mark: 158 | 0 | 158 |
| Total: 651 | 13 | **638** |

These are absent **plan viewing IDs**, not proof that every underlying viewing is absent under all manual or legacy representations. Current movie matches, duplicates, deletions, and target eligibility must be checked before a write. Do not run the old 651-row plan unchanged or treat 638 as an approved write count.

The plans also retain **105 originally doubtful entries** (Craig 86, Mark 19); 3 of Craig's IDs now appear in history. Their presence does not prove a correct identity decision. Any renewed review/import must deduplicate them against current history.

All **7 saved proposed watch re-pointings** still have existing watch rows on their saved old movies; **0** are on their proposed targets. The other **8** saved re-pointings were doubtful and remain a judgement list, not write authority.

**Next scope:** prepare a current, reviewable watch-history recovery proposal: the exact one-row Mark username change, a fresh safe reconciliation of the saved plans, explicit duplicate/target counts, and a bounded source-read plan only if genuinely required. Craig's decision precedes any username write, backfill, re-pointing or provider request. The RSS feed holds only 50 entries, so this deserves priority over optional new UI. Current feed contents were deliberately not fetched; no missing time span is guessed.

## 2. Price-history charts — numerical gate passed, identity gate unresolved

There are **46 completed real cron days**, from **24 Sep to 8 Nov**, **0 top-level run errors**, and **215 written checks** summed across those runs. Individual shop failures are distinct from top-level run errors; no claim is made that every shop answered.

Stored price-check timestamps were matched to actual completed non-dry-run cron intervals. Three active wanted IDs now have two shops with at least two real scheduled days:

| Want | Scheduled history per shop | Current issue |
|---|---|---|
| Castle Freak (1996) | 101 Films 28 days; Zavvi 19 | Latest points 8 Nov / 12 Oct |
| Dog Soldiers (2002) | Second Sight 20 days; Zavvi 12 | Latest points 8 Nov / 12 Oct |
| Dead Man's Shoes (**1940**) | Second Sight 24 days; Zavvi 19 | Documented wrong-film association remains; latest points 8 Nov / 12 Oct |

Thus the old “only two wants have enough shop history” blocker is stale. **Three wanted IDs pass the numerical gate**, but the Dead Man's Shoes row still points to the **1940 film, TMDB 416920**, while the review already documented that the shop prices concern the 2004 film. Current stored price titles still read “Dead Man's Shoes Limited Edition Blu-ray”. No new retailer/TMDB read or identity correction was performed.

Do not count that row as a trustworthy third film until its identity and retained history association are reviewed. Existing chart data also needs to disclose that Zavvi's most recent retained points are 12 Oct; these are historical series, not fresh quotes.

**Next scope:** resolve the stored wanted-film discrepancy through the owner identification path, without silently moving collection copies/watches or rewriting history. Then propose Batch 21's chart build and its chart-library/SVG choice, acceptance and model/effort. No chart implementation is started by this reconciliation.

## 3. Catalogue review — current counts, not historical workload

The queries follow the source rules for still-to-identify and visible doubts: owned copies are non-deleted and `in_collection`/`listed_for_sale`; deleted films and not-a-film decisions are excluded; doubts only show while their named copy or film remains owned.

| Queue | Current result |
|---|---|
| Owned title still to identify | **1: Shetland - Series 5**. It remains unmatched while an owned Shetland row already holds TV ID 46923; duplicate/series handling is an owner decision. |
| Visible open doubt | **1 doubt on 1 film: Titanic (1953), TMDB 16535**. Stored evidence says its selected Blu-ray.com page is a 1997 film. Inspect the actual disc/evidence before choosing the identity. |
| Scoped 4K/Blu-ray copies | 1,267 |
| Copies with stored specs | 848 |
| Spec queue `needs_you`, no specs | **419** |
| Accepted awaiting fetch / no match / skipped / not searched | 0 / 0 / 0 / 0 |

The earlier 166-unmatched / 384-doubts / 385-specs numbers must not be presented as current work. Edition-confirmation judgements may overlap the spec workflow; they were not turned into a speculative extra count.

### Three supposedly outstanding TV-copy moves are already done

Audit records prove the moves on **17 Oct**: Tinker Tailor Soldier Spy 2011 → TV 1979 at 10:16:02, Life 2017 → TV 2009 at 10:16:49, The Name of the Rose 1986 → TV 2019 at 10:17:38. None has an undo record, and **all 3 exact original copies remain owned on their recorded target series**.

Remove those three moves from the current owner workload. Do not move a remaining legitimate film copy merely because the film and series share a title. Historical TV-suspect reports still require copy-level evidence; the existing Shetland issue is separate.

## 4. Cinema and collection work

The **11:30 scheduled report** proves 8 future Rocky reruns across four ODEONs and an empty natural digest evaluation. At **11:55:45**, appearances/outbox/claims remain **0 / 0 / 0**. The morning run's metadata report still records 29 pending lookups; the morning future-identity snapshot has review aliases for Ramayana, Tabby McTat and The Devils. Those counts are tied to that run/read, not to new provider activity.

**Outstanding:** a genuine qualifying AC6 appearance, scheduled outbox/claim and transport outcome; then Craig's phone receipt/tap. AC3's owed positive production classification read-back has now been obtained. No test send or identity repair follows.

**Completed:** AA10b's 1 Nov campaign and the 8 Nov scope-qualified Home read-back. The earlier Home snapshot is £14,739.54, 1,309 priced / 162 checked-unpriced / 2 unchecked / 61 sales-backed copies over 1,473 physical copies. The two due pairs were later additions. These figures were not re-queried here. The before £16,867.11 covered 1,469 copies, so its difference is not a pure re-pricing effect. No extra Home press is needed.

**Future gate:** AA10c remains from **25 Nov**, with sufficient recorded-sales evidence and its existing owner decisions required. No comparison, stand-in switch or re-price starts here.

## 5. Work needing people or explicitly left parked

- **Phone/normal-use acceptance:** natural cinema digest receipt/tap; first wanted cinema trip and both-phone invitation/trip experience; genuine Mark-addition push; real loan receipt/handovers; actual barcode camera and dictation/offline checks; Mark's launch; live match update on an already-open iPhone page. Craig's accepted launch/header/Search checks are complete and must not be repeated without changed code/deployment or a new report.
- **Live/account observations still only recorded as open:** real assistant follow-up, eBay Connect for each person, sale-page preview/save, and a sensible value lookup. Their old checkboxes are not fresh proof of failure or proof that nobody has used them; ask for an observation before rebuilding anything. No live calls or account access were used to settle these.
- **Operational owner records:** backup-key copy into a password manager, Neon credential hygiene, formal revocation of the already-invalid April token, optional Railway restart-policy drift. Current password-manager/revocation/hosting-plan state was not verified; no secret or setting was changed.
- **Parked features:** sale pagination (22c, #247), email OAuth/scanning (33–34), AVForums expansion and paid/source-access proposals. Reopening needs its own explicit scope/decision; they do not block the cinema verification.

The monthly delta-review cadence suggests a review around **12 Nov**, following the 12 Oct review. That is a planning inference, not a scheduled appointment or authority to start a multi-pass review. A whole review plan and go are still required.

## Local record corrections

`STATUS.md`, `OWNER-ACTIONS.md` and `docs/phase-batches.md` now distinguish completed implementation, completed read-backs, genuine live-data checkpoints, normal-use observations, and parked work. The principal corrections are the completed cinema rerun read-back, still-empty digest, completed re-pricing read-back, Mark's inactive sync, current catalogue/spec counts, completed TV moves, and the chart gate's changed blocker.

Older dated logs and all three earlier reports remain intact. Shipped V9, Group X later sittings, Batch 38 and Z1 are no longer labelled future implementation in the touched current summaries. No batch was newly closed out, no new design decision was made, and no gate/model choice was changed.

## Recommended next task

**A bounded watch-history recovery preparation, not an implementation batch.** Use current stored evidence and saved plans to present exact proposed writes, duplicates/targets, necessary source reads, alternatives and risks. Keep Mark's one-row username setup distinct from hundreds of historical entries and the seven corrections. Estimate **20–30 minutes** for proposal/revalidation, excluding any newly approved provider reads or live apply. Craig approves the concrete write/read scope before those actions.

In parallel with normal use, the small catalogue choices are Shetland Series 5, Titanic's disc evidence and Dead Man's Shoes' wanted identity; these are owner judgements, not automatic merges. Spec review is a separate 419-item owner queue. Positive AC6 evidence can be read after a later natural run; no new automation is created here. AA10c remains at its separate 25 Nov gate.
