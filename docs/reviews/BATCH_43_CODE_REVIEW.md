# Batch 43 — Code and architecture review (wave 1, pass R1)

**Pass R1** · reviewed SHA `527522d` · lens: senior software engineer (CR) · read-only · paid
calls: none. Written 11 Oct 2026.

## 1. Summary

Grade **B**. Careful, heavily tested code whose earlier defects are mostly fixed as classes; one
live High (the blind eBay scan) and one failure path that fails.

1. **Correct and safe:** mostly. The eBay scan's mark trusts eBay's clock and has been blind
   since 9 Oct (CR43-01); the identify run's error handler crashes on its first failure (CR43-02).
   35 of 36 rollbacks are safe, and 7 of 10 risky fixes fail their tests when reverted.
2. **Honest:** the web reads every answer through the shared schema (131 of 145 calls; the other
   14 read no body), and the schemas agree with the API today. The same film can still be "the
   same" on one screen and not another (CR43-03).
3. **Doing its job:** the code supports every job. About 7% of it serves features nobody has
   used yet (photos, box sets, smart collections, eBay alerts and accounts), all route-tested.
4. **Noticed:** a blind scan reports "finished" 28 times; no test feeds a future-dated input,
   injects a failure into a run loop, or runs three of the five crons' entry points.
5. **Cheap to run and change:** yes, with three costs: four title rules patched per site, an
   unguarded API–web contract, and agent docs that contradict their own procedures.

## 2. Findings (8: 1 High, 2 Medium, 5 Low)

### CR43-01 — High — The eBay scan's mark trusts eBay's clock; one future-dated listing has blinded it since 9 Oct
- **Evidence:** `proved` — probe 2 drives the real `read_new_listings` with a crafted page: a
  listing dated 12 days ahead becomes the stored mark, and the next pass, offered 50 genuinely
  new listings, keeps 0. `observed` — production, 11 Oct: all 28 runs from 9 Oct 02:21 to 11 Oct
  08:23 read one page, found 0 deals and ended "finished"; mark 21 Oct 16:35:01.
  `implemented` — the mark is the newest `itemCreationDate` seen, with no ceiling at the run's
  own clock, and `scanned_up_to` is the maximum over every run ever, so a later, correct run
  cannot lower it. No test feeds a future-dated listing; the two mark tests assert only that the
  mark equals the newest listing.
- **As a class:** the only stored cursor that takes its value from an outside payload. Checked
  and safe: the Letterboxd sync (no cursor; dedupes per entry), the calendar refresh, the spec,
  review, identify and valuation runs, and deals' "last seen" (all the app's own clock);
  scraping's `Retry-After` (bounded at 90 s, dates parsed). Nearest relative: CR43-06.
- **What the user or operator experiences:** no eBay deal found or pushed since 9 Oct, while every
  run reads as a success. On 21 Oct 16:35 the scan resumes from that mark and never reads what
  was listed in between.
- **Fix and cost:** clamp on write (a listing dated after the run's clock plus a few minutes is
  still read but does not move the mark) **and clamp on read** (`scanned_up_to` never answers
  later than now). The read clamp is what unblinds the stored 21 Oct row without a data write; a
  write clamp alone leaves the scan blind until 21 Oct. A test with a future-dated listing, and a
  standing check: several runs in a row that read one page and see nothing raise a warning Craig
  receives (R2). About two hours with tests.
- **Where it goes:** fast lane (with Craig since 11 Oct; he chose the roadmap). First row of the
  roadmap's eBay group; R5 owns the deal logic around it.

### CR43-02 — Medium — The identify run's error handler crashes on its first failure (a read after a rollback)
- **Evidence:** `proved` — probe 1 drives the real `apply_plan` with a real async session holding
  the run as production's does, and an item that raises a TMDB connection error. The handler's
  rollback expires the run, its next line reads the run's id, and SQLAlchemy raises
  `MissingGreenlet` inside the handler; the TMDB error survives only as its context.
  `implemented` — the only test of `apply_plan` covers success (`failed == 0`).
- **As a class:** 35 of the API's 36 rollbacks are safe: ids taken before the work, frozen
  dataclasses, reload by id (the review, spec, valuation, bid-trial and eBay runs all do it). V9's
  tests met this defect on 3 Oct and it was fixed where found.
- **What the user or operator experiences:** one TMDB hiccup during a live identification run
  ends the run at that film with an unrelated traceback. The row reads "running" for 30 minutes,
  then "abandoned … its process probably stopped"; the planned stop after three failures in a
  row never runs. Films already applied are kept (one commit each). 166 films still wait for
  Craig, so the run is likely to be used again.
- **Fix and cost:** take the run's id before the loop and reload by it, as the review run does;
  one test that injects a TMDB error. Under an hour. **Guard:** one failure-injection test per
  run loop (identify, specs, reviews, valuation, eBay): only success paths are tested, which is
  why this class keeps returning.
- **Where it goes:** new small row, before the next identify run.

### CR43-03 — Medium — Four title rules decide "same film" differently, and are patched per site
- **Evidence:** `proved` — probe 3 runs the four real normalisers (`canonical_title` in the
  catalogue matcher, `fold` in T9's identify, `normalise_title` in the Letterboxd matcher,
  `normalise` in review finding) on 8 pairs; they disagree on 7. The catalogue's rule does not
  read "&" as "and" or drop accents; the reviews rule turns "é" into a gap; only Letterboxd's
  drops a leading article. `implemented` — the spec candidate check patches "&" before calling
  the catalogue's rule, while Search's "you may already own this" check calls it unpatched.
  `computed` — 7 of the 210 unidentified films carry "&" (5) or "and" (2).
- **What the user experiences:** Search can show TMDB's "Angels & Demons" as not owned while an
  unidentified "Angels and Demons" is on the shelf; a review page titled without an accent can
  miss its film. Each feature relearned the same lessons ("Lampoon's" is handled in two files).
- **Fix and cost:** one title-key module with named strictness levels, used by all four; delete
  the per-site patches; the probe's pair table becomes the test. About half a day, plus an
  identify dry-run diff to show no identification moves (R4 to judge).
- **Where it goes:** new row after R4's matching findings.

### CR43-04 — Low — Nothing fails if the web and the API drift apart, and they have twice
- **Evidence:** `computed` — 145 web functions call the API: 131 parse through a shared zod
  schema, 14 read no body (#12 holds). All 109 zod enums cover the API's enums. 88 zod number
  fields refuse a value the API never bounds; the data-driven ones are safe today (a TMDB
  runtime of 0 is sent as null; ratings held at 0.5–5 by a database check; review scores live
  1.5–5.0 with no database bound). #205 records two breaks of exactly this kind (a sold film's
  page; a cached answer missing a new field). `implemented` — no test compares the API's response
  models with the zod schemas, and the enums are closed with no fallback, so a client still on
  the previous build fails a whole screen when the API adds a value.
- **Fix and cost:** a CI contract test: OpenAPI from the app against the compiled schemas (enums,
  nullability, minimums). This review's contract scripts are a start. About half a day. Guard.
- **Where it goes:** new small row; guard list.

### CR43-05 — Low — The offline queue's replay has no test where it matters
- **Evidence:** `proved` — revert-the-fix: deleting the replay's "may have landed → unconfirmed"
  step leaves all 525 web tests green. The first send's version of the rule is tested (#43).
- **What the user would experience if it regressed:** a replay that met a deploy restart would be
  sent again rather than read back; a disc add would usually meet the server's duplicate refusal
  (a question the person must answer), an edit would be applied twice.
- **Fix and cost:** one vitest case. 20 minutes. **Where it goes:** fold into Batch 38 or the next
  web batch.

### CR43-06 — Low — The TMDB client waits however long TMDB asks, doubled each retry
- **Evidence:** `implemented` — on a 429 it waits `Retry-After` × 2^attempt with no ceiling; a
  date-form `Retry-After` raises an uncaught `ValueError`; a 429 on the last try ends as a
  `RuntimeError`, which routes that catch HTTP errors turn into a 500. Scraping's rule (#238) is
  bounded and reads dates.
- **What the user experiences:** unlikely (TMDB rarely refuses), but a refusal burst would hold
  Search, identify and the calendar refresh for minutes.
- **Fix and cost:** reuse the scraping wait rule. 30 minutes. **Where it goes:** with CR43-01
  (same class: outside values are bounded).

### CR43-07 — Low — Three of the five cron jobs have never run in a test
- **Evidence:** `implemented` — the eBay scan, the spec and review job and the valuation job have
  only their `report()` tested; their `main()` (client, session, start, work, deliver) first runs
  in production. The shop check and reminders run `main()` in tests. `AGENTS.md` says crons are
  imported, not run; both crons crashed every night from 10 to 23 Sep unseen.
- **Fix and cost:** one test per job that runs `main()` on CI's Postgres with fake outside
  clients. About two hours. Guard. **Where it goes:** Batch 38's scope, or a new small row.

### CR43-08 — Low — Agent-facing summaries contradict the procedures they summarise
- **Evidence:** `implemented` — `AGENTS.md`'s header and current state say "~140 physical discs"
  (1,884 copies live), "mid-re-scaffold", that the web app "does not boot until Batch 3" and "do
  not build new features onto the old spine"; `docs/agent-commands/README.md` lists close-out as
  "never automatic", while the procedure itself and #24 say automatic. The Supabase-era
  `/migrations/001_profiles.sql` is read by nothing (B1.5). `DECISIONS.md` uses #28 twice.
- **What the operator experiences:** a fresh Claude or Codex session reads `AGENTS.md` first and
  is told the app does not boot and that close-out waits for a command.
- **Fix and cost:** a 15-minute doc edit and one file deleted. **Where it goes:** the synthesis
  PR or the next batch's close-out.

## 3. Follow-through corrections (rows of the pack's table in this lens)

| Row | Pack says | Corrected to | Evidence |
|---|---|---|---|
| B5.1 | "Whether every route is covered is R1's" | Covered: 131 of 145 web calls parse through a schema; 14 read no body; none skips | `computed`, contract scripts |
| B3.4 | Errors are plain strings, no codes: open? | Open, accepted in practice: details are strings except where a screen needs fields (the duplicate refusal); the web keys on status | `implemented` |
| B1.5 | Root `/migrations/001_profiles.sql` | Confirmed dead: nothing reads it (CR43-08) | `implemented` |
| DIGEST §1 | 644 DB tests skip on the Mac | 650: 1,188 passed + 650 skipped = CI's 1,838 | `observed`, local run 11 Oct |
| DIGEST §1 | CI 5 Oct: 1,838 API passed | Confirmed for `527522d` itself: 1,838 passed, 0 skipped; web 525; shared 131 | `observed`, CI run 37348918715 |
| LIVE | 168 routes | Confirmed: 168 operations in the app's OpenAPI | `computed` |
| Scope 1 | 28 blind runs; mark 21 Oct 16:35 | Confirmed at 08:23 on 11 Oct; every one ended "finished" | `observed` |

## 4. Queued and parked items in this lens, re-verified

| Item | Verdict |
|---|---|
| Batch 38, end-to-end suite | Accurate: CI builds the bundle and never runs it. Its scope should take CR43-05's replay, CR43-07's cron entry points and the never-used screens (photos, box sets, smart collections, eBay alerts and accounts) |
| T8b, Connect eBay, "unproved until first sign-in" | Accurate for this lens: 20 parser tests on eBay's sample XML and 10 route tests; no real eBay answer yet (R2, R5) |
| 21, 22c, 33–34, Dead Man's Shoes | Not this lens |

## 5. For reconsideration · Hypotheses · Limitations · Probe log

**Scope finding 8, the features with no use, answered.** Photos, loans, box sets, smart
collections, eBay alert targets and eBay accounts have never run in production. Each has
route-level tests that CI runs on Postgres (test files of 21, 29, 15, 16, 12 and 10 tests); none has run in a
browser. Without loans, they hold about 2,900 API, 2,000 test and 3,800 web lines (7% of the
117k measured). The shelved
bid trial stays on Home by #237's choice.

**Already near-optimal (no change):** the rollback class (35 of 36 sites); held connections (every
long loop commits per item since T9 and 20b); time bombs: all 1,188 runnable tests pass with the
app's clock moved 30, 90, 182 and 365 days ahead (`proved`, clock-shift runs), and the recorded
fixtures are past-dated; migrations 001–048 each reverse, and production sits at 048 with no
drift; Blu-ray.com fetching is one client shared by specs and reviews; eBay listings are parsed
once for valuation, alerts and the scan.

**Revert-the-fix, ten fixes, in a throwaway clone at `527522d`** (fails = guarded):

| Fix | Outcome |
|---|---|
| #200 refresh token split at the last dot | 1 test fails |
| #200 web keeps the session when renewal meets a 5xx | 2 fail |
| #200 web keeps another tab's rotated tokens | 1 fails |
| #238, #240 a refusal waits for `Retry-After` | 6 fail |
| #45 a 5xx or 408 is not the application answering | 1 fails |
| #43 a replay that may have landed is marked unconfirmed | **0 fail: gap** (CR43-05) |
| #53 a date is in the future only if it is not today anywhere | 0 fail locally; a DB test (a purchase dated tomorrow is accepted) guards it, not run |
| #233 the CHECK escapes the apostrophe | 2 fail |
| #110 a 403 or 429 from Blu-ray.com halts everything | 0 fail locally; six DB tests assert the halt, not run |
| e256d65 eBay retries a dropped connection | 2 fail |

Read, not run (DB only): #71 (a test asserts the stored hash is not the token), #194, #198 and
#199 (four `orphan_risk` tests), #232 (changing your mind replaces the vote), #252 (borrower
tests). Each asserts the fixed behaviour.

**For reconsideration:** none. #237 keeps the bid trial; no new evidence.

**Hypotheses** (no evidence of harm yet):
- Movie night: two likes on one card in the same instant can each miss the other (no lock under
  read committed), so "It's a match" is never announced. Production has 0 mutual likes so far.
  Cheap fix: lock the suggestion row before detecting.
- Push delivery claims no rows, so two deliverers at the same moment could send one push twice.
  Overlap is rare: an in-request movie-night send against a cron's pass.
- An installed client behind the API fails a screen on a new enum value until it reloads; the
  worker's immediate takeover and hourly update check bound the window (CR43-04's guard closes it).

**Limitations:** no local Postgres, so 650 DB tests were read, not run (CI ran all 1,838 on 5 Oct);
the clock-shift runs cover the runnable tests only; no browser (R6's pass).

**Probe log** (11 Oct):
- Production, read-only role: 9 SELECTs, each under 5 rows, one refused (a wrong table name, re-run):
  review-score bounds; rating bounds; movie-night likes against announcements; votes per session;
  unidentified titles with "&", "and" or accents; migration head and visible tables; the latest
  3 eBay runs; eBay runs since 9 Oct. No JSON or blob column read.
- GitHub, read: the CI run list and run 37348918715's log.
- Outside services: none. Paid calls: none.
- Local, in a throwaway clone under scratch: the API suite once plus five clock-shifted runs; web
  and shared once; ten reverts; three probes (identify rollback, eBay mark, title rules); three
  contract scripts (calls, enums, number bounds). Clone and scripts stay in `scratchpad/wave-1/r1/`.
