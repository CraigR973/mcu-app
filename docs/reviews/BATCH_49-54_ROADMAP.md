# Batches 49–54 remediation roadmap (wave 2)

Synthesised 16 Nov 2026 from six passes at `1668071`; production served that commit at check-in.
Reports: R1 code (`BATCH_49_CODE_REVIEW.md`), R2 data, security and ops (`BATCH_50_…`), R3 the
assistant (`BATCH_51_…`), R4 catalogue and cinema listings (`BATCH_52_…`), R5 prices and deals
(`BATCH_53_…`), R6 product and UX (`BATCH_54_…`; its two-person scorecard is never published). Scope:
`BATCH_49-54_REVIEW_SCOPE.md`. Corrections, re-verification and the full coverage table:
`BATCH_49-54_FOLLOWTHROUGH.md`. People are named by role: the admin and the viewer.

**Evidence:** observed (production rows), computed (derived from them by a script), proved (the real
function driven, or a test that fails when the fix is reverted), implemented (read in the code).
**Spend:** $0 of the $0.50 cap (the canary could not run). TMDB 4 of 100 calls; cinema pages 1 of 20;
eBay 0 of 50; Brave 0. The synthesis re-checked every Med-High and headline number with 20 read-only
queries and 2 `gh` reads; every one held, three with a corrected count.

## a. The verdict and the scorecard

1. Both people's everyday paths work, and wave 1's ten Highs all hold. No High this time: 3 Med-High,
   17 Medium, 12 Low (32 findings).
2. One story across six passes: the app tells the truth on the screen built for a problem, not on the
   screens people look at first (Home, pushes, the digest, the daily check).
3. Noticing is still the weak half. Four cinemas went dark for five days and one shop for five weeks
   with no word. The cinema half is fixed (PR 161); the 08:00 job, the backup and the calendar are not.
4. "A fact found for the film it was" leaks through doors the fixes missed: a moved copy, a want's
   shop prices, a merge, a phantom import copy, and about 1 deal push in 18.
5. Cheap to run ($0.0992 of model spend, ever). The fixes are about 9 days of batches; the assistant's
   upkeep is the one cost to cut.

| Question | Grade | In one line |
|---|---|---|
| 1 Correct and safe | B+ (C) | One latent crash path; three wrong-film facts live |
| 2 Honest with its user | B− (C−) | True where built; silent on Home, pushes, digest |
| 3 Doing its job | B (C−) | Cinema, Movie night, Needs you work; pushes weak |
| 4 Failures noticed | C (F) | 4 of 8 jobs watched; P1 and a shop unseen |
| 5 Cheap to run and change | B (B) | Nil cost; per-site rules; assistant upkeep |

Wave 1's grade in brackets.

| Pass | Grade | In one line |
|---|---|---|
| R1 Code | B+ | Tests bite; fixes land per site, two classes back |
| R2 Data, security, ops | C | Sound data and auth; half the jobs unwatched |
| R3 Assistant | B | Well built; unused since 18 Oct |
| R4 Catalogue, cinemas | B | Right almost everywhere; three wrong-film facts |
| R5 Prices and deals | B− (D) | Value honest; deals thin and clock-driven |
| R6 Product and UX | B (C+) | Snags landed; the person affected rarely told |

## b. Happening now, and before the first delta review (about 16 Dec)

- **PR 161 (#381), the fast lane, merged 16 Nov.** The four ODEONs are read again from 17 Nov
  08:00 UTC, and the daily check names a cinema that fails or finds nothing. Read-back on 17 Nov: ODEON
  rows from 18 Nov exist; the 307 stored rows from 11 Nov are seen again or withdrawn.
- **#381 left two questions for this roadmap.** What `partial` should mean: judge each venue against
  what its source can read, so `partial` means a venue read less than it can (AG2). Whether a showing a
  source stops returning stays `confirmed`: yes, as the last observation; every reader then uses the
  one stale test the cinema screens already use (AG3).
- **AA10c, 25 Nov** (stand-ins settled from sales): add MK53-04's deal check to its read-back.
- **5 Feb 2027:** the 1,064 films last synced in September start crossing 150 days (DS50-05, AG2).
- **Railway is unreachable** (the saved token is rejected): nothing Railway-side is verified until
  owner decision 8.
- No protected window.

## c. How the app works now

```
 TMDB · eBay · shops · cinemas · Brave
 Letterboxd           (all reads)
          │
          ▼
 Railway: API + scheduled jobs
  02:00 specs · 03:00 shops
  04:00 values (set days)
  eBay every 2 h
  08:00 check → Letterboxd →
        pushes → cinemas → digest
 GitHub Actions: Sunday backup
          │
          ▼
 Neon Postgres (192 MB of 1 GB)
          │
 Vercel web app ── two phones
 Home · Needs you · pushes
```

Eight scheduled things feed one database; the daily check at 08:01 reads their traces and writes App
rows to the admin's Needs you, with a push for a new failure. At `1668071` it watched four (shops,
specs, eBay, values); PR 161 added the cinemas. Still unwatched: the 08:00 job itself (reminders,
Letterboxd, the digest), the backup and the calendar's TMDB refresh. Facts about a film are kept honest
three ways (an identity stamp, a time rule, an audit of corrections), and each new door (a move, a
merge, a want) must remember to join one.

| The records say | The code or production says | Finding |
|---|---|---|
| The repo is private (owner item 9, review brief) | Public since 10 Nov; kept so (#382) | DS50-03 |
| The daily check names a job that stops (guard 9) | 4 of 8 jobs; 5 since PR 161 | DS50-01 |
| One title-key table (guard 6) | A fixed list of 7 sites; the cinema code has its own | CR49-03 |
| "A merge is not a correction" (#378, #380) | Nor is a move; a merge drops cinema links | CT52-02, CR49-05 |
| The restore runbook assumes a second key copy | One copy, on the Mac | DS50-04 |
| The canary is the monthly guard (guard 19) | Never run; needs Railway | AI51-04 |
| Owner item 14 Nov: correct a want's film | Settled by the app's own question, 15 Nov | CT52-04 |

## d. Work packages

**Dispositions:** do now · fold into a queued item · decision-gated · defer with a trigger · accept
and close. **Models:** "top" is the ledger's top tier, "mid" its mid tier. AG0–AG10 are draft names
(Group AG); the rows step confirms them.

| Package | Findings | When |
|---|---|---|
| AG0 Owner actions | decisions 1–3, 7–9 | now, no code |
| AG1 The 08:00 job survives a failure | CR49-01 | do now, first |
| AG2 Every scheduled thing watched | DS50-01, CR49-04, DS50-05, MK53-02 | do now, first sitting |
| AG3 Say it where people look | CT52-01, UX54-01, -02, -03 | do now, second sitting |
| AG4 Found for the film it is | CR49-02, -05, CT52-02, -03 | do now, third sitting |
| AG5 Wants know their film | CT52-04, MK53-03 | do now, with AG4; decision 1 |
| AG6 Deals: right disc, fair figure | MK53-01, -02, -04, -05, -06 | after 25 Nov; decision 4 |
| AG7 One title fold | CR49-03, CT52-05 | do now, any sitting |
| AG8 The assistant, if kept | AI51-01, -03, -04 | decision-gated (5) |
| AG9 Security and records | DS50-02, -03, -04 | do now; decisions 6, 9 |
| AG10 Polish | UX54-04, -05 | any sitting |
| Deferred | AI51-05 | trigger: a deprecation notice |

### AG1 — The 08:00 job survives one person's failure
CR49-01 Med-High.
- **Evidence:** proved in a throwaway clone. The Letterboxd sync's error handler rolls back, then reads
  `person.id`; async SQLAlchemy raises, the original error is lost, the second person is skipped, and
  the job's later steps (delivery, the reminders heartbeat, the cinema refresh, the digest) never run.
  The run row is rolled back too, so the person stays due and the crash repeats every morning. 0 live
  occurrences.
- **What people see:** mornings go quiet. The daily check ran before the crash, so its own rows look
  fresh; the first word is PR 161's "cinema programme not run" a day later.
- **Fix:** take the person's id before the `try`; record the failure on a committed run row; guard the
  sync in `_run` as the cinema phase is. Test: a failure for the first of two existing people, the
  second syncs and the job carries on. Guard: no ORM attribute read after `rollback()` in an `except`.
- **Cost:** ~0.5 day · first · top · high.

### AG2 — Every scheduled thing watched
DS50-01 Med-High · CR49-04, DS50-05 (Low) · MK53-02's noticing half.
- **Evidence:** observed. 4 venues failed with 0 rows on each run 12–16 Nov; rows fell 2,247 → 888;
  all 16 daily-check rows read OK on 16 Nov. 14 of 14 cinema runs since 3 Nov `partial`, nine with no
  failed venue. One shop has given no price since 12 Oct and reads "no results" nightly. 1,064 films
  last synced 60+ days ago, oldest 8 Sep; 24 identified films never synced.
- **Fix:** one rule, not a list: every scheduled thing writes a heartbeat with a cadence and a failure
  figure, and a CI test lists the cron modules and fails on one the check does not read. Add the 08:00
  job (26 h), the backup (its last run, 8 days), the TMDB refresh (moved into the 08:00 job; a row when
  a film passes 165 days; never-synced films synced once), a venue switched off on refusal. Give
  `partial` a meaning (a venue read less than its source can). A shop whose search lands off its search
  path, or returns nothing for every want N nights running, counts as refused, so the weekly ask names it.
- **Cost:** ~1 day · first sitting · top · high. Before 5 Feb 2027 at the latest.

### AG3 — Say it where people look
CT52-01, UX54-01, UX54-03 Medium · UX54-02 Low.
- **Evidence:** observed through the read-only rig. At the cinema says four cinemas are stale only after
  the last film (about line 490 of 506); their times look like any other. Home's strip and the digest
  push say nothing. A phone that stops is shown on its notification settings page and to the admin,
  not on its owner's Home. The admin's Home opens on two rows labelled with the viewer's name whose
  next move is the admin's.
- **Fix:** one "N cinemas not read since <date>" line, from the existing stale test, at the top of At
  the cinema and under Home's strip heading; a "stale" word on a stale time; "N cinemas not read today"
  in the digest. The person's own device state on their Home. Needs you rows labelled by whose move it
  is, the admin's own first; the review-assigning control moves to the admin's tools.
- **Cost:** ~1 day · second sitting · mid · high.

### AG4 — Found for the film it is
CR49-02, CT52-02, CT52-03 Medium · CR49-05 Low.
- **Evidence:** observed. One copy moved to the 1971 film still carries the 1975 sequel's disc page and
  specs (a move is in neither #378's nor #380's re-lookup). Sheet row 878 ("King Kong [1976]") is a
  second 2005 4K copy beside row 877 with the same page; *Hitchcock* rows 703–704 share film, format
  and page. Implemented: the eBay sold store is in no mechanism; an undo defeats the time rule; a merge
  hard-deletes a film and drops its cinema link (`SET NULL`). 0 sold listings predate a correction today.
- **Fix:** one mechanism: stamp each derived row with the TMDB id it was found for, or one
  `identity_changed` hook that identify, undo, merge and move call. A move forgets its copy's page.
  Tests: every table with a film id registered; every foreign key to `movies` moved or listed as
  dropped. A Needs you row when two live physical copies share film, format and page.
- **Cost:** ~2.5 days · third sitting · top · high. Before onboarding a third person.

### AG5 — Wants know their film
CT52-04 (recast), MK53-03 Medium.
- **Evidence:** observed. Shop prices are matched to a want by title: the shop extractor drops a year
  as noise. The 2009 *Bad Lieutenant* want holds 27 prices of the 1992 film's 4K since 12 Oct and
  pushed on 22 Oct; the *Dead Man's Shoes* want holds 53 prices of another film's disc (26 since
  12 Oct). The latter want's film was confirmed through the app's own question on 15 Nov: the want
  stays; its prices are the defect. The want question is built for one film (a database check allows
  two answers; wording fixed in `services/assigned_reviews.py`).
- **Fix:** compare a shop title's year with the want's film (±1, as the eBay rule does); record a
  mismatch as "another film", not a price; run once over stored prices and hide the mismatched ones.
  Generalise the want card so any want can ask "which film?" (a migration widens that check, a
  data-shape change), and raise it when a want's shop years disagree. Batch 21's charts wait for this.
- **Cost:** ~1 day · with AG4 · top · high.

### AG6 — Deals: the right disc, a fair figure, sensible pushes
MK53-01, -02, -04, -05 Medium · MK53-06 Low.
- **Evidence:** observed. 7 of 124 deal pushes named another film or product (five same-title films
  given away only by cast names; "Mastered in 4K"; one disc of a set). 94 of 318 deals rest on exactly
  three asks; 105 on a scaled New price; a fifth to a third of checkable deals sat at or above recorded
  sales. Five pushes a day go to whatever the 00:20 and 02:20 passes find, both people, 121 of 124
  upgrades, about a quarter at night. 502 push rows keep listing words.
- **Fix:** "mastered in 4K" and "ONLY" rules; refuse a listing naming cast absent from the filed film
  but present in a same-title film's; the seven titles join the wrong-product tests. A percentage only
  on 5+ asks or 3+ sales. Rank across the day per decision 4; default quiet hours. Repair the dark
  shop's search address. Prune or rewrite expired push rows.
- **Cost:** ~1.5 days · after AA10c's read-back (25 Nov) and decision 4 · top · high.

### AG7 — One title fold
CR49-03 Medium · CT52-05 Low.
- **Evidence:** proved. The cinema rule and `title_key` disagree on 12 of 15 crafted pairs ("Part Two"
  and "Part 2", "Rocky II" and "2"); three live listings slip the cinema prefixes (a typographic
  apostrophe, "Curates:", a certificate bracket).
- **Fix:** build the cinema rule on `title_key.fold`; the pairs and the three titles join the table;
  no `unicodedata.normalize` outside `title_key.py`.
- **Cost:** ~0.5 day · any sitting · mid · high.

### AG8 — The assistant, only if kept (decision 5)
AI51-01 Medium · AI51-03, AI51-04 Low.
- **Evidence:** proved over a scripted wire. A refusal leaves a blank or cut-off answer stored as
  finished; the stored empty turn should make every later message in that chat fail; nothing counts it.
  Model argument types are unchecked, so a card can omit a stored rating or price.
- **Fix:** on a refusal, the existing "declined" sentence, no empty turn stored, a usage row the check
  counts; the give-up logged; `strict` tools; the card prints what will be stored; assert the prompt's
  load-bearing lines.
- **Cost:** ~0.75 day · top · high. Before any model switch (AI51-05).

### AG9 — Security and records
DS50-03 Med-High · DS50-04 Medium · DS50-02 Low.
- **Fix:** a wrong current PIN on PIN change counts toward the login lockout, with its rate limit. The
  monthly drill also encrypts and decrypts with a throwaway key pair. Correct the records that say
  private; remove wave 1's scorecard from the tree if decision 6 says so.
- **Cost:** ~0.5 day · any sitting · mid · high.

### AG10 — Polish
UX54-04, UX54-05 Low. Pad Settings' switches and Needs you's tabs and links to 44 px; split the two
large script chunks by route (charts, the assistant, the scanner). ~0.75 day · mid · high.

**Queued items, re-verified by the passes**

| Item | Verdict |
|---|---|
| AA10c, stand-ins from sales (25 Nov) | accurate; add MK53-04's check to its read-back |
| Batch 21, price charts | decayed: two of its three films carry another film's prices; after AG5 |
| Batch 22c, every page of a sale | accurate; parked on owner action 28 |
| #254, eBay licence (accepted) | stands; residue MK53-06 in AG6 |
| Batches 24, 29, 37; X12c tidying | accurate |
| Owner item 9, revoke the April PAT | decayed premise ("private"); the token is dead |
| Owner item 14 Nov, correct a want's film | contradicted: decision 3 |
| Onboarding more people | after AG4 |

## e. Coverage, follow-through, guards, open questions

**Coverage:** 32 of 32 findings placed (29 in packages, 2 in owner decisions alone, 1 deferred); the
table is in the companion, section 3. **Follow-through:** wave 1's 44 stand as the pack found them,
with 16 rows corrected by the passes (companion, section 4). The synthesis corrected four findings:
DS50-01 settled at Med-High; CT52-04's premise withdrawn and recast; UX54-02 Medium → Low; UX54-03's
contested half dropped (companion, section 1).

**Guards — the standing checks this wave adds**

| Check | Catches | Runs in |
|---|---|---|
| No ORM attribute read after `rollback()` in an `except` | CR49-01's class | CI |
| Every run loop survives an injected failure, Letterboxd's too | CR49-01 | CI |
| Every cron module is read by the daily check | DS50-01 | CI |
| Backup within 8 days; TMDB sync within 165; a venue switched off | DS50-01, -05 | daily check |
| `partial` only when a venue read less than its source can | CR49-04 | CI, daily check |
| A shop landing off its search path, or empty for every want | MK53-02 | shop job, weekly ask |
| Every film-id table registered; every FK to `movies` moved or dropped | CR49-02, -05, CT52-02 | CI |
| Two live copies sharing film, format and page | CT52-03 | daily check |
| A shop title's year must meet the want's film | MK53-03, CT52-04 | shop job, CI |
| The seven wrong-product titles never match | MK53-01 | CI |
| No `unicodedata.normalize` outside `title_key.py` | CR49-03, CT52-05 | CI |
| Every cinema card reader uses the one stale test | CT52-01, UX54-01 | CI (web) |
| The drill decrypts a copy with a throwaway key | DS50-04 | monthly drill |
| A wrong current PIN counts toward the lockout | DS50-02 | CI |
| A refusal in three shapes; the prompt's key lines (if kept) | AI51-01, -04 | CI |

Wave 1's twenty: 18 run; guard 9 covers 5 of 8 jobs since PR 161; guard 19 (the canary) has never run.

**For reconsideration**

| Decision | Amendment | Evidence |
|---|---|---|
| #129 deals on three listings | No percentage when the yardstick is thin | MK53-04; raised in wave 1 too |
| #378, #380 "a merge is not a correction" | A move is a correction for its copy; a merge carries every link | CT52-02, CR49-05 |
| #257 backups as Actions artifacts | Holds once the key has a second copy | DS50-04 |
| #261, #300, #331 the assistant | Freeze, then retire on a dated trigger | AI51-02, UX54-06 |
| #381's two open questions | Answered in section b | CR49-04, CT52-01 |

**Hypotheses.** Two sold-store runs abandoned on 11 Nov may be the process dying at a Railway limit
(needs logs). Three GETs write as a side effect; one failing would fail its screen (R6). A deploy
where the web goes live before the API could briefly fail a screen whose new field is required (R1).
The *Hitchcock* pair may be a second import duplicate. The scaled-New factor may not transfer to
rarer films (testable after AA10c).

**Not covered by wave 2**
- **Railway is unreachable:** the saved token (dated 1 Oct) is rejected, so no assistant canary, no
  job logs or exit codes, no variables (a Sentry DSN unknown), no restart-policy plan, and no eBay
  calls (the keys live only in Railway).
- **R6 swept Chromium in the light scheme only:** no dark scheme, Firefox or WebKit; the viewer's
  Home and several screens were caught loading; snags 1, 4 and 7 not driven; 8 Nov's 18 points not
  walked one by one.
- **No real phone:** no install, push tap, iOS Safari, Android or offline check.
- No shelf check; the import spreadsheets are not in the repo (16 sheet rows swept). Not re-read: the
  CSP, CMA209 in full, X5's 87 doubtful diary entries, the owner ask about three copies.
- The scope note, R1 and R2 use the two people's first names, as the agent instructions do; R3–R6
  and this roadmap use roles.

## f. Decisions for the owner

**Answered 16 Nov (#383):** 10 yes; 4 yes, once the viewer has been asked; 5 no, the assistant is
kept, so AG8 is written; 6 yes, in AG9. Decision 1 was settled earlier the same day (the viewer's
Needs you, via AG5); 2, 3, 7, 8 and 9 are the owner's jobs at the top of `OWNER-ACTIONS.md`.

1. **Which *Bad Lieutenant*: put it on the viewer's to-do list.** Recommend yes: AG5 generalises the
   want card (a migration widens a database check, so a data-shape change), then the admin assigns it
   on the viewer's Needs you. Until then, an "Ask the viewer" entry in `OWNER-ACTIONS.md` (in this
   PR). Cost: ~half a day inside AG5; one tap for the viewer.
2. **King Kong row 878 and the *Hitchcock* pair.** Recommend deleting row 878's copy in the app (a
   soft delete, restorable from Trash; 2 minutes), and checking the shelf for two *Hitchcock* (2012)
   Blu-rays (5 minutes; delete one if there is one). The admin's to do: it changes live data.
3. **The 14 Nov owner item "Correct Dead Man's Shoes' match".** Its premise is contradicted by the
   app's own question, answered 15 Nov. Recommend applying that answer from Needs you and striking
   the 14 Nov item; AG5 then stops the other film's prices. Cost: 2 minutes.
4. **Which pushes each person wants** (UX54-02, MK53-05). Recommend: Wanted finds and finds of 40% or
   more at once; upgrades as one daily summary at 18:00 UK time; quiet hours 22:00–07:00 by default;
   each person may choose Wanted-only. Ask each person; AG6 builds it in about half a day.
5. **The assistant: freeze, then retire** (AI51-02, UX54-06). Recommend freezing now (no new work, no
   canary unless it is used) and retiring if it gets fewer than five questions by 31 Jan 2027: one
   small batch, keeping the tables and usage log. Cost: nil now; AG8 only if you keep it.
6. **Wave 1's tracked scorecard** (`docs/reviews/BATCH_48_SCORECARD.md`, public since 10 Nov).
   Recommend removing it from the tree in AG9: an ordinary commit, so it stays in history. A history
   rewrite is destructive and yours alone; not recommended for one file already public.
7. **Secret scanning and push protection.** Recommend switching both on: free on a public repo, a
   security setting, so yours. One minute, from the repo folder:
   ```
   gh api -X PATCH repos/{owner}/{repo} -f "security_and_analysis[secret_scanning][status]=enabled"
   ```
   ```
   gh api -X PATCH repos/{owner}/{repo} -f "security_and_analysis[secret_scanning_push_protection][status]=enabled"
   ```
8. **A new Railway token.** Recommend yes: it unblocks the canary (about $0.08, inside the review's
   cap), job logs and the restart-policy plan. Five minutes in Railway; save it to the secrets file.
9. **Copy the backup key into your password manager** (open since 14 Oct). Two minutes; then AG9's
   drill change proves a copy opens.
10. **Go for the rows.** Recommend yes: write AG1–AG10 to the ledger from this roadmap (AG8 only if
    decision 5 says keep), first sitting AG1 and AG2.

## g. Draft ledger rows (written to the ledger only after the owner's go)

| Row | Done when | Model · effort |
|---|---|---|
| AG1 08:00 job survives | the two-person failure test passes; the rollback guard runs in CI | top · high |
| AG2 Every job watched | the CI list test passes; the 08:00 job, backup, TMDB age and a refused venue have rows | top · high |
| AG3 Say it where people look | Home, At the cinema's top and the digest say stale; the device state is on its owner's Home | mid · high |
| AG4 Found for the film | one mechanism; move, merge, undo tested; FK walk test; duplicate-copy row | top · high |
| AG5 Wants know their film | year rule; stored mismatches hidden; the want card asks any want | top · high |
| AG6 Deals | seven titles refused; percentage only when backed; ranking per decision 4 | top · high |
| AG7 One title fold | the 15 pairs and three titles agree | mid · high |
| AG8 Assistant (if kept) | three refusal shapes tested; strict tools | top · high |
| AG9 Security and records | PIN change locks out; drill decrypts; records corrected | mid · high |
| AG10 Polish | 44 px targets; entry chunk under budget | mid · high |
