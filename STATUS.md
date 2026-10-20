# STATUS — MCU App

## Now

**20 Oct: a time-zone fault in the stale-edit guard is fixed (#288, migration `063`).** Every
naive-UTC column now defaults to `timezone('utc', now())` rather than a bare `now()`, so a new
row's `updated_at` matches the trigger's UTC whatever the database's time zone. Production was
safe only while Neon runs in UTC; its live zone was not checked from the Mac. No row rewritten.

**20 Oct: Z1, the four faults the end-to-end suite found, is built (#287), and that is Group Z.**
A first message in a new conversation keeps its Yes/No card however late the conversation's
record arrives (a record asked for before the stream ended no longer speaks for the card). A
disc added offline by TMDB id, series id or title, whose answer was lost, is read back through
the duplicate check and settles. Formats read as the Archive names them on the barcode screen,
in the Trash, in a price-alert push and in the offline banner (one server formatter, tied to the
web's list by a test). Two likes cast at once make exactly one match (the night's row is locked
while a vote is recorded). No migration, no live data step. Each fix was reverted once and its
test seen to fail. **Local note, since fixed (#288):** on the scratchpad Postgres (Europe/London)
two stale-edit tests failed on `main` too; the cause was the column defaults, not the tests.

**19 Oct: Batch 38, the end-to-end suite, is built (#94, `DECISIONS.md` #285), and that finishes
Group X.** `apps/e2e` runs the production web build in Chromium, Firefox and WebKit against the
real API on a throwaway Postgres with every outside service faked, plus the five cron jobs run as
Railway runs them: 29 cases on Chromium, 28 on Firefox (dictation skipped, no Web Speech API), 27
on WebKit (2 skipped, reasons in #285), 5 job cases. A seventh CI job, `e2e`, runs on pull
requests and `main` (about 10.5 minutes, 11 billed), **not on feature-branch pushes**. **WebKit
cannot run on the Mac** (Playwright has no build for macOS 13): CI is where it runs. **The suite
found and Batch 38 fixed** a first assistant message that could 500, a queue that could flush
twice at once, and Safari's wording for a removed chunk. **Found, not fixed (#285):** a
new-conversation card race, a TMDB-id add whose lost answer never settles, the raw `blu_ray` on
the barcode screen. **Yours:** the two-phone movie night (16b) now also settles whether Safari
shows a live match on an open page. Run it: `apps/e2e/README.md`.

**18 Oct: X12c, terms and tidying, is shipped (#284; `833369c`, fix `e109b98`), and both its live steps ran at Craig's word the same day.** Settings has TMDB's logo and "not endorsed" notice and JustWatch is credited by the providers; TMDB data older than 150 days is refetched inside the calendar refresh (none is yet; the first is on 5 Feb 2027); Brave results go when a lookup settles; completion sets count the top ten billed and drop shorts and compilations. **Live steps:** `prune_spec_results --apply --expect 9456` deleted 9,456 of 15,516 stored Brave results (6,060 left: 5,210 on lookups still waiting for a person, 850 accepted pages); the completion-set refresh created 22 sets, updated 14, left 4, removed 22 no longer chosen, 0 errors (20 actor and 20 director sets, all refreshed 18 Oct). **Group X's sitting 5 is done**; 38, the end-to-end suite, is next at Craig's go.

**18 Oct: X12b, phone type, targets and speed, is built (#283).** Re-measured first with R6's
axe walker on the current build: the dark primary button is already 4.84:1 and no screen has an
axe violation. Done: nothing under 12 px (390 small-text elements to 0), list links and the
activity rows at 44 px (targets under 44 px 142 to 70; buttons, switches and in-sentence links
not claimed), JSON compressed, the Archive list selecting the 14 columns it shows (5.4 MB to
287 kB of database read on live data) and showing its first 60 films before the rest. Wall-clock
speed on a phone is not measured; check it after the deploy. Next: X12c (terms and tidying; two
live steps at Craig's word).

**18 Oct: X12 is split into X12a, X12b, X12c at Craig's word (#282); X12a is built.** Home says
"Films owned" and "Copies: N discs, M downloads"; the two Digital figures are labelled
(Downloads in Formats, the Digital shelf in Where they live). One date family in `lib/utils.ts`,
with a test that fails on a hand-formatted date. The movie-night shortlist, push and match read
the film's title, year and poster; **a match is stored on the session** (migration 061) and
shown on the night page. A copy's shelf prints once. **Tell Craig:** Mark's You page sends a
line to Craig's "Needs attention" row (migration 062). Next: X12b (phone polish and speed),
then X12c (terms and tidying, two live steps at Craig's word).

**18 Oct: X11, Wanted shows shop prices, alerts need no limit, refusing shops asked weekly
(#281), built at Craig's go after a re-measure.** The Wanted card lists each shop's latest
price with its day and a link; a shop price strictly under the film's stored usual (same format
and standard edition, fresh within 14 days) now alerts when the want has no limit (9 of 10
had none). **The weekly criterion was amended:** no shop refuses *every* request (each of the
three had 5-10 of 10 refused twice, and some retries got through, on each of the last 9
nights), so a shop that refused at least half its requests on seven scheduled checks in a row
(`retailers.refused_nights`, migration 060) is skipped by the scheduled check until a week
after it was last asked; "Run now" asks all. **No live row was written:** every counter starts
at 0, so the half-hour nights (26-29 minutes since 3 Oct) end about 26 Oct, unless Craig says to
seed them (count shown first). Noticed, not X11's: Zavvi has priced nothing since 12 Oct. Next:
X12, same sitting.

**18 Oct: X10, one title rule and owned twins found, slimmed at Craig's word (#280).** Re-measured
first: the four title rules still disagreed on 7 of 8 pairs, but Mark's identifying had merged
all 5 split films and left 1 owned film unidentified, and no copies shared a barcode. Now one
module, `services/title_key.py` (T9's fold and two levels), decides "same title" for Search,
the add form, the spec check, the diary and refresh index and review finding; the diff over all
1,939 live films moves 0 identifications. The add form says "You may already own this" for an
unidentified owned twin, and names the copy a scanned barcode is already on (a box of two
formats is one copy). Merged as `f8de7ab` (PR #86); production API and web report it, `db:
ok`. **The 12 leftover film rows** (9 from the 18 Sep refresh, 3 since) **went to the Trash at
Craig's word the same day**, audited as him and restorable: live films 1,939 → 1,927, 0
leftovers left. Next: sitting 5, X11 → X12, at Craig's go.

**18 Oct: Y6, a doubt shows only while what it is about is still owned (#279), at Craig's
choice of option A, widened.** On 17–18 Oct a re-check doubt outlived the disc it named (#278
binned it): Identify films counted it while the Archive and the film page could not show it.
Now one rule decides, everywhere: a doubt naming a copy shows while that copy is owned and on
the film; one naming no copy shows while the film has a copy. Binning or selling hides it,
restoring or unselling brings it back; nothing is written either way. "Identified, in doubt"
now counts films, equal to the Archive's "In doubt (N)"; the daily check counts films whose
doubt is a fortnight old. No live data step: live has 0 open doubts.

**17 Oct: Y5, Mark's 16 Oct points, built at Craig's word of 16 Oct (#277).** A disc can be
added to, or one copy moved to, a TMDB series: the add form and "Move only this copy" list
series apart from films, and a doubt's move opens already searched on the sheet's title, so
BBC's *Life*, the 1979 *Tinker Tailor* and the 2019 *Name of the Rose* are one tap from their
doubts (the series search reads two TMDB pages: BBC's *Life* is 28th for "Life"). The
Archive's genre filter offers **Film Noir**, TMDB's keyword 9807, from `movies.tmdb_keyword_ids`
(migration 059); every full TMDB fetch fills it, and the films identified before Y5 wait for
`src.scripts.fill_keywords --apply`, **run 17 Oct at Craig's word: 1,905 filled, 225 noir, all
on the shelf.** Merged as `99cee5e` (PR #82); production API and web report it, `db: ok`. A
disc TMDB lacks is added by its title and filed as not a film. **Next for Craig or Mark:** the
three series moves in the app (item 33, step 2).

**12 Oct 2026: the wave 1 full review is done, and its remediation is Group X** (#253,
`docs/reviews/BATCH_43-48_ROADMAP.md`). Six passes at `527522d` found 44 findings, 10 High; the
roadmap's twelve packages are X1–X12 in `docs/phase-batches.md`, "Group X — the wave 1 review,
planned 12 Oct", in five sittings (#255). **Sitting 1 is done: X1, the eBay scan, X2, the daily
check, and X3, push that heals itself, shipped 12 Oct (`7979e19`, `857ee8f`, `adcae0d`).
Sitting 2 is done: X7, the assistant repair (`aa6946d`), and X8, offline, drift and failure
words (`e991281`), shipped 13 Oct. Sitting 3 is done in code, 14 Oct: X6, value as used copies
(`51c81ff`, #267); X4, a weekly encrypted copy outside Neon with a monthly restore drill
(`87a734b`, #268), its credential steps done by a session at Craig's word and its first run
passing its drill; and X5, watch history (`19c9aad`, #269). **X5's live data steps wait for
Craig's word:** the diary backfill (651 watches, about 490 films added; 105 doubtful entries
listed for him), 7 of the 15 misattributed watches moved (8 doubtful), and Mark's username;
then both press Sync now.** **Sitting 4 began 15–16 Oct at Craig's go ("code here, data at
the Mac"): X9, catalogue truth, shipped 16 Oct ([#79](https://github.com/CraigR973/mcu-app/pull/79),
#275).** An identified film can be "in doubt" (Identify films and its page say so); the spec and
review jobs raise a doubt when a page for the film's own title is another year's; one copy can
move to another film; inferred editions read "Probably …"; `MatchingEngine` decides nothing in
the app. **Its live step ran on Craig's Mac, 16 Oct (item 32):** after Mark's afternoon of
identifying fixed 14 of the review's 30, a clean dry run re-checked 1,486 copies (1,102 agree;
5 different, 3 series, 3 not offered, 373 unsure) and, at Craig's word, raised all 384 as doubts
on Identify films (0 kept before, 0 changed). Of the 30: 19 corrected, 10 wait as doubts, and
King Kong [1976] was not re-checked, since its film was identified since. **Both settle the
384 since Y4, built at Craig's word the same evening (#276):** the Archive's "In doubt" filter
finds them, and each film page lists its open doubts with It's right, Correct match and Move
only this copy, for Mark too, audited as whoever did it; Craig sees a keep under Recently
identified and undoes it there. Mark added right copies of King Kong (1976) and Ghostbusters II
rather than moving the wrong ones, so each old copy is now a duplicate to bin. Next: X10, at
Craig's go.
**Craig's, from X4: copy `~/.mcu-secrets/backup-age-key.txt` into the password manager.**
Without a copy off the Mac, losing the Mac makes every backup unreadable.
**What X6 does to Home:** every stored value was a new copy's price, so all 1,454 are due and
count nowhere until re-priced; the scheduled runs of 15 and 16 Oct 04:00 UTC re-price them as
used copies (750 eBay calls each, the usual share). Until then Home shows no total, then a
partial one. Pressing **Update values** on Admin's Collection value today would start sooner.
**Also 13 Oct, outside Group X: Group Y, Mark's requests, is done.** Y1 (`4840711`, #264):
Mark edits, moves and deletes copies. Y2 (`e0b5bad`, #265): Move discs, a tray of discs found
by search or scan, moved together and movable back (Group Y in `docs/phase-batches.md`). Mark's
first feedback was fixed the same evening (`2ef3b8a`, #266): a shelf-only edit kept the old
location text, and the delete question hid its own Yes on a phone. His second, 14 Oct
(`f5f63e2`, #71, #270): the Lounge has a Side picker (Left / Right hand side, in `shelf`), and
migration 055 filled in the side of 164 live and 160 trashed Lounge copies from their text;
detail typed beside a section is kept after it ("Garage - top row"), where #266 had dropped
it; the add form's TMDB search shows 20 and reads a trailing year, so "Texas Chainsaw Massacre
1974" finds TMDB's "Chain Saw". **Mark's to do:** pick the side again for Nope and Us (both
4K, Lounge), whose typed side #266 dropped; re-save 12 Angry Men's 4K (Front 4th) to tidy its
text, and decide whether its location-less Blu-ray, added twice on 10 Oct, goes to the Trash. Home's "Needs attention" row is live for Craig; the
first check runs at 08:00 UTC on 13 Oct, and until then the row says it has not run yet.
**Mark's third feedback, 15 Oct, after working through about 200 unidentified films** (#272,
#273), **shipped 15 Oct as `ef62257` (#75), verified in production by Craig** (API and web
both report it, `db: ok`, every field `configured`): a title is flagged "Identify"
exactly when "Still to identify" (#73, #271) lists it; on a phone the open Filters panel ends in
"Show N films" and closes on the back gesture, where before it hid the films (the grid measured
0px) and back left the app; and **Y3, built at Craig's word the same evening, identifies TV
series from TMDB** (`movies.tmdb_tv_id`, migration 056), from a title's page by either person,
"Correct match" included, so Band of Brothers and 11.22.63 can go from the films they were
matched to, to the series they are. The 34 series T9 set aside are back under "Still to
identify". **Owner action 31 ran on Craig's Mac, 15 Oct (#274):** the read-only pass found 45
titles; Craig moved The Kennedys to Mark's list, then authorised the live plan. It identified
33 series, left the second Shetland row waiting because its series ID was already held, and
failed on none. The first live `/tv/{id}` answers worked with the series model. The read-only
film check examined 1,852 identified films and found 9 suspects, with no TMDB failures. Mark
still has 11 titles to choose and the agreed film-matched series to correct (item 31).

| Batch | State |
|---|---|
| ~~X1~~ → ~~X2~~ → ~~X3~~, sitting 1 | done 12 Oct (`7979e19` #258, `857ee8f` #259, `adcae0d` #260) |
| ~~X7~~ (`aa6946d` #262) → ~~X8~~ (`e991281` #263), sitting 2 | done 13 Oct |
| ~~Y1~~ (`4840711` #264) → ~~Y2~~ (`e0b5bad` #265) | done 13 Oct |
| ~~Y3~~ (`ef62257` #75, #273), TV series, with #272's two fixes | code done 15 Oct; live pass identified 33, 1 duplicate waits; read-only film check found 9 suspects; Mark's review remains (item 31) |
| ~~Y4~~ (#276), Mark settles the doubts from the film page | shipped 16 Oct; the 384 are both people's to settle |
| ~~Y5~~ (`99cee5e` #82, #277), series added and moved, Film Noir, add by title | shipped 17 Oct; keywords filled (225 noir); the three series moves are Craig's or Mark's (item 33) |
| ~~Y6~~ (#279), doubts on a film with no copy | shipped 18 Oct; no data step |
| ~~X6~~ (`51c81ff` #267) → ~~X4~~ (`87a734b` #268), sitting 3 | done 14 Oct; values re-priced by the runs of 15–16 Oct; backups weekly from 19 Oct |
| ~~X5~~ (`19c9aad` #269), sitting 3 | done in code 14 Oct; live data steps at Craig's word, by 31 Oct |
| ~~X9~~ ([#79](https://github.com/CraigR973/mcu-app/pull/79), #275), sitting 4 | shipped 16 Oct; the live re-check ran 16 Oct, 384 doubts raised; settling them is Craig's (item 32) |
| ~~X10~~ (`f8de7ab` #86, #280), one title rule, owned twins | shipped 18 Oct; the 12 leftover rows trashed at Craig's word |
| X11 → X12 | sitting 5 (#255), at Craig's go |
| 38, the end-to-end suite | at Craig's go, last; six cases added by the review |
| 21 · 22c · 33 → 34 | unchanged: 21 waits on data; 22c and email parked |

- **Live faults (12 Oct, read-only):** the eBay deal scan read 0 listings in 45 of 45 runs
  from 9 Oct until X1's deploy (stored mark 21 Oct 16:35); the first pass after X1's deploy (20:23 UTC) read 2,709 listings and found 21 deals; 30 copies are confidently the wrong film; every second
  message to the assistant failed until X7 (13 Oct; a live follow-up is Craig's to try); no copy of the database exists outside Neon's six-hour
  window. Pushes reach both phones again, re-registered by hand on 11 Oct.
- **The nightly jobs (UTC):** 02:00 `cron-specs` (specs, then reviews); 03:00 `cron-scrape` (Zavvi
  and Arrow answer, the Shopify shops refuse, #247; shown Crashed every night by design until
  X2); 08:00 reminders; `cron-ebay` every two hours (blind until X1); `cron-values` on the 1st,
  2nd, 15th and 16th, its first run with work on 1 Nov 04:00.
- **The gate** is six CI jobs (#248). Locally: API 1,188 passed and 650 skipped without Postgres
  (11 Oct), web 525, shared 131.
- **Craig's open items** (`OWNER-ACTIONS.md`): a copy of the backup's private key off the Mac
  (X4, 14 Oct); 29 connect eBay; 22 the Neon
  password (left for now, 12 Oct); the Identify films (165) and Disc specs (525) queues; the
  384 re-check doubts on Identify films (item 32, 16 Oct); Y5's keyword backfill and the
  three series discs (item 33, 17 Oct; the keyword backfill is done).

**Live numbers (12 Oct, read-only):**
- **Collection:** 1,889 live copies (1,466 discs, 422 downloads, 1 unlabelled); 1,891 films,
  209 without a TMDB id.
- **Identify:** 157 identified, 165 waiting, 35 set aside. **Disc specs:** 734 done, 525 waiting.
- **Value:** £23,604 over 1,300 priced discs, 92.5% of it new-copy asking prices; X6 (14 Oct)
  re-prices it as used copies on 15–16 Oct, roughly £12,800–£17,200 by the review's estimate.
- **Watch history:** Craig synced once (11 Oct, 4 written); Mark has no username stored (X5).

**The Now entries this block replaced** (5 Oct, Group W) are in git: `git show 527522d:STATUS.md`.
The Log keeps a dated line for each.

## Next

**The remaining sequence is Group X's table in `docs/phase-batches.md`** (the wave 1 review's
remediation, #253, in five sittings since #255), then 38. **Sitting 1 is done** (X1–X3, 12 Oct);
**sitting 2 is done (X7, X8, 13 Oct); sitting 3 shipped X6, X4 and X5 (14 Oct); X5's live data steps wait for Craig's word, by 31 Oct.**
Groups V and W are done; their records stay in the ledger.

**Four acceptance criteria an agent cannot meet.** Say so plainly in each close-out; never let
a green gate imply otherwise. 6.2 (two devices) · 5.6 (a price-drop push received) · 9.5 (a
spoken query) · 8.4's "notification to both", depending on how the match is signalled.

**Settled inputs, so no batch has to ask again:** the AI daily cap is **50 messages per person**
(`#112`'s neighbour, recorded in the ledger); photos are capped at **~300 KB** after
server-side resize and stored in Postgres, not an object store — **confirmed by the owner
2026-09-10, `#120`**; Batch 23 gathers its ten
Blu-ray.com URLs from browse pages under `#110`'s bounds and extracts no prices.

### Verify against the live system, not only the suite

Three times on 2026-09-09 a green gate coexisted with a broken feature: CI was green while
production had no TMDB token; the scraper "test" button showed results while saving nothing;
and phase 5.5 carried a criterion no correctly working system could satisfy. For each batch,
run the gate **and then exercise the real thing** — live API, real database, the browser where
it renders — and report what was observed rather than what passed.

### Four things the next agent should know

1. **Planned batches whose criteria have not yet been recovered need them written into the
   ledger before implementation.** Batch 10 removed §16. Recover them verbatim from
   `git show d94a6b8~1:MCU_Architecture_v2.1_FINAL.md`, grep for `**Phase X.Y:`, and write
   them into the batch's ledger section **before** writing code (`DECISIONS.md` #54).
2. **Adding a Python dependency means regenerating both locks.** CI installs with
   `pip install --require-hashes -r requirements-dev.lock`; `pyproject.toml` alone is not
   enough. The command is in each lock file's own header.
3. **The Postgres-backed tests cannot run on this machine** — no local server, no Docker — so
   650 of them skip locally (11 Oct) and run only in CI; run the suite with `env -u
   DATABASE_URL`. A throwaway local Postgres does work: `pgserver` 16.2 is in the API venv,
   and the wave 1 review ran the 60 assistant tests against one (its scripts are in
   `scratchpad/wave-1/r3/probes/`, gitignored). Do **not** point them at production Neon to
   get local coverage. A test fixture bug on 2026-09-09 used an unresolvable host and was
   caught only because CI ran it against real Postgres; against Neon it would have passed and
   shipped hidden behind a green local run.
4. **Anything that lives only in a Railway variable has no test.** The TMDB token was missing
   for an unknown length of time behind a fully green gate. `AGENTS.md` already says the gate
   proves the code and not the infrastructure around it — the TMDB outage is what that
   sentence looks like in practice.


## Gotchas

0. **The collection is 1,857 items, not ~140 and not 1,866.** Measured by running the
   real parser over the real spreadsheet on 2026-09-07. The sheet has 1,867 rows = 1
   header + 1,866 data rows, but **9 of those data rows are entirely blank** (all nine
   columns `None`, at sheet-rows 1857–1863, 1865, 1866). The parser correctly drops them
   and returns 1,857 candidates → 1,847 distinct titles, 10 of them repeated.

   **1,866 was a trailing-blank-row artifact and was wrong everywhere it appeared** — the
   roadmap's mentions, this gotcha, and Batch 4's own acceptance criterion. Phase 1.5's
   acceptance ("parser produces 1,866 structured entries with no data loss") was therefore
   unsatisfiable as written and always had been; there is no data loss, the count was just
   wrong. Corrected in `MCU_Architecture_v2.1_FINAL.md` and `docs/phase-batches.md`
   (`DECISIONS.md` #29). **`docs/part-b-audit.md` and `docs/part-d-roadmap.md` still say
   1,866** — they are dated analysis records and are left as written per `DECISIONS.md` #16.

   `import_review.csv` (137 rows) is a *review-queue* artifact from the April import, not
   the collection. Anything that scales with catalogue size — location tracking, shelf QR
   codes, smart collections, saved filters, export, natural-language search — must be
   judged at 1,857.

0b. **FIXED AND VERIFIED IN BATCH 4, COMPLETED IN BATCH 6. The location data was
   extracted at import and then discarded** — the most consequential defect the 2026-09-07
   review found. **1,855 of the 1,857 items now carry a structured `section`, and all 1,857
   carry their `location` text**, in the live database. Batch 4 got 1,733 of them; Batch 6
   added the four cabinets to the vocabulary and backfilled the remaining 122
   (`DECISIONS.md` #34). Only 2 are unsectioned, and correctly so. **Batch 6 also made the
   data reachable** — until then the columns and the composite index existed and no
   endpoint queried them. Kept here as the record of what was wrong and how it was proved
   fixed.

   What was wrong, each link verified in April and re-verified 2026-09-07:
   - `MCU_Architecture_v2.1_FINAL.md` §3.4 **designs** `location`, `section` and `shelf`
     as first-class columns on `collection_items`.
   - `apps/api/src/spreadsheet/parser.py` **implements** the extraction — `parse_location()`
     yields `section` and `shelf`.
   - The legacy `0003_create_collection_items.py` and the pre-re-scaffold flat
     `models.py` **omitted all three columns**.
   - The importer therefore fell back to `notes = candidate.location_raw` — the **raw**
     string survived, the parsed structure was thrown away, and `notes` then held location
     for imported rows and real notes for hand-added ones with nothing to tell them apart.
   - `0015`'s `search_vector` never referenced `notes`, so the "put it in notes" workaround
     would not have made location searchable even if it had been deliberate.
   - §6.2 promises *"show me everything on the Front 2nd shelf"*. Not implementable as built.

   **What Batch 4 changed.** Migration `003` creates `location`, `section` and `shelf` as
   real columns with a CHECK constraint pinning `section` to the five §3.4 values, and a
   partial composite index on `(section, shelf) WHERE deleted_at IS NULL` — the index
   Batch 6's "Front 2nd shelf" query needs. The importer writes all three and leaves
   `notes` alone. `parse_location` also gained `E:\\Movies` → `Digital`: the digital
   library is only ever recorded as its filesystem path, so without it all 413 digital rows
   landed with `section IS NULL` and the vocabulary never produced the value §3.4 names.

   **Coverage after Batch 4 was 1,733 of 1,857** (Front 550, Back 575, Digital 413,
   Lounge 160, Garage 35), with 124 cabinets unsectioned. **Batch 6 settled that question
   by growing the vocabulary**: Top Big Cabinet 38, Top Small Cabinet 38, Fish Room
   Cabinet 26, Black Box 20 — 122 rows, leaving 2. `location` was never modified, so the
   backfill is derived and reversible.

1. **RESOLVED. The derived-field trigger tests now run in CI — 14 of them, zero skips.**
   Proved on run `34162647232`: `tests/test_derived_field_triggers.py ..............`
   against the Postgres 17 service, no `s` characters in that line.

   They were **re-authored, not resumed.** They could not be resumed: every one of them was
   written against the April schema — `movies.id` as an INTEGER TMDB id, a scalar `format`
   column, scalar `hdr_format` and `audio_formats[]` — and all three are gone under §3.4.
   All 13 original behaviours are preserved one-for-one; the 14th covers a combo pack whose
   single row holds several formats, which the old scalar column could not express.
   This was an owner decision taken at the start of Batch 4 (`DECISIONS.md` #28) precisely
   because rewriting a test to match new code is otherwise forbidden as a route to green.

1b. **RESOLVED. The matching engine used to let TMDB popularity decide which film was on
   the shelf.** Found by Batch 4's own `--dry-run`-against-`matching_eval.csv` criterion,
   which is exactly what that criterion exists for.

   The mechanism, both links verified: `engine.py` scored `original_title` as well as
   `title` and took the **max**, so a film whose *original* title matched scored
   identically to one whose displayed title did; then it sorted by
   `(confidence, popularity)`, so ties were broken by a ranking that is not stable over
   time and now favours 2025/2026 releases.

   Measured over all 1,857 titles before the fix: **687 matched rows (39.9%) had ≥2
   candidates tied at the top confidence, 652 of them with no year in the source title —
   35.1% of the collection.** `Frankenstein` → 2025 rather than the 1931 Karloff,
   `Lolita` → 1997 rather than Kubrick's 1962, `Amistad` → `Friendship (2023)`.

   **The fix** (`DECISIONS.md` #31): `title_is_exact` promotes a displayed-title match
   over an `original_title`-only one — a tiebreak that never moves a confidence — and
   `is_ambiguous` marks a leader tied with films that are not plausibly the same one.
   Ambiguous rows are **catalogued with their location** and only their identification is
   deferred to review. After the fix: 1,093 settled, 628 ambiguous, 136 unmatched.

   **The ranking is still imperfect, but Batch 5 gave it a route out.**
   `title_similarity` floors a substring match at 0.9, and a near-miss that appends a
   numeral can beat it: "french connection" scores 0.919 against "French Connection II"
   and only 0.900 against the correct "The French Connection", because a leading article
   costs more than an appended "II". **11 of the 1,093 settled rows are in this class and
   about four look wrong:**

   | sheet row | as written | chose |
   |---|---|---|
   | 550 | French Connection | French Connection **II** (1975) |
   | 1789 | X-Men 2 | X-MEN 2 - **Wolverine's story** |
   | 1831 | 11.22.63 | 11-22-63: **The Day the Nation Cried** |
   | 1254 | Planet Earth II | Planet Earth II: **A World of Wonder** |

   **These are now corrected in the app, not in the engine.** The identify picker, opened
   from an already-identified film, replaces any of them in a click (`DECISIONS.md` #33).
   A third change to the matching ranking would have cost its own measurement pass over
   all 1,857 titles and risked regressing matches that are currently right.

2. **The new migration chain starts with an intentionally empty `001`.** It has been
   proven to apply and reverse against disposable Postgres, and CI repeats both commands.
   Batch 3 owns the auth schema and Batch 4 owns the domain schema; do not put future
   tables into the baseline.

3. **`cd` is actively dangerous here.** autoenv sources `apps/api/.env` on entry and raises an interactive allow/deny prompt. Use absolute paths.

4. **~22 of the 25 tables are speculative** — created in April for roadmap stages 4–11 that were never built. Do not assume a table's existence means its feature exists. Part D decides which survive onto the new baseline.

5. **RESOLVED IN BATCH 9 — and there were four dead steps, not three.** The wizard is
   rebuilt against a real completion column (migration `010`), and every remaining step is
   backed by something that exists.

   - `StepInstallPWA` read `window.__pwaInstallPrompt`, which nothing set and nothing
     could have — there was no manifest and no service worker for `beforeinstallprompt` to
     fire against. **Batch 8 supplied both**; `usePwaInstall` now captures the event, and
     falls back to instructions on iOS, which never fires it.
   - `StepNotifications` offered to enable push against **zero** infrastructure, and still
     does: no VAPID key, no subscription, no endpoint, no `push_subscription` column.
     **Dropped, not fixed** (`DECISIONS.md` #50) — the batch definition's claim that it
     "now has real infrastructure behind it" was wrong. **Batch 11 owns bringing it back.**
   - `StepEmailConnect` was doubly dead: Stage 10 is dropped *and* this app has no email
     addresses at all, since sign-in is a display name and a PIN.
   - **The fourth, which this gotcha never listed:** the catalogue step read
     `d?.meta?.total` — the `{data, meta, errors}` envelope `DECISIONS.md` #6 removed — so
     it rendered a loading skeleton for ever. A dead read can hide behind a plausible
     loading state indefinitely.

7. **RESOLVED IN BATCH 5. The web app now parses every API response through
   `packages/shared`.** It previously imported no shared schemas at all — expected during
   the bottom-up re-scaffold, but only true because there were no read endpoints yet.
   Batch 5 shipped the schemas with their endpoints, as `DECISIONS.md` #6 requires: 7
   `.parse()` call sites and **zero `as Promise<T>` casts** on an API response. The rule
   that made this hold is that a schema ships *with* its endpoint — one added later never
   gets added.

8. **`pnpm -r test`, not `--filter @mcu/web test`** — the filtered form never runs `packages/shared`.

9. **mypy runs `strict = true` with `warn_unused_ignores`** — prefer `model_validate()` over `**spread` with a `type: ignore`.

10. **`ruff format` (not just `ruff check`) must pass** — a Phase 3.1 commit failed CI on formatting alone.

11. **A GitHub PAT was committed in April and remains in git history** (commits `4768da8`, `0bfb672`). It is dead (401) and now redacted from the working tree, but **it has not been revoked at GitHub and history has not been rewritten.** Both are outstanding owner decisions.

12. **A Railway 502 does not mean the app is down.** The public domain must target
    Railway's injected `PORT` (8080), not the Dockerfile's `EXPOSE 8000`. Pointing it at
    8000 returned a public 502 while the container was healthy and its internal
    healthcheck returned 200 throughout. `DECISIONS.md` #20; `.railway/README.md`.

13. **Run the Railway CLI on Node 22+.** Its IaC engine uses Node's type-stripping flag,
    which Node 20 rejects, so `railway config plan` fails before touching infrastructure.
    The app's own build stays on Node 20.

14. **`mcu-app.vercel.app` is somebody else's app.** The bare name was taken, so Vercel
    assigned us `mcu-app-fawn.vercel.app`. `FRONTEND_ORIGIN` was initially set to the bare
    name, which pointed the API's CORS allowlist at a stranger's deployment while excluding
    our own front end. Corrected at close-out. **Read the alias list from
    `vercel inspect`; never assume the project name is the domain.** `DECISIONS.md` #23.

15. **There is no local Postgres and no Docker on this machine.** Migration changes and
    the DB-backed lockout tests cannot be run here at all — they skip locally and only
    execute in CI. Both of Batch 3's CI failures were migration defects invisible to a
    green local gate. **Treat a green local run as silent about anything touching SQL.**

16. **The first real write against real data is its own test stage.** Batch 4's gate was
    green, its `--dry-run` was clean, and the live import still hit three separate
    defects: the importer could not connect to any hosted database (its tests mock the
    connection), a 300-character `character_name` overflowed `VARCHAR(255)` and rolled
    back a whole item, and an idempotency key on the item's contents collapsed two
    distinct discs into one. **No test could have caught any of them** — mocks do not
    enforce column widths or unique constraints, and a dry run never writes. Budget for a
    real write, and read the import summary's error count rather than trusting its
    success lines (`DECISIONS.md` #32).

17. **A bare digit in a location string is not a shelf.** `parse_location`'s ordinal
    regex used to match any `\d+` anywhere, so `Top small cabinet (Arrow 4 Film Noir
    Classics Vol 2)` became shelf **"4th"** for four live discs. `Back 6th Shelf (Arrow 4
    Film Noir Classics Vol 1)` was right only because `re.search` returns the leftmost
    match — a correct answer for the wrong reason, which is the harder kind to notice.
    Fixed in Batch 6: a shelf needs its ordinal suffix, or the word "shelf" after the
    digit. **The general lesson is that the box-set titles in these cells are full of
    numerals**, so any future parse of `location` must anchor on structure rather than on
    finding a digit (`DECISIONS.md` #36).

18. **CI's migration job runs against an empty schema, so it cannot prove a backfill.**
    `upgrade head` → `downgrade base` proves a data migration *applies and reverses*; it
    says nothing about whether its `WHERE` clauses select the right rows, because there are
    no rows. Batch 6's `007` was checked by running its own predicates as read-only
    `SELECT`s against live Neon first — 122 sectioned, 4 shelves cleared, 2 left — and the
    post-deploy counts matched exactly. Do that for any future migration that writes data,
    and see gotcha 16 for why.

19. **A green build, green types and green tests can all coexist with a page that lies.**
    TanStack Query **pauses** a retry when it believes the app is offline: the query sits
    at `status: 'pending'`, `fetchStatus: 'paused'`, `isError: false`, with no data, and
    stays there. The usual `isLoading → isError → items.length === 0` ladder therefore
    falls through to the **empty state** — so `/trash` rendered "Nothing has been removed."
    while its request had never come back, indefinitely and confidently.

    Found by opening the page in a browser during Batch 7, with nothing failing anywhere
    else. `listState()` in `apps/web/src/lib/query-state.ts` names the fourth state so a
    list can say "waiting for the network" instead (`DECISIONS.md` #41). **Any new list
    must use it**, and Batch 8's offline banner should build on it rather than around it.

20. **A pydantic `field_validator` does not run for a field the request omits.** Batch 7's
    create body used one on `tmdbId` to enforce "exactly one of `movieId`/`tmdbId`", which
    correctly rejected a body naming *both* and silently accepted one naming **neither** —
    a 500 where a 422 belonged. Use `model_validator(mode="after")` for any rule that spans
    fields or must hold when a field is absent.

21. **`mypy` is unpinned (`>=1.11.2`), so local and CI disagree about unused ignores.**
    A `# type: ignore[arg-type]` that this machine's mypy 2.3.1 considered *necessary* was
    reported as *unused* by CI's, and `warn_unused_ignores` made that a red gate. The fix
    is to write code that needs no ignore — narrow in a loop rather than assert in a
    comprehension. **Pinning mypy is an open suggestion, not a decision taken.**

22. **A green build, green types and green tests prove nothing about behaviour with the
    network away.** Batch 8's four defects were all found by driving the built app against
    a stub API that could be switched off, with everything else passing. The most
    important: **React Query pauses queries and mutations when it thinks you are offline**
    (`networkMode` defaults to `'online'`), which silently disables both halves of an
    offline story — the mutation never runs `mutationFn`, so an offline write queue inside
    it is unreachable, and the query never issues the fetch a service worker exists to
    answer. `apps/web/src/lib/query-client.ts` sets `'always'`, and
    `query-client.test.ts` hangs if that is reverted. **Any new QueryClient must keep it.**

23. **`fetch` resolves for a 5xx, so "the server answered" and "the write was applied" are
    different questions.** A 503 comes from a gateway, a proxy, a captive portal or a
    container that is still booting as readily as from the application. Treating one as a
    refusal discards the write; treating it as certain failure and retrying duplicates it.
    It is the *unknown* case — see `DECISIONS.md` #43 — and the same reasoning is why
    only a 401 or 403 may end a session (#48).

24. **`NOW()` in Postgres is the transaction start time.** Every row written by one
    transaction gets the same value, and two updates inside one transaction are
    indistinguishable. That is fine for "created at" and wrong for "modified at" — and
    once `updated_at` became Batch 8's concurrency token it was a guard that could not
    detect anything. Migration `009` moves `set_updated_at` to `clock_timestamp()`.
    **The test harness runs each test in one transaction**, so anything that depends on
    time advancing must use `clock_timestamp()` or it will pass for the wrong reason.

25. **A service worker cannot be registered from the tooling available here.** The
    in-app browser pane refuses with "An unknown error occurred when fetching the script"
    even though the file serves correctly, and no Chrome extension is connected.
    Everything else about the PWA is verifiable — the manifest, the icons, the generated
    worker's contents, the queue end to end — but **"it caches the collection offline" and
    "it installs to a home screen" can only be confirmed on a real device.**

26. **`date.today()` reads the *server's* timezone, and this codebase is UTC everywhere
    else.** A test can therefore go red from the clock alone, with nothing changed: the
    watch-log default was computed in UTC and validated against local today, which agree on
    Railway and disagree on a British machine for the hour after midnight. Green in CI all
    day, red at 00:07 BST.

    Use `src/clock.py` — `utcnow()`, `utc_today()`, `latest_plausible_today()` — never
    `date.today()`. And for a date a *person* supplied, "in the future" means "not today
    anywhere on Earth" (UTC+14), not "later than today here": a guard on UTC today refuses
    someone in London logging tonight's film at 00:30 (`DECISIONS.md` #53).

27. **`set -a; . apps/api/.env.local` silently drops `DATABASE_URL`, and pytest then reports
    green while skipping 246 tests.** The Neon URL ends
    `?sslmode=require&channel_binding=require` — **unquoted**, so bash reads the `&` as job
    control: the assignment is backgrounded (no effect on the shell) and
    `channel_binding=require` runs as its own command. `DATABASE_URL` ends up unset, the
    database-backed tests skip rather than fail, and the run exits **0**.

    Hit during Batch 27's close-out: `301 passed, 246 skipped` looked green next to the real
    `547 passed`. Always read the count, not the colour. Export it by hand instead:

    ```
    export DATABASE_URL="$(grep '^DATABASE_URL=' apps/api/.env.local | sed 's/^DATABASE_URL=//')"
    ```

28. **`cryptography` runs at a different version here than in CI, and it is the security
    floor that forces it.** The lock pins **50.0.1**; this machine has **48.0.1** and
    cannot install the pinned one. cryptography 49+ ships no `macosx-10.15-x86_64` wheel,
    so pip falls back to a Rust source build that fails here, while CI's and Railway's
    manylinux wheels install without comment.

    The obvious fix — pin below 49 — was tried and **reverted**: 48.0.1 carries
    PYSEC-2026-3552, -3553 and -3554, and CI's dependency-audit job refused it, correctly.
    A vulnerable crypto library in production is not worth a tidy local install
    (`DECISIONS.md` #115).

    **So CI is the authority for anything touching `cryptography`**, which today means
    Web Push. A local `pytest` run exercises the same tests against a different version of
    the library, and a green local run is therefore weaker evidence than usual — the same
    caveat gotcha 15 puts on anything touching SQL. Lift this when the developer machine's
    platform tag moves past `macosx-10.15-x86_64`.

29. **Prepending Node 22 to `PATH` makes the Railway CLI vanish**, and the error blames
    the wrong thing: `bash: railway: command not found`, which reads as "not installed".

    Two facts collide. The IaC engine needs **Node 22+** (gotcha in `.railway/README.md`),
    but the CLI is installed under **Node 20's** nvm bin — `nvm alias default` is 20 — and
    is an `#!/usr/bin/env node` script. So `PATH="…/v22.23.2/bin:$PATH" railway …` fixes
    the runtime and removes the binary, because `railway` was never in Node 22's bin.

    It is easy to miss from an agent session, where the shell is initialised from the
    user's profile and already has Node 20's bin on `PATH` — the bare `railway` form
    resolves there and fails only in the owner's terminal. **`.railway/README.md` carried
    the broken form** until 2026-09-10.

    Both halves, and it works from a shell with no nvm loaded:

    ```
    PATH="$HOME/.nvm/versions/node/v22.23.2/bin:$PATH" \
      "$HOME/.nvm/versions/node/v20.20.2/bin/railway" config plan
    ```

    The general rule this is an instance of: **a command that only works because of the
    ambient shell is not a command worth writing into a doc.** Test it under
    `env -i HOME="$HOME" PATH=/usr/bin:/bin bash -lc '…'` before handing it to anyone.

30. **The first version's data is no longer in the old Supabase project.** That project's
   `public` schema held it: 27 tables at Alembic `0017`, last written 27 Apr 2026, with rows
   only in `movies` (1,697), `collection_items` (1,830) and `movie_credits` (69,421). On
   2026-09-24 it was archived to
   `~/garmin-coach-snapshots/2026-09-24-mcu-v1-public-schema/` on Craig's Mac, as a
   gzipped `pg_dump` with a README giving the row counts, checksum and restore steps. It
   was then dropped to free space for Garmin Coach (garmin-coach `DECISIONS.md` #349).
   Nothing live used it, because this app has run on Neon since #17. **Restore it only into
   an empty database or a scratch schema**, because its table names are the same as this
   app's.
31. **A recorded payload can carry a real expiry, and a route that reads the wall clock turns
   it into a time bomb.** The eBay listing behind the alert tests ended at 09:06 UTC on 3 Oct
   and failed two tests on every branch (#242). A test that sends a capture through a route
   pins that route's clock to the capture's time; a service call takes `now=` explicitly. When
   a test fails on a branch that did not touch its area, check whether `main` fails the same
   way before blaming the branch.


## Log

- **2026-10-20 (fix, #288)** — Two stale-edit tests failed on a Europe/London Postgres, on
  `main` too. Cause: 54 naive-UTC columns defaulted to a bare `now()` (session-local time)
  while the `set_updated_at` trigger writes UTC, so under BST a new disc's first edit looked
  older than its original and a stale edit was accepted. Migration `063` sets every one to
  `timezone('utc', now())`; a catalogue guard and two Tokyo-zone tests fail on the old schema.
  Full API suite green on a London and a UTC database. Neon's live zone not checked (no
  read-only URL on the Mac).
- **2026-10-20 (Batch Z1, #287)** — Re-verified the four faults at `1faf99a` (all present; the
  card race worse than recorded, the raw codes in three more places). Locked the night's row while
  a vote is recorded, added one server format formatter tied to the web's list, read a TMDB-id,
  series or title add back through the duplicate check, and set aside conversation records asked
  for before the latest stream ended. Race test on two real connections (40 nights), format,
  read-back and card tests; the chat e2e case back to the real order and the offline case adding
  by TMDB id too. Each fix reverted once and seen to fail. Gate and e2e (Chromium, Firefox) run on
  the scratchpad Postgres; WebKit on CI.
- **2026-10-19 (Batch 38, #285)** — Re-measured read-only first (import has no screen; CR43-05 and
  CR43-07 still open, CR43-07 wider than the review said). Built the harness, one fake outside
  world (httpx, httpx2 and a socket backstop, failing closed), 29 browser cases, 5 job cases, three
  unit cases for the replay and one for the flush, and the `e2e` job. One request with a fake key
  reached api.anthropic.com from the Mac before the SDK's own HTTP library was covered (disclosed
  in #285). Fixed what the suite found (first-read race on `ai_settings`, concurrent queue flush,
  Safari's chunk wording). Green on CI on all three browsers after eight runs of fixing browser
  differences; WebKit cannot run locally. Guards proved by reverting seven fixes.
- **2026-10-18 (X12c live steps)** — At Craig's word: Brave results pruned (dry run 9,456 of 15,516, applied with `--expect 9456`, 6,060 left, every `done` lookup keeps its accepted page) and the completion-set refresh run (dry run, then live: 22 created, 14 updated, 4 unchanged, 22 removed, 0 errors).
- **2026-10-18 (X12c, #284)** — Re-measured read-only (9,456 of 15,516 Brave results qualify; no TMDB
  field is 150 days old; 40 completion sets last refreshed 8 Sep). Built TMDB logo and notice,
  JustWatch credit, results pruning at settle plus a one-off script, the 150-day refresh, top-ten
  billing and shorts filter, and the tidying. One expectation changed (a spec test now keeps the
  accepted page only). TMDB's logo downloaded at Craig's word.
- **2026-10-18 (X12b, #283)** — Ran R6's walker against the current build and a seeded throwaway
  database, before and after. 12 px floor and guard test, `.list-link`, whole-row activity link,
  gzip, `LIST_COLUMNS`, the Archive's two-step load (4 tests). One expectation changed
  (`MobileTabBar` 11 px to 12 px). Gate green bar the two known pgserver stale-edit tests.
- **2026-10-18 (X12a, #282)** — Re-measured first (live copies 1,923; the films count and agent
  summaries already fixed), split X12 in three at Craig's word, built X12a: Home's labels and
  `downloadCopies`, `formatDate` family and a guard test, `placeLabel`, film-sourced movie-night
  face and a stored match (061), Tell Craig (062). Tests: 8 web files extended, 6 API. Two
  expectations changed because a response gained a field (reported in #282).
- **2026-10-18 (X11, #281)** — Re-measured read-only first: 1 of 10 wants has a limit; the
  nightly run 26-29 minutes every night since 3 Oct; no shop refused every request, so the
  weekly criterion became "half its requests, seven scheduled checks running", at Craig's word.
  Built: shop prices on the Wanted card, alerts under the stored usual with no limit, the
  counter and the weekly skip. Tests: 8 alert cases, 6 refusal cases, 3 API, 2 web. Gate green
  bar the two known pgserver stale-edit tests; checked at 375 px.
- **2026-10-18 (X10, #280)** — Re-measured read-only before code, then slimmed at Craig's word:
  title rules still 7 of 8 apart; 0 of 5 splits left; 1 owned film unidentified; 0 shared
  barcodes; 12 leftover rows. Built the title-key module (T9's fold moved unchanged; `WORDS` and
  `TITLE`), moved every site onto it, and guarded it with a 21-pair table run through each site.
  Diff over 1,939 live films: 0 identification moves, 0 index changes, 3 new Search lookalike
  pairs (none an owned unidentified film), *Alien³* no longer matched to *Alien*'s reviews. The
  add form's duplicate check names an unidentified twin and a barcode's copy; the add refuses an
  unconfirmed barcode clash. Merged `f8de7ab`, production verified. At Craig's word,
  `remove_leftover_films --apply --expect 12` trashed the 12 (item 34): 1,939 → 1,927 live films.
  Gate green bar the two known stale-edit tests on pgserver; checked at 375 px.
- **2026-10-18 (Y6, #279)** — Craig chose option A, widened, over settling a doubt when its
  copy is binned. `showing_doubt()` in `services/identify/doubts.py` is the one predicate for
  Identify films' list, overview and the daily check, the Archive's filter, count and flag, and
  the film page. The overview and daily check count films; `/identify/doubts` adds `films`.
  Gate green bar the two known stale-edit tests on pgserver; browser-checked at 375px.

- **2026-10-17 (#278, the 378 doubts)** — Settled from one plan Craig agreed, with Mark's
  word: 370 kept, 6 corrected, 1 copy moved (French Connection), 1 copy binned (Ghostbusters
  2's old 4K). `src.scripts.settle_doubts` applies it through the app's own actions, audited as
  Craig; the dry run on live data checked all 378 with none skipped and no merge needed.

- **2026-10-17 (item 33, Y5's keyword backfill)** — At Craig's word, on the Mac, after Y5
  merged (`99cee5e`, production on it with `db: ok`). Dry run: 1,905 rows, 225 noir (1930s 7,
  1940s 115, 1950s 98, 1960s 4, *Dead Again* 1991), 24 with no keywords, 0 missing. `--apply`
  wrote 1,904 in about 30 minutes (one row at a time to Neon); one TMDB miss was written by a
  second run. Read-only check after: 0 unfilled, 225 noir, all with a live copy.

- **2026-10-17 (Y5, #277)** — Mark's 16 Oct points, approved by Craig 16 Oct. Series on the add
  form (`series`, `tmdbTvId`) and for "Move only this copy" (`seriesCandidates`, `mediaType`),
  made or found by `tmdb_tv_id` as Y3 identifies one, from one shared module
  (`services/film_rows.py`); the series search reads two pages. A doubt's move opens searched on
  its `searchHint`; Identify films' doubt card moves to a series too. Film Noir: migration 059,
  `movies.tmdb_keyword_ids` (null = not fetched), GIN-indexed and granted to both roles;
  `keywordId` on `GET /movies` and saved collections; `src.scripts.fill_keywords` is the
  backfill, not yet run. Add by title: a fourth film reference, set aside `not_film` by whoever
  added it. Found on the way: the add form's overviews were never clamped (`block` overrode
  `line-clamp`). Tests: nine Postgres tests in `test_y5_series_noir_title.py` and twelve unit
  tests, run here against a throwaway pgserver too; web and shared tests for each part. Two
  stale-edit tests in `test_collection_write_api.py` fail against pgserver on `main` as well,
  and pass in CI.

- **2026-10-16 (Y4, #276)** — Mark settles identification doubts from the film page, at Craig's
  word after item 32 raised 384. Keep, move one copy and the move's TMDB search take either
  person; the rest of Identify stays Craig's. The Archive's "In doubt (N)" filter and an "In
  doubt" flag find them; the film page lists every open doubt with its copy, T9's proposal and
  the three actions. A keep is now listed under Recently identified and undone there, and every
  row says who. Two earlier web assertions changed with the decision: Mark now sees "This copy
  is another film" on a copy card, and no longer "Craig will settle which film this is".
  Tests: five Postgres tests in `test_mark_settles_doubts.py`, run here against a throwaway
  pgserver as well as in CI; web and shared tests for the filter, flag, panel and kept row.
- **2026-10-16 (owner action 32, X9's live re-check)** — On Craig's Mac at his go. The sheet is
  the 18 Sep refresh's `… 02.02.26 (1).xlsx` (1,880 rows; rows 550, 614, 878 and 1831 checked;
  the 20 Sep "corrected" copy differs only in rows 302 and 816). The morning dry run re-checked
  1,508 copies (401 disagreements) and missed 2 of the 30: Holy Grail and House on the River
  exactly match an obscure film's title, and T9 never counts a grouping against a film. Mark
  then identified 25 films (13:34–15:23 UTC), fixing 14 of the 30 and both misses, so the run
  was repeated. The first repeat lost 508 lookups when the Mac slept with its lid shut (a failed
  lookup reads as "nothing" and raises no doubt) and was discarded. **The clean run (18:10 UTC):
  1,486 copies, 8,759 TMDB calls; 1,102 agree, 5 different, 3 series, 3 not offered, 373
  unsure, 0 nothing; 52 without a sheet row, 0 on another grouping; 0 of the 30 missed.** The
  apply raised 384 doubts (0 kept before, 0 changed). King Kong [1976] stays outside the
  re-check, because its film was identified on 15 Oct; it and Ghostbusters 2 each have a
  duplicate copy from Mark's adds.
- **2026-10-16 (X9, #275, [#79](https://github.com/CraigR973/mcu-app/pull/79))** — Catalogue
  truth, built in a cloud session at Craig's go. The identify run survives a TMDB failure, and
  all five run loops have failure-injection tests. The refresh, Correct match and Identify's
  search use T9's identifier, and a CI guard keeps `MatchingEngine` out of `src`.
  `identify_doubts` (057) holds "this film may be the wrong one": the spec and review jobs raise
  doubts, the Identify page lists them, and the film page says so. Keep, re-identify (undo
  reopens) or move one copy (undoable). `edition_source` (058) shows inferred editions as
  "Probably …" until confirmed, and release names use T9's rule too. `recheck_identifications`
  is the Mac's dry run and apply (item 32). Local gate: API 2,148 passed, none skipped; shared
  146; web 602.
- **2026-10-15 (owner action 31, Y3 live series pass)** — On Craig's Mac at his go: 45 still
  to identify; The Kennedys moved to manual review, leaving 34 in the apply plan and 11 for
  Mark. Apply identified 33, left Shetland Series 5 waiting because Series 1–4 already holds
  the same TMDB series ID, and failed on 0. The first real TMDB series details parsed and
  committed. The read-only film scan checked 1,852, found 9 suspects, and had 0 TMDB failures.
  Reports and full apply log are under `~/mcu-series/`; Mark's choices remain open.
- **2026-10-15 (Y3 follow-up, #274)** — The series pass: `identify_series` proposes a TMDB series
  for each title still to identify where TMDB leaves no doubt (dry run, report), and `--apply`
  identifies exactly that plan, audited `auto`, undoable, never merging. The "still to identify"
  rule moved to `services/identify/waiting.py`. Gate: API 2,109 passed with Postgres. Craig runs it
  at the Mac (item 31): this session reaches neither TMDB nor the database.
- **2026-10-15 (close-out, `ef62257`, #75)** — Y3 and #272's fixes merged; CI green on `main`.
  This session's network policy refused the production hosts, so Craig read them: `/api/v1/health`
  `ef62257`, `/health/ready` `db: ok` with every field `configured`, `version.json` `ef62257`. Y3
  struck in `docs/phase-batches.md`; Group Y has no §17 row. Open: the first live series
  identification (TMDB's real answer), Mark's series, and item 31's read-only check.
- **2026-10-15 (Y3, Mark's TV series, #273)** — A title is identified as a TMDB series from its
  page: `tmdb_tv_id` (migration 056) beside `tmdb_id`, never in it; the panel lists series beside
  films; a film corrected to a series and back; merge and undo as a film's; streaming from TMDB's
  series providers; the 34 set aside listed again. `find_series_as_films` reports series matched
  as films, read-only, over a session or HTTPS. Browser check at Pixel 7 against a stand-in TMDB:
  Broadchurch identified from "Still to identify", Band of Brothers corrected from the film to the
  series, both cards "TV series". Gate: API 2,101 passed with Postgres, web 592, shared 143;
  migrations up, down to base and up.
- **2026-10-15 (Mark's feedback, `37a5efc`, `7e0379a`, #272)** — The Identify badge, the list
  row's "Needs identification" and the film page's "Which film is this?" now follow #271's
  filter: `setAsideAs` on list items and film pages, and a set-aside series reads "TV series".
  The Archive's open Filters panel below 1280px is a history entry ending in "Show N films",
  checked in Chromium at Pixel 7 size against a seeded throwaway database (the grid measured
  0px before). TV series identification proposed as `OWNER-ACTIONS.md` item 31. Gate: API
  2,085 passed with Postgres, web 588, shared 142.
- **2026-10-14 (Mark's feedback, `f5f63e2`, #71, #270)** — The Lounge's sides: a Side picker
  in the copy form, Move discs and the Archive filter, stored in `shelf`; migration 055 filled
  in 164 live and 160 trashed copies from their text. #266's rule no longer drops detail typed
  beside a section; it is kept after it. The add form's TMDB search shows 20 results and reads
  a trailing year (the 1974 Texas Chain Saw Massacre was 14th). Nope and Us wait for Mark.

- **2026-10-14 (X5, `19c9aad`, #69, #269)** — Watch history: the feed attaches by TMDB id and
  a film not owned gets a row with no copies, kept out of every collection count
  (`owned_film`); a known year more than one apart excludes a title match; the diary import
  no longer identifies; a weekly sync in the 08:00 job; the tab says the feed holds 50 entries.
  Migration 054, live. Dry runs (read-only): backfill 651 watches and 105 doubtful; the 15, 7
  to move and 8 doubtful. The applies and Mark's username wait for Craig's word. Sitting 3 done
  in code.
- **2026-10-14 (X4, `87a734b`, #67, #268)** — At Craig's word ("option 2") a session made the
  backup role `mcu_backup` (generated password, never shown), the `BACKUP_DATABASE_URL` secret
  and an age key pair (private half in `~/.mcu-secrets`; a copy off the Mac is Craig's). X4: a
  weekly GitHub Actions copy of every table but credentials, encrypted, kept 90 days, newest 8;
  a monthly drill restores it into a throwaway Postgres and compares rows. Migration 053, live:
  the role reads 48 of 56 tables whole and two without their credential column. First run by
  hand: 49 tables, 99,822 rows, 26 MB, drill passed; decrypted on the Mac. Runbook
  `docs/restore-runbook.md`.
- **2026-10-14 (X6, `51c81ff`, #65, #267)** — Group X sitting 3 began. X6 values each disc as a
  used copy (#256): used listings' median with three or more, else New's median times a factor
  measured per format from the stored values (0.60 until 20 films), re-applied at each run's
  end. Migration 052, live; all 1,454 stored values are due, re-priced by the 15 and 16 Oct runs.
  The shared matcher now refuses another film's word before the title, Staffel and mini-series,
  "Not 4K UHD", and reads "Steelbooks" as collector; R5's crafted wrong products never price a
  film. Gate green locally and in CI; production at `51c81ff` with `db: ok`; checked at 375 px
  against a seeded local API. The group stopped at X4's checkpoint: Craig's credential steps.
- **2026-10-13 (copy fix, `2ef3b8a`, #266)** — Mark's feedback on Y1, both on 12 Angry Men.
  (a) A shelf-only edit kept "Front 3rd shelf" over Front · 4th; the form now clears the text
  for a new shelf, and the API recomposes text naming a different place (1 of 1,885 live discs
  affected, re-saving it corrects it). (b) No delete was recorded: Y1's confirmation pushed
  "Yes" off a phone and left Save in its place; the question now stands alone with Yes and
  Keep it. CI green first time (pytest 1,981, none skipped); production and the web report
  `2ef3b8a`.
- **2026-10-13 (Y2 shipped, `e0b5bad`, #265; Group Y done)** — Move discs: find each disc by
  search or scan (W3's finder, now shared with Loans), collect them in a tray on the phone,
  move them all to one place in one request, and move them back. `POST /collection/move`
  answers per disc (moved, unchanged, stale, not found) and audits each move. Online only.
  CI green first time (pytest 1,979, none skipped); production and the web report `e0b5bad`.
- **2026-10-13 (Y1 shipped, `4840711`, #264)** — Mark's request: he adds discs (#155) but could
  not correct or move them. `PUT` and `DELETE /collection/{id}` take either person now, the
  film page shows him the copy tools, and Move to trash asks first because only Craig can
  restore. Photos, the eBay tools, the item history and the Trash stay Craig's. Y2, moving
  several copies at once, is written up and not built. CI green first time; production and
  the web report `4840711`.
- **2026-10-13 (X8 shipped, `e991281`, #263; sitting 2 done)** — The worker caches the
  cross-origin API at last (it never had in production), and sign-out clears it. Failure screens
  say "No signal", "The archive had a problem" or "needs the newest version" with Reload; a
  missing chunk reloads once; a crash's 500 carries CORS. Readiness adds TMDB and Brave; the
  close-out gate now also checks every readiness field and the web's `/version.json`. A CI
  contract test holds every `api.ts` parse to the API's OpenAPI (158 bounds moved onto the
  API). The CSP names the one API host. Production: API and web at `92273e3`, all configured.
- **2026-10-13 (X7 shipped, `aa6946d`, #261, #262)** — The assistant answers follow-ups: stored
  answers keep only the API's request fields. Writes go straight to a Yes/No card naming the
  exact film and date; a shared title asks; typing while a card waits declines it, and the box
  locks meanwhile. Results are compact, totals first, 25 a page. Failed calls leave a usage row
  and the daily check names them; the person reads "Craig has been told". Caps hold before
  every call under a per-person lock (200 messages, $10, zero refused). Production at `4b38214`,
  `db: ok`. A live follow-up is Craig's (`OWNER-ACTIONS.md` 2). New: `.claude/api-local.sh`
  runs the API on a throwaway Postgres for browser checks.
- **2026-10-12 (X3 shipped, `adcae0d`, #260; sitting 1 done)** — A device the push service
  refuses is kept as refused, and the app registers the phone again on its next open; Settings
  says "on" only when the server holds the phone live, otherwise when it stopped; a banner stays
  while a person's last device is refused; the eBay run counts pushes delivered. Migration 051.
  Production reported the merge SHA at 23:06 UTC with `db: ok`. A real phone re-subscribing is
  Craig's to see.

- **2026-10-12 (X2 shipped, `857ee8f`, #259)** — A daily check inside the 08:00 reminders job
  records every job's heartbeat, the eBay scan, each person's notifications, readiness, the
  database's size, PIN locks and identification's doubts, and tells Craig in a "Needs
  attention" row at the top of Home and one push per new problem. Every job beats each run;
  `cron-scrape` exits 0 on refusals alone; Price alerts says how many listings the last checks
  read; Deals stays in the menu; PIN locks escalate within a day. Migration 050. Production reported the merge SHA at 22:30 UTC with `db: ok`, and the API's boot heartbeat says all three readiness fields are configured.

- **2026-10-12 (X1 shipped, `7979e19`, #258)** — The eBay scan's mark is its own clock, so the
  21 Oct row stopped blinding it on the deploy; the matcher refuses another year, incomplete
  items, a Blu-ray named 4K, Region A/1 and television; a used listing meets only used listings
  and a shop price only lowers a New listing's usual; a find is re-checked before its push, and
  every deal card names its condition and when it was last seen. Migration 049. The first pass after the deploy read 2,709 listings and found 21 deals, 5 pushed. Production reported the merge SHA at 19:03 UTC with `db: ok`.

- **2026-10-12 (X6 and X4 decided, #256, #257)** — Craig's answers: owned discs are valued as
  used copies (X6, amending #209), and the weekly backup is kept as encrypted GitHub Actions
  artifacts (X4). Sitting 3 now stops only for his credential steps in X4 and his word on X5's
  live data. Docs only.

- **2026-10-12 (Group X regrouped, #254, #255)** — Craig's answers the same evening: X4 joins
  the late-October sitting as X6 → X4 → X5, so Group X runs in five sittings, not six; sitting
  1 runs as one group; eBay's API licence (MK47-04) is an accepted risk, so X1's close-out does
  not stop to ask. Docs only.

- **2026-10-12 (wave 1 review, Batches 43–48, synthesis)** — Six passes at `527522d` found 44
  findings (10 High); the roadmap (`docs/reviews/BATCH_43-48_ROADMAP.md`) groups them into 12 draft
  batches X1–X12 and names 20 standing guards. Re-checked 12 Oct: the eBay scan still blind (39 of 39
  runs since 9 Oct), 30 copies still the wrong film, pushes reaching both phones again after Craig's
  and Mark's re-subscribes on 11 Oct. Craig's go the same day: Group X written into the ledger (#253) and the
  review's pull request merged. X1 (the eBay scan) is next and should land before 21 Oct.

- **2026-10-05 (W1 follow-up, [#44](https://github.com/CraigR973/mcu-app/pull/44))** — Craig, dark theme: the top bar was still faded with
  Search open. The search sheet covers the bar while open and had kept the page's colour, so
  every tap of Search brought the faded bar back; it takes the bar's surface now. A test opens
  Search and checks it.

- **2026-10-05 (W3, [#42](https://github.com/CraigR973/mcu-app/pull/42), `3ad71eb`)** — Both people lend, borrow and mark returned. A borrow
  names the person by their profile (migration 048, `loans.borrower_profile_id`, 0 rows to
  backfill); overdue reminders go to both, the borrower reading "You've had it". Loans' "Lend or
  borrow" finds a disc by search or barcode, then lists the film's discs. Gate and CI green, CI
  running the six new database tests for the first time; production reported the merge SHA at
  16:53 UTC with `db: ok`. **Group W is done**; Craig's are the iPhone checks and a real scan
  (`OWNER-ACTIONS.md` 30).

- **2026-10-05 (W2, [#39](https://github.com/CraigR973/mcu-app/pull/39), `0a87625`)** — Home is a page of rows that scroll sideways, the collection
  first (numbers, then charts), then disc releases, the four highlight rows, memories, Completion
  (fewest missing first, "All 40" to `/insights`) and Recent activity as a list. Gone from Home:
  Most watched, its own Add a disc, and the bid trial with "Update values", now Admin's Collection
  value. Found and fixed: tapping a completion set showed the whole list. Gate and CI green;
  production reported the merge SHA at 16:41 UTC with `db: ok`.

- **2026-10-05 (W1, [#38](https://github.com/CraigR973/mcu-app/pull/38), `9dd6805`)** — Search opens with the keyboard up: the sheet is built
  and its box focused inside the tap, which is what iOS asks before it shows a keyboard. The
  top bar is a raised panel, the bottom bar's surface and shadow, its icons at full strength;
  V1's fix had been invisible because nothing scrolls under the top bar. Browser check at 375
  and 1,280 px, light and dark, with Home's data read from production read-only (#250). Gate
  and CI green; production reported the merge SHA with `db: ok` at 15:08 UTC, 25 minutes late
  because Railway's GitHub builds were queuing (its incident). cron-scrape's deployment failed
  at Railway's image push; the previous one, same API code, stays live until the next merge.
  Craig's: the two iPhone checks (`OWNER-ACTIONS.md` 30).

- **2026-10-05 (the 5 Oct snags, reconciled and planned)** — Craig raised seven snags: search
  needs a second tap for the keyboard, Craig borrowing and lending from Loans with the scanner,
  Home as carousels with the collection first, Most watched repeated in Highlights, the top bar
  still faded, Home's Add a disc, and the bid trial on Home. Each was checked against the code,
  the live database (read-only) and a 375 px render (`docs/owner-snags-2026-10-05.md`). Two
  findings mattered most: the search box is focused a frame after the tap, which iOS does not
  honour with a keyboard; and V1's top-bar fix could not change the bar's look, since nothing
  scrolls under it. His answers the same day (#249): both lend and borrow, the collection
  first, the trial to Admin, go. Group W written into the ledger.

- **2026-10-04 (housekeeping)** — At Craig's word ("yes do 1 -4 now"), four tidy-ups:
  STATUS's Now back to the current state (it had grown to about 200 lines of dated entries;
  they are at `git show e23d716:STATUS.md`) and Next to the live sequence; reconciliation rows
  34 (chat cost tracking, shipped in Batch 30) and 48 (rate limiting) brought up to date; 38
  redundant asyncio marks removed from the API tests, local warnings 152 → 0; and a sixth CI
  job that builds and boots the image Railway deploys (#248). The gate docs no longer tell an
  agent to export the Mac's `DATABASE_URL`, which is production's.

- **2026-10-04 (28 left for now)** — Craig asked what the fixed outbound address was for, and
  left it at that (#247): Railway's static addresses need Pro and may be shared, and Railway
  offers no dedicated one. 22c parked with it; 21 still 2 of 3 by the 4 Oct count.

- **2026-10-04 (T8b, [#33](https://github.com/CraigR973/mcu-app/pull/33), `2995b26`)** — Merged at Craig's OK ("yes to 1 and 3") and live at
  10:28 UTC with migration 047; CI green first time, the 10 database tests run; production
  checked as in the Now block. The first live sign-in is his (`OWNER-ACTIONS.md` 29).

- **2026-10-04 (T8b built, not merged)** — Connect eBay, each person their own (#245): the
  sign-in with a single-use, ten-minute state tied to the person; two sealed tokens per
  person; Your eBay's watch, saved-search and selling lists read live; alerts from them via
  T8a; `/privacy`; both eBay variables declared with `preserve()`. A session hit its spend
  limit mid-gate on 4 Oct and this one finished it. The browser check and review found five
  faults, all fixed; the saved-search picker now looks on Wanted too (#246). Merge waits for
  Craig's OK (`OWNER-ACTIONS.md` 29). A `cd` printed the Neon password into the transcript
  (22).

- **2026-10-04 (V9's first night)** — `cron-specs` ran the reviews batch 02:01–02:16 UTC
  after a spec batch with nothing due: 20 Brave searches, 16 reviews found (Blu-ray.com 10,
  AVForums 6), 150 Blu-ray.com requests five seconds apart, 81 reviews scored (Bad
  Lieutenant, Cross of Iron, Don't Look Now and The Third Man among the 5.0s), 3 with none,
  1 another year's film (Dead Man's Shoes, catalogued as the 1940 film). No halt. 651 owned
  films and formats wait, about five more nights. The spec backfill had nothing left to search:
  728 of 1,250 Blu-ray and 4K discs have specs, and 522 wait for Craig on Disc specs.

- **2026-10-03 (V9, [#30](https://github.com/CraigR973/mcu-app/pull/30), `d1c3bf7`)** — Reviews, found with Brave, on Wanted items and
  film pages; Blu-ray.com's scores read within #110 as #228 widened it, owned films' by
  following their spec page's link to the reviewed edition; AVForums links only (#241); Home's
  "Best reviewed". Browser check at 375 px, light and dark; it found Brave's line unclamped,
  fixed before the merge. CI's first run on 3 Oct failed two V9 tests on their own setup (a
  halt with no time; a film read after a rollback) and two eBay tests on the expired
  recording, fixed separately (#242). Gate and CI green (1,801 API tests, warnings unchanged at
  178; web 475, shared 127); production reported the merge SHA at 22:47 UTC with `db: ok`.

- **2026-10-03 (item 18 done; an expired eBay recording)** — Craig set eBay's sign-in page and
  both variables for T8b (`OWNER-ACTIONS.md` 18). They were checked by name and shape, with no
  value printed, and production stayed healthy. The recorded listing behind two eBay alert
  tests ended at 09:06 UTC and failed them everywhere. `0770bbc`
  ([#27](https://github.com/CraigR973/mcu-app/pull/27)) pins those routes' clock to the
  capture's time (#242). CI: 1,750 passed, none skipped. Live 13:18 UTC with `db: ok`. Craig
  chose to start T8b after V9 (#243).
- **2026-10-03 (20b's second half read back, and V9's capture)** — The 3 Oct shop check ran
  under 20b's second half (`abc17d6`), 03:03–03:31 UTC: 27 refused requests waited the 60
  seconds asked and 2 got through (Powerhouse's Romper Stomper, Second Sight's Bad Lieutenant);
  25 were refused again (101 Films 9 of 9, Powerhouse 8, Second Sight 8). Every refusal `429`,
  `retry-after 60`, Cloudflare, "Too many requests", no `cf-mitigated`, from each Shopify shop's
  first request. A minute's wait does no better than two seconds did (4 of 29 on 2 Oct), so the
  remaining option, a fixed outbound address, is Craig's (`OWNER-ACTIONS.md` 28). V9's capture:
  AVForums' terms (§3.6) and `robots.txt` forbid automated access and it challenges the app's
  client, so links only (Craig's word); Blu-ray.com's review lives on one edition's page, and
  owned films follow the spec page's link to it (Craig's word, #241).

- **2026-10-02 (20b, second half, [#25](https://github.com/CraigR973/mcu-app/pull/25), `abc17d6`)** —
  At Craig's "20b now, merge by 02:45" (#240), from one night's evidence: a refused request
  waits for `Retry-After` (bounded at 90 s) before its one retry, the sale-page check too;
  `scrape_runs.refusals` (migration 045) records each refusal's wait and whether the retry got
  through; the nightly run holds no transaction through a wait; "Run now" keeps 2 s. Gate and
  CI green first time (1,750 API tests, warnings unchanged at 178; web 464, shared 123);
  production reported the merge SHA at 23:51 UTC with `db: ok`, at migration 045.

- **2026-10-02 (Craig's "yes keep", and the next Mac session)** — Craig kept V8's like-for-like
  rule for shop prices (#239) and asked for a prompt to do 20b and the Blu-ray.com/AVForums work
  on his Mac: `docs/next-mac-session.md` (the shop checks since 2 Oct, 20b's second half, then
  V9; top tier at `max`). The cloud session's scheduled read-back of 3 Oct's check was cancelled
  so two sessions do not edit 20b's section at once; the Mac session reads it back first.

- **2026-10-02 (V8, [#22](https://github.com/CraigR973/mcu-app/pull/22), `37e7c0a`)** — An eBay
  find's "usually" is the average of eBay's asking price and each shop's latest like-for-like
  price from the nightly check's last week (same format, standard edition; #239), eBay's alone
  where no shop has one; the 70% rule compares with it, and its parts are stored
  (`deals.usual_sources`, migration 044). The card says "with postage · usually £U" over
  "eBay £A before postage · Zavvi £B"; "Sold on eBay" and the film page's "Sold listings on
  eBay" open eBay's sold listings. Browser check at 375 px, light and dark, against the real
  API on the throwaway test database. Gate and CI green first time (1,724 API tests; web 463,
  shared 123); production reported the merge SHA at 03:36 UTC with `db: ok`, at migration 044.

- **2026-10-02 (the first shop check under 20b's first half)** — 03:04 UTC: no shop switched
  off. 101 Films and Powerhouse each got a price and went back to 0 failures; Second Sight was
  `blocked`, its count held at 1. 25 of 42 refused, every one `429` with `retry-after 60`,
  `server cloudflare` and the title "Too many requests", no `cf-mitigated`: a rate limit asking
  for a minute, not a block. Each Shopify shop refused its first request of the night, so the
  limit is filled by something other than this run (most likely Railway's shared address);
  4 of 29 retries two seconds later got through. Suggests the second half honours
  `Retry-After` before its one retry (evidence in 20b's section). 21 still 2 of 3.

- **2026-10-01 (20b's first half, [#19](https://github.com/CraigR973/mcu-app/pull/19), `548160f`)** —
  At Craig's "2) yes": a `429` is a refusal, never a step towards auto-disable (#238). The
  fetcher raises a refusal carrying `Retry-After`, `cf-mitigated`, `server` and the page's title;
  the runner logs each refused request, records a shop that only refused as `blocked` (Batch 16's
  status, no migration) with its count untouched, and a genuine failure beside refusals still
  counts. Gate and CI green first time (1,719 API tests, warnings unchanged at 178); production
  reported the merge SHA at 19:26 UTC with `db: ok`. **And "1) neither":** V7 shelved, values stay
  on asking prices, V8 next on them (#237).

- **2026-10-01 (the cloud setup checked, and the checks that waited for the database)** —
  `OWNER-ACTIONS.md` 27 is done: from a cloud session, `live_sql` answers as `mcu_readonly`,
  read-only, 1,888 films; the six credential columns are unreadable (proved from the
  privilege catalogue: the session's own safety check refused a `SELECT pin_hash`, rightly);
  Railway 5.63.1, `config plan` at its resting `0 to add, 1 to change, 0 to destroy`. **V5's
  open check is closed:** production's plans ran at 3.5, 0.8, 2.9 and 10.3 ms with the scratch
  run's shapes. **The 1 Oct shop check was worse than 30 Sep's:** 29 of 42 refused with `429`,
  every Shopify shop from its first request, so pacing is unlikely to be the cure; 101 Films
  and Powerhouse are one refused night from auto-disable (diagnosis in 20b's section). **21's
  condition:** 8 scheduled days, but 2 of 3 wants. **Craig ran the bid trial at 14:14 UTC:** no
  film has a bid price (13 auctions with bids across 100 films, at most 2 on one), so a blend
  equals asking prices. The pick, and the go on 20b, are Craig's.

- **2026-10-01 (cloud sessions, #236)** — At Craig's "yes to all": a startup hook readies the
  gate in every cloud session (venv, pnpm, Postgres 16 with `mcu_test` at head, Railway CLI
  5.63.1); `src.scripts.live_sql` reads the live database over Neon's HTTPS endpoint with a
  read-only role; `docs/mac-cloud-setup.md` is the one-off Mac session that makes the role
  and tests a Railway token (`OWNER-ACTIONS.md` 27). From the cloud, Neon's endpoint and
  Railway's API both answered made-up credentials, so only the real ones are missing.

- **2026-10-01 (V6, [#14](https://github.com/CraigR973/mcu-app/pull/14), `153d45b`)** — "Try
  bid prices" on Home (#228, "trial first"): admin only, up to 100 priced films a third per
  format, one Buy It Now and auctions search each, out of the day's valuation share through a
  `valuation_runs` row with trigger `trial` (migration 043). An auction counts with a bid and
  past the valuation's own matcher; the report, kept on the run row, compares bids with the
  same search's asking prices and totals stored, asking, bids and blend (#235). It saves no
  prices; no live eBay request was made building it. Gate and CI green first time; production
  reported the merge SHA at 00:39 UTC with `db: ok`. The overnight run stopped here, as
  written.

- **2026-10-01 (V5, [#12](https://github.com/CraigR973/mcu-app/pull/12), `f1b497c`)** —
  Highlights on Home (#228, "a mix of all"): top rated on the shelf at 4½ or 5 with whose rating
  (the caption says Mark has rated none, from the data, #159), most rewatched across both
  diaries, most valuable discs at their stored value through the total's own
  `owned_valued_discs()`. One request, `GET /highlights`; its plans read at production's counts
  on a scratch database, 22 ms for the endpoint, so no cache (#234). Gate and CI green first
  time; production reported the merge SHA at 00:04 UTC with `db: ok`.

- **2026-09-30 (V4, [#10](https://github.com/CraigR973/mcu-app/pull/10), `f7a66f8`)** —
  "Craig's house" is a section (#228): in `SECTIONS`, the parser ("Craigs house" and an iPhone's
  curly apostrophe too) and the CHECK, through migration 042, which escapes the apostrophe 007's
  pasting would have broken on, writes no rows, and reverses by clearing `section` first. Its
  downgrade was proved against a real row in a rolled-back transaction (#233). The copy form
  offers every section (`allSections` on the facets); the filter lists only places with a disc.
  The assistant's browse tool names every section. Gate and CI green first time; production
  reported the merge SHA at 23:38 UTC with `db: ok`.

- **2026-09-30 (V3, [#8](https://github.com/CraigR973/mcu-app/pull/8), `0b29e58`)** — Movie
  night on one screen. The shortlist is the whole night: one Add / Added control per film (Added
  takes the vote back as a vote of `false`, #232), details in the row, the swipe deck, its
  gestures, arrow keys and "N of M" count removed (#228), "Start movie night" for "Start
  swiping". The push that sends a night says "N films on the shortlist". Three deck tests
  removed with the deck, named in the ledger. Two-person match on the rig: announced once to
  both, 2 pushes queued. Gate and CI green first time; production reported the merge SHA at
  23:13 UTC with `db: ok`. The two-phone check is Craig's (16b).

- **2026-09-30 (V1, [#6](https://github.com/CraigR973/mcu-app/pull/6), `13791c2`)** — The top
  bar's background and every tint, back arrows, Loans always listed. The five opacity steps the
  redesign's classes named (12, 14, 88, 94, 96) joined the Tailwind theme; a test reads every
  colour class in `apps/web/src` and fails on a step the theme lacks (it lists exactly the 20
  without the fix). On a phone only the four tabs and You are top-level; the film page's Back
  goes back through history; Loans no longer hides while empty (#228). Browser check against
  the real API on a local Postgres (#231). Gate and CI green first time; production reported
  the merge SHA at 22:48 UTC with `db: ok`.

- **2026-09-30 (`urllib3` 2.8.0, [#4](https://github.com/CraigR973/mcu-app/pull/4),
  `037d4e8`)** — `main`'s dependency audit went red at 19:26 UTC on `8e4c6a2`: `urllib3` 2.7.0,
  three CVEs, fixed in 2.8.0. Fixed on its own `fix/` branch, the first change to land through a
  pull request from a cloud session (#230). Only `urllib3` moved in either lock. Locally:
  `pip-audit` clean, the pnpm audit under its threshold, 1,634 API tests against a local
  Postgres 16, web and shared green. CI green on the push and pull-request runs. Production's
  `commitSha` not confirmed from the session (the Railway host is blocked); Craig to check.

- **2026-09-30 (Craig's nine snags reconciled; Group V planned)** — No code. Checked against
  `8e4c6a2` in `docs/owner-snags-2026-09-30.md`; his answers are #228 and the plan's shape #229
  (six sittings, V2 merged into V1 and V10 into V9, his steps inside the batches, a model tier
  and effort per batch), and his go on an overnight run, a pull request per batch, #230. One
  bug found: the top bar has had no background since 10 Sep (`bg-background/94` is not a
  Tailwind 3 step; 20 classes share the fault), V1's fix. Also found: `main` red on the
  `urllib3` audit. A cloud session ran the whole gate, the API suite against a local
  Postgres 16 (1,634 passed, none skipped). Pushed to `claude/collection-valuation-ui-ix0oww`,
  not `main`.

- **2026-09-30 (Craig's answers on 22b)** — §5.9 not met with two shops; 22c (every page of a
  sale) and 20b (shops answering `429`) written with criteria, waiting for his go; Bad
  Lieutenant (1992) and Dog Soldiers (2002), both 4K, added to Wanted through the app's own
  route for Batch 21 (no price limit); owner item 18's eBay values fixed (#227).

- **2026-09-30 (Batch 22b shipped, `eb51568`)** — Zavvi reads its "2 for £30 4K" listing, at
  Craig's pick (its flash-deals page had become six discs, five owned); Second Sight reads its
  sale collection's compare-at price; "Check sale pages" and then "Save deals" on /retailers
  (#224). Three Batch 22 faults fixed: the same-site guard, single-price cards kept as deals,
  and the film matcher's shop words and years (#225); #153's premise corrected (#226). Five
  read-only page fetches, all `200`. Local gate and CI green (5 of 5 after the PyJWT fix).
  Production serves `eb51568` with `db: ok`; the retailer rows carry the new configuration
  (apply-built-ins at 13:44 UTC, three values changed, nothing set by hand). Browser check at
  375 and 1,280 px from a captured real dry run (pane hidden, so measured, not screenshotted).
  The live check and save are Craig's (1e).

- **2026-09-30 (PyJWT 2.13.0 → 2.15.1, `6a8197b`)** — Ten advisories published after 28 Sep
  turned the CI dependency audit red on every branch, `main` included. Fixed on its own `fix/`
  branch and closed out ahead of 22b: CI green, production serves `6a8197b` with `db: ok`, and
  answers `401` to forged and malformed tokens. Only PyJWT moved in either lock.

- **2026-09-30 (Batch 21 did not start)** — Its scheduled session (08:00 UTC) found the seven
  scheduled scrapes in, but only 2 wanted items priced by more than one shop, against the 3 its
  criterion needs; it built nothing and asked Craig. It also found the 03:00 UTC shop check
  mostly refused: 21 of 33 checks answered `429` (Second Sight, 101 Films, Powerhouse).

- **2026-09-28 (Batch U4 shipped and applied, `3974733`)** — At Craig's word ("merge and run
  those commands"): merged after CI green (1,595 API tests); production serves `3974733` with
  `db: ok`. The agent wrote the Railway plan to a pinned file and read it (1 to add, the known
  `api` restart-policy change, 0 to destroy), then applied exactly that plan at 21:23 UTC;
  `cron-values` exists and built from `main`. A one-off scheduled session starts 21 at 09:00
  BST on 30 Sep.

- **2026-09-28 (Batch U4 built, not merged)** — `cron-values` re-prices the collection at 04:00
  UTC on the 1st, 2nd, 15th and 16th, the Home button's run on a schedule, with the eBay keys by
  reference (#223). Two mornings a fortnight because a day's share prices about half the
  collection. The merge waits for Craig's OK; his config apply starts it.

- **2026-09-28 (Craig's answers on Group U; the first scheduled spec batches)** — U4 yes,
  re-pricing every fortnight; 21 go, starting itself after the 30 Sep scrape; item 14 closed;
  the 36 photographic brand images kept (#222). The first scheduled spec batch (27 Sep, 02:02
  UTC) ran clean: 148 searched, 91 given specs, 15 editions filled, no page had moved. The
  second (28 Sep) stopped after 14 discs: Brave answered `402` once this month's searches
  reached 1,005, past its ~1,000 free. Batches wait for the credit to renew, or a higher
  spending limit (Craig's call, optional). 530 discs have specs, 385 wait, 335 unsearched.

- **2026-09-26 (Batch U3 shipped, `e116ef2`)** — Craig's three picks (#221): the assistant is
  a top-bar icon beside the initial and the floating button is gone; `/debug` exists in
  development builds only; the 25 third-party brand images are untracked and ignored, still on
  disk. Local gate and CI green first time (1,593 API tests against Postgres, 408 web).
  Production serves `e116ef2` with `db: ok`; the live web bundle has no `/debug` route or page.
  `main` was fast-forwarded without being checked out, because checking out the old `main`
  and merging would have deleted the images from disk. Browser check at 375 px: nothing on
  Settings, Price alerts, Identify films, the Archive or a film page sits under anything;
  two older faults found and fixed (switch knobs, film tab counts). Left for Craig: 36 tracked
  images built from stills, four served by the live site. The first scheduled `cron-specs`
  run (02:00 UTC, 27 Sep) had not happened yet, so there was nothing to check.

- **2026-09-26 (owner item 15 corrected)** — While writing the prompt for U3: the brand files
  are not untracked. All 195 under `docs/brand/` (56 MB), third-party stills and posters
  included, went into git on 10 Sep (`fb6ecbd`) and are on GitHub (a private repository). Item
  15 and U3's brand criterion now say so; the choice is leave them, stop tracking the images,
  or also rewrite history.

- **2026-09-26 (Craig kept "Sub-category")** — His answer on U2's one open call. Checked the
  same evening: the live web app (`mcu-app-fawn.vercel.app`) serves U2's build, with the Edition
  field and "Sub-category" in the copy form and film page, and no "Collector edition" left.

- **2026-09-26 (Batch U2 shipped, `52fcced`)** — Each copy's edition (migration 041), filled
  only where its Blu-ray.com page is certainly the copy, and shown while browsing (#220). Local
  gate and CI green first time; production serves `52fcced` with `db: ok`. The backfill wrote
  83 editions, all from pages that were the one UK edition the search found, identical to the
  dry run. "Collector edition" became "Sub-category". Browser check at 375 and 1,280 px.
  Owner item 12 is done.

- **2026-09-26 (Batch U1 shipped, `cb1111f`)** — At Craig's go on U1 → U2. A moved
  Blu-ray.com page is followed once, to the same release only (#219). Local gate and CI green
  first time; production serves `cb1111f` with `db: ok`. A batch run by hand at 14:35 UTC
  settled Dr. Strangelove's disc at its new address: 148 searches, 83 discs gained specs, 6
  sent back by the year check, no failures. 430 have specs, 323 wait for Craig, Brave 838.

- **2026-09-26 (Group U regrouped)** — At Craig's word: U1 and U2 run back to back on one go;
  the brand assets (was U5) join U3's two small calls; U4 shares a Railway apply with T8b's
  when the timing allows. Six steps instead of eight. Still waits for his go.

- **2026-09-26 (the remaining work batched)** — At Craig's request: owner items 1b and 1i marked
  done (both were finished but read as open), and everything left written up as Group U with
  its gates. Found while planning: no copy records an edition, so item 12 needs a column
  first (U2). The Blu-ray.com moved-page task became U1. Waits for Craig's go.

- **2026-09-26 (the first scheduled eBay pass)** — `cron-ebay` ran at 12:21 UTC and finished:
  15 calls of 500, 363 new UK Blu-ray and 4K listings, 13 upgrades priced, 3 deals, 3 pushes
  sent to Craig (Mark's suppressed: no subscription). No alerts are set yet.

- **2026-09-26 (Railway config applied)** — The agent ran `config plan` read-only at Craig's
  request: 2 to add (`cron-specs`, `cron-ebay`), 1 to change (the API's restart policy, unset
  to `ON_FAILURE`), 0 to destroy. The Brave key was already on `api`. Craig applied at about
  10:25 UTC; both jobs were created and built. A plan afterwards still lists the restart
  policy line alone: Railway seems to keep its default as unset. The API stayed on
  `cc0c593` with `db: ok`.

- **2026-09-26 (Batch T8a shipped, `e2142b7`)** — Craig said OK to merge and to keep Price
  alerts always in the menu. Production serves `e2142b7` with `db: ok`; migration 040 is
  applied. CI failed once, on three new database tests reading objects a refused request had
  expired, and passed after the fix. The schedule waits on Craig's config apply.

- **2026-09-26 (Batch T8a built, not merged)** — eBay price alerts and the deal scan, on
  `feat/t8a-ebay-alerts`. Probing eBay live shaped it: about 200 new UK Blu-ray and 4K listings
  every two or three hours, so the scan reads them all for a few calls a pass. The browser
  check, as Mark, found an older Deals bug (a long title widened the card past a phone's
  edge), fixed. The merge waits for Craig because it declares a Railway job (#218).

- **2026-09-26 (Batch T10 shipped, `db75229`; valuations current)** — Craig said go on the
  plan. T10 searches again, once, a queued disc whose film was identified since its search.
  Local gate and CI green first time (1,467 passed); production serves `db75229` with
  migration 039. A batch run by hand searched 5 discs again and settled 2, and gave 82 discs
  specs in all; the queue went from 197 to 257 because 143 discs were searched for the first
  time. The 92 valuations T9 made due were priced: 85 priced, 7 not. Total £23,636.80.

- **2026-09-26 (T8 split; T10 added)** — Craig chose to split T8: T8a, price alerts and the
  deal scan, first; T8b, "Connect eBay", after his eBay set-up. He also chose T10: a queued
  disc whose film was identified after its search is searched again, once. All three are in
  `docs/phase-batches.md` (#216) and wait for his go on the plan.

- **2026-09-25 (Batch T9 shipped, `4d16723`: live run and knock-ons)** — At Craig's go, main
  was merged into the branch, and the local gate and CI were green. Production serves
  `4d16723` with `db: ok` and migration 038. The live run applied the approved plan once:
  156 identified, 166 for Craig, 35 set aside, 0 left alone, 0 failed, 80 Brave searches
  recorded. In one spec batch the second look settled 9 discs of identified films, and 87
  discs gained specs; the queue went from 136 to 197. One valuation pass re-priced 41
  films and formats, and 92 remain due. The Identify films page was checked in a browser
  against the live data. No failures on the way.

- **2026-09-25 (T9 built; dry run with Craig)** — T9 is built on `feat/t9-identify-films`:
  a title reader, a matcher that uses TMDB, its alternative titles and TV index, then one
  Brave search, an audited identification whose merges carry every row and can be undone,
  and the Identify films page. CI failed twice on the page's tests, which shared one session
  across requests, and passed on the third. The first dry run made two wrong calls, both
  fixed: a 2007 film for "The Devil and Daniel Webster" (the 1941 film holds that title only
  as an alternative one) and "Munch" set aside as TV off an unrelated series. The second
  lost its plan when Neon dropped a connection held through the searches; the dry run now
  holds none. The third: 156 identify, 166 for Craig, 35 set aside, 26 Brave searches. No
  nightly spec batch has run.

- **2026-09-25 (the first valuation finished)** — Day two, at Craig's 24 Sep word: 707 eBay
  calls, 620 films and formats priced, 87 not priced, none failed, nothing left due. All
  1,457 physical discs are now checked: 1,262 priced, **£22,810.28 at current asking prices**.
  Not priced: 98 of the 319 discs of unmatched films, 97 of the 1,138 of matched ones.

- **2026-09-25 (T9 written up; checks)** — Craig's session renewed silently on 24 Sep, so
  #200's fix is proven live. The 25 Sep reminder run sent no cinema pushes (#210). The
  Brave key is still not in Railway. T9, identifying the 366 unmatched films, is defined
  in `docs/phase-batches.md` and waits for Craig's go.

- **2026-09-24 (Batch T7 shipped, `160f842`, `bfc28e7`)** — T7 merged once Craig's Brave
  key was in. Three watched batches: 314 searches, 188 pages fetched, 178 discs with
  specs, no halts. None of the 10 Sep pages was a UK edition, so none was copied. The
  year check caught 10 remakes and 2 doubtful identifications. A matcher fix ("&",
  leading articles, publisher brackets) and a second look at the queue settled 10 more.
  136 discs wait for Craig. Nightly batches wait for the key in Railway and a config
  apply (#213).

- **2026-09-24 (Batch T7 built, not merged)** — Brave search proposes each disc's
  Blu-ray.com page; one UK page for the right film and format is accepted, the rest wait
  on a new Disc specs page. Nightly batches fetch under #110's rules, and the page's year
  is checked. The 10 Sep specs were mostly US pages, so they are copied only when the
  search confirms a UK edition. Branch `feat/t7-bluray-backfill` (`829737f`), CI green.
  It waits for the Brave key. The local gate gained the shared type-check and build
  after CI caught what they miss (#212).

- **2026-09-24 (the old Supabase data)** — Garmin Coach needed the space, so the first
  version's tables in the shared Supabase project were archived to Craig's Mac and dropped
  (Gotcha 30). This app's code, data and hosting did not change.
- **2026-09-24 (fixes, and T6's first valuation)** — The scheduled jobs' first real runs:
  the shop check at 03:04 UTC and the reminders at 08:04 UTC. The reminders pushed Craig 27
  releases, 23 of them cinema dates; release pushes are now disc releases only (`59808f4`,
  #210). The first valuation ran at Craig's word: 641 of 1,457 discs priced, £11,844.31 at
  asking prices. A dropped eBay connection stopped the first of its two runs at call 574;
  such failures are now retried (`e256d65`, #211). Mark's push registration expired. No
  session renewal yet, because nobody has opened the app since the tokens lapsed.

- **2026-09-23 (Batch T6 — collection value, `9acd0ee`)** — A valuation run prices each
  owned disc at current eBay asking prices with the film page's own estimator: one search
  per film and format, three listings or "not priced", 750 calls per UTC day, re-priced
  every 30 days. Home shows the total and how many discs it rests on; each copy shows its
  stored value. Migration 036 is live. Nothing is priced yet: the first full run is
  Craig's (`OWNER-ACTIONS.md` 19). CI failed once, on strict mypy, which the documented
  local command never ran; the command is fixed (#209).

- **2026-09-23 (Batch T5 — releases, `1e08f40`)** — The calendar asks TMDB for GB releases
  by type, six months ahead. Discs aren't genre-filtered. The calendar refreshes itself
  when read and more than a day old. "Coming to disc" lists the next releases from today,
  and Home leads with five. **Live run: 28 disc releases** (18 4K, 10 Blu-ray) and 131
  cinema dates, with no errors. Migration 035 is applied. CI failed once: a background
  refresh leaked rows between tests. It was fixed and green (#208).

- **2026-09-23 (Batch T4 — movie night, `99b04c0`)** — A night opens on its shortlist,
  showing your own vote on each film. The deck says Skip and Add. "Send to Mark" puts him
  in the night and pushes a notification that opens it, and Share link uses the share
  sheet. **Found:** movie-night notifications had only ever been queued, so no match had
  ever reached a phone; they now go out at once (#207). CI was green first time.
  Production serves `99b04c0` with `db: ok`. The two-phone check is Craig's.

- **2026-09-23 (Batch T3 — navigation and the Archive row, `90d6994`)** — Phones get five
  tabs (Home, Archive, Add, Movie night, Search) with 11px labels. There's no slide-out
  menu any more: the top bar shows the page's title, a back arrow below a destination, and
  your initial, which opens a new "You" page with everything else. The Archive's controls
  are one row at every width, and runtime from/to is a filter, a chip and a
  saved-collection key. CI failed once on a Postgres-only test that pins the saved-collection
  wire shape; it was fixed and green, and production serves `90d6994` with `db: ok` (#206).

- **2026-09-23 (Batch T2 — one search, `fe409f3`)** — Owned results say when *you* last
  watched them. Films not in the collection follow them, from TMDB, with a UK streaming
  line; an owned film nothing has identified is flagged rather than hidden. There's a film
  card for strangers, with Add to Wanted and Suggest for movie night, and movie night's
  suggest box uses the same live search. Picking a result on a phone now closes the
  search sheet. Fixed on the way: the web schema rejected films with no disc (#205).
  Green first time in CI (1,209 passed, the 19 new ones against Postgres), and
  production serves `fe409f3` with `db: ok`.

- **2026-09-23 (scheduled jobs fixed, `aeb87aa`; Group T approved)** — Craig said yes to the
  jobs fix and to Group T, and no to applying for eBay's Buy API. A job now runs without
  the web server's secrets, and `src.main` refuses to start as a job (#204). CI failed once
  on a new test that read secrets from the environment. It was fixed and green on the
  re-run, and production serves `aeb87aa` with `db: ok`. The first cron runs are due at
  03:00 and 08:00 UTC on 24 Sep.

- **2026-09-23 (the 23 Sep snags reconciled, and sign-in renewal fixed, `aa112bd`)** — Craig
  raised 14 snags. Each was checked against the code, live Neon (read-only) and live TMDB,
  and the results are in `docs/owner-snags-2026-09-23.md`. Found along the way:
  - **Session renewal had never worked:** 30 sign-ins and 0 renewals. Fixed on
    `fix/session-renewal`. CI was green (1,175 passed, including the 4 new Postgres
    tests), and production serves `aa112bd` with `db: ok`.
  - **Both scheduled jobs crash on import every day,** because they're missing web-only
    secrets.
  - **`release_calendar` hasn't changed since 9 Sep** and holds no physical rows. That
    contradicts S6's record, which is now corrected.

  Craig's answers:
  - fix the sign-in bug without making it a batch
  - five-tab navigation (#201)
  - Blu-ray.com option A (#202)
  - an eBay alert and auto-buy hybrid (#203)
  - diagnose the jobs

  Group T is proposed and not approved.

- **2026-09-20 (identification tidy-up — and Jack the Ripper got its disc back)** — Ran
  `--identify` over both diaries at Craig's instruction after the import above. **3 films
  identified**, all from Mark's: *Nocturnal Animals* (340666), *The Firm* (37233, retitled
  from `Firm, The`) and *The Secret Identity of Jack the Ripper* (220168).

  **The third was a merge, and it repaired a split the refresh had made.** The fresh sheet
  lists the film as plain `Jack the Ripper`, which matched nothing and arrived as a new
  title-only row carrying the disc — while the old `The Secret Identity of Jack the Ripper`
  row kept its 2 watches and no disc, one of the two genuinely-stranded films from 2026-09-18.
  Mark's diary resolved the new row to 220168, `apply_identification` found the existing row
  and merged them, and the disc and the history are back together. `movies` 1,888 → 1,887,
  and **0 orphaned watch rows** created by the merge.

  Watch rows on disc-less films: **7 → 5** (*Misery* 2, *Project Hail Mary* 2, *Crime and
  Punishment* 1 — the first two were already disc-less before any of this). **Unidentified
  films holding watch history is back to 1**, and that one is *The Pacific*, a miniseries
  TMDB's film search cannot match. Craig's diary reported 1 film to identify and identified
  0, which is that same title.

- **2026-09-20 (diary re-run after the refresh — 11 new watches)** — Additive run of both
  diaries now the 34 new films are catalogued. Craig 1, Mark 10; `watch_log` 1,555 → 1,566.
  Mark's are mostly the Agatha Christie TV films and the noir downloads the April sheet
  never listed — *Murder in Three Acts*, *Thirteen at Dinner*, *Appointment with Death*,
  *Murder Is Easy*, *Way Out West*, *Blood on Satan's Claw*. **Unidentified films holding
  watches went 1 → 3**: *The Firm* and *Nocturnal Animals* arrived in the refresh without a
  `tmdb_id` and have now been watched. `--identify` was deliberately not passed — it is a
  separate decision from writing watches (#175) and this run was authorised as the import.


- **2026-09-18 (the collection refresh ran — 1,880 discs, 0 watches lost)** — Three batches
  and one live replacement. Batch 41 (`2d2858c`) and Batch 42 (`00bdcd9`) shipped, then the
  fresh spreadsheet replaced the April catalogue: 1,857 items to Trash, 1,880 inserted, 34
  new films, **1,555 watch rows unchanged and none repointed**. All 10 Blu-ray.com spec rows
  are preserved on the Trash items as #195 accepted. 7 watch rows sit on 4 disc-less films;
  two of those were already disc-less before the run.

  **The day's real finding was between the batches.** The first dry run of the fresh sheet
  would have duplicated 401 films and stranded 587 watch rows silently, *because* of the
  identification run done correctly that morning: `upsert_unmatched_movie` reused a film
  only via `title = %s AND tmdb_id IS NULL`, and 395 films had just gained a `tmdb_id`
  (#198). Batch 39's guard passed it — it counts unidentified films holding watches, which
  was 1. Doing the right thing in the right order created the hazard, and only running the
  rehearsal and reading past the summary line caught it. Batch 42 then narrowed the new
  guard after it named two films that were never at risk (#199), on the reasoning that a
  guard with a one-flag override must not cry wolf.

  Also corrected mid-flight: two claims in Batch 40's write-up that a throwaway branch
  disproved — the per-film identification guard is about duplicate *report* lines, not TMDB
  cost, since the matcher already caches searches.


- **2026-09-17 (Batch 40 — identification on a re-run, `78dc054`)** — Craig asked
  whether to import a fresher spreadsheet. Checking the prerequisite turned up that
  `OWNER-ACTIONS.md` 1i step 2 **could not be run**: `--identify` had been unreachable
  since step 1 wrote the watches on 2026-09-15, because the already-imported check sat
  above the match. Two dry runs against live Neon proved it — Craig 593 already imported /
  0 identified, Mark 962 / 0 identified — and no test caught it, because every S8
  identification test identifies on a *first* run, the one case where the two halves are
  separable (#197). The skip now suppresses the watch row alone. Fixed two latent faults
  the change would otherwise have made common: TMDB is called once per film rather than
  once per watch (a failed identification leaves `tmdb_id` NULL and so looked like work to
  redo on every watch), and a later entry follows a row that identification merged away
  rather than writing against the deleted movie. Six tests added; CI ran **1,152 tests
  with none skipped**. A throwaway branch carrying the new tests against the *unfixed*
  importer was pushed first to confirm they actually fail — this batch exists because a
  suite asserted a design and never the sequence. **Nothing was identified and nothing was
  imported**; both live runs remain Craig's.

- **2026-09-16 (Batch 39 — guarded collection refresh shipped, `b1db470`)** — Added
  `--replace-items`: all live items move to Trash in the same locked transaction as the
  import, dry-run reports without writing, and matching/enrichment or database failure
  leaves the live collection intact. The importer now deduplicates source rows against
  live items only; migration 034 replaces the historical unique index with a live lookup
  index so a complete old row can be restored even after its sheet line is reused (#196).
  Postgres CI proves watches survive, existing movies are not overwritten, identified
  replacements reuse their movie, and derived ownership ignores old rows. **The live run
  did not happen** and remains `OWNER-ACTIONS.md` 1k after identification and a fresh sheet.
  Batch-start corrected the safety measurement from 0 specs to 10; Craig accepted losing
  those from the active collection while preserving them on the Trash rows (#195). First
  CI was red because the new test fixture used `None` where the TMDB model requires integer
  budget/revenue; fixed to TMDB's `0`, then branch and `main` gates passed. Production serves
  `b1db470162e7cab62ff1e72036a7fdba690c5c05` with `db: ok`.

- **2026-09-16 (the refresh path chosen, and written up as Batch 39)** — Docs only. Craig
  picked option 1 of `OWNER-ACTIONS.md` 1k: rebuild the discs, keep the films. Decided on a
  measurement rather than a preference — `collection_items` carries no app-created data and
  **nothing references a `collection_items.id`**, so the item identity a refresh-in-place
  would protect is protecting nothing. **Batch 39 — Collection refresh** entered in the
  ledger with criteria authored rather than recovered (#54 does not apply). Tiered 🟡 /
  `xhigh` on Batch 15's precedent: 1,857 live rows, and two silent failure modes — a missing
  `deleted_at` filter empties the collection while reporting success, and replacing before
  identifying splits 586 watches from their discs without erroring. **The live run stays the
  owner's** and waits on a spreadsheet that does not exist yet.

- **2026-09-15 (the importer cannot refresh)** — No code change. Craig proposed a fresher
  spreadsheet import before go live and asked whether identification should wait for it.
  Checking turned up that **re-running the importer over live data refreshes nothing**:
  items dedupe on the spreadsheet *line number* and all 1,857 lines are claimed, while the
  film upsert runs independently and would add orphan `movies` rows with no discs (#192).
  Identification was deferred as Craig asked — but the premise does not hold, because the
  importer cannot back-fill a `tmdb_id` onto an existing row. **A wipe-and-reload also
  stopped being free today**: 397 unidentified films now carry 586 watches and
  `watch_log.movie_id` is `RESTRICT`. Three paths written up as `OWNER-ACTIONS.md` **1k**,
  which now blocks go live. Also flagged: `.letterboxd-export/` is load-bearing for two of
  those paths and exists on one machine (#193).

- **2026-09-15 (the live watch-history import)** — Run at Craig's instruction after Group S
  closed. **1,555 watch rows written** — Craig 593, Mark 962 — matching the dry runs exactly,
  which is the check that a dry run is a rehearsal rather than a different code path that
  prints numbers. 1,101 distinct films; 245 both of them have seen. On this day, Worth a
  rewatch, Most watched and S7's "has he seen it" all have data for the first time.
  **Re-running wrote 0**, proving idempotency against production. 28 ambiguities skipped and
  written out. **Step 2 (`--identify`) deliberately not run** — it rewrites ~397 existing
  `movies` rows and deletes some (#189). **Two corrections:** #159's "Mark rates nothing" is
  true of the 50-entry RSS window and wrong about his history — he has rated 178 of 1,149
  (#190); and `OWNER-ACTIONS.md` 1i's `set -a` command could never have worked, because
  `DATABASE_URL` is unquoted and contains an `&` (#191). **Two credentials were exposed in a
  session transcript** by a careless `head` of `.env.local` — see the Now block.

- **2026-09-15 (Batch S7 — movie night rebuild)** — Group S batch 8 of 8, shipped as
  `804744f`, **green first time**. Votes moved from films onto `movie_night_suggestions`,
  which is the one change that makes three of Craig's five points possible at once (#185):
  anyone suggests, everyone votes on anyone's, and a film outside the Archive — with no
  `movies` row to key against — can be voted on at all. Cards carry cast, runtime, genres,
  who suggested it, streaming for films nobody owns, and **which other participants have
  seen it and when** (empty until S8's import runs). The unseeded `func.random()` that
  contradicted its own docstring is seeded on `md5(session_id ‖ movie_id)` rather than
  having the claim deleted (#187). **The migration is additive** — 13 votes across 2 open
  sessions — with a CHECK written for the database where the backfill did not run (#188).
  The shared list keeps what you have voted on; the other person's vote stays invisible
  (#186).

- **2026-09-15 (Group S complete)** — All eight snag batches from the 2026-09-14 triage
  shipped and deployed in one run. **Six CI failures, none reaching `main`**: four in the
  batches' own new tests (invisible locally, where the Postgres tests skip), one mypy
  strictness difference, and one that was not a code failure at all — `git add` aborting on
  a stale pathspec with its stderr suppressed, so a commit carried only two deletions
  (#184). **Four spec facts were wrong and the code was right each time** (#170, #172,
  #174, and S6's row count). Nine test expectations changed, every one required by a
  criterion and none of them a weakening. **Three owner actions wait**: `OWNER-ACTIONS.md`
  1h, 1i and 1j.

- **2026-09-15 (Batch S6 — physical release dates)** — Group S batch 7 of 8, shipped as
  `b5b3796`. `tmdb/client.py` gains `get_release_dates`; GB type 5 is ingested **beside** the
  cinema date, and Calendar merged with Coming soon at `/calendar` (`/discover` redirects).
  **Coverage measured and reported: 1%** — 1 of 58 forthcoming GB films has a physical date
  (#181), so the disc section leads, is usually empty, and says the number. `classify_physical`
  reads TMDB's free-text note because type 5 cannot distinguish 4K from Blu-ray (#182).
  **One CI failure, from `git add` aborting on a stale pathspec** with its stderr suppressed —
  the first commit carried only two deletions (#184). Sidebar 8 → 7.

- **2026-09-15 (Batch S5 — watch history, ongoing)** — Group S batch 6 of 8, shipped as
  `834c3f1`. Reads the public Letterboxd diary RSS feed and keeps `watch_log` current,
  **reusing S8's matcher and writer whole** — S5 added only `feed.py` and `sync.py`. The
  no-double-count criterion is proved end to end: import from the file, sync the feed, second
  writes zero. `letterboxd_syncs` records every run **including failures**, because a silent
  failure and a sync that never ran look identical and the 50-entry cap makes the difference
  expensive (#180). The panel says when it last ran — seen at 375×812. **The fixture is built
  from recorded element names rather than a captured payload**, so the parser is deliberately
  prefix-blind and a test proves it (#178); `OWNER-ACTIONS.md` **1j** is the one-press owner
  check that settles the real shape. **One CI failure** in the lint job: CI's mypy vs local,
  gotcha 21 again.

- **2026-09-15 (Batch S8 — watch history, the backfill)** — Group S batch 5 of 8, shipped as
  `0a8c813`. Importer, matcher and dry run for a Letterboxd diary; migration `031` adds
  `watch_log.letterboxd_viewing_id`, unique per person, which is **also S5's
  no-double-count criterion, met and tested here** (#176). **Both dry runs executed against
  production and wrote nothing**: 1,555 watches and ~397 identifiable films wait for Craig
  (`OWNER-ACTIONS.md` 1i). **#160's "6 ambiguities" is corrected to 28** (#174) — the shipped
  matcher is stricter, and 22 rows #160 scored as "not in the collection" are really
  questions; 66% unchanged. `--identify` is deliberately a separate flag from `--write`
  (#175). `_apply_identification` extracted to `services/identification.py`. **One CI
  failure**, in this batch's own test, where the code was right and the assertion wrong.

- **2026-09-15 (Batch S4 — quick add within reach)** — Group S batch 4 of 8, shipped as
  `45ec4fa`. Mark can add a disc and a phone has somewhere to do it from: an accented Add slot
  in the bottom bar and a button on Home, both visible below 640px. **Eight endpoints moved
  from `AdminUser` to `CurrentUser`**, not the three the criterion named — the eighth,
  `PUT /collection/{id}/listing`, is what "List for sale" actually calls, and without it every
  visible step of the upgrade flow would have worked and the button would have 403'd (#170).
  Editing and destroying stayed admin-only; the line is where the attribution is (#171). **One
  criterion was wrong in the code's favour** — `GET /retailers` has been open to a viewer since
  Batch 18 and the criterion meant the page (#172). **One CI failure in this batch's own test**,
  which was passing a 409 duplicate off as a role check (#173). Browser pass driven as a
  *viewer* at 375×812 by the harness method #169 records.

- **2026-09-15 (Batch S3 — navigation shape)** — Group S batch 3 of 8, shipped as `a3409f1`,
  green first time. **Fourteen sidebar destinations became eight**, by merging what was thin
  but real (Home+Stats+Insights → `/dashboard`; Notifications+AI settings → `/settings`) and
  hiding what is empty (Box sets, Collections, Deals, Loans). New `GET /nav/sections` supplies
  the four counts; an unknown count shows the item, so a slow request cannot empty the menu.
  **Both states seen in a browser at 375×812 — 8 with the counts at zero, 12 with them full.**
  `navGroups` is built by path rather than index, which is the defect that had already lost AI
  settings from every group. Search moved from the mobile header's second row to the bottom
  bar; `FilterBar` is one control at 375px; `/` opens Home; Export moved to Admin. The empty
  charts are hidden **with their explanations kept** in one line beneath (#167). The signed-in
  browser pass used the repo's DEV-only `VITE_SKIP_AUTH` plus a scratch API stub rather than a
  PIN (#169); nothing from it is in the tree. Decisions #165–#169.

- **2026-09-15 (Batch S2 — app-feel fixes)** — Group S batch 2 of 8, shipped as `baef542`,
  green first time. Form controls **14px → 16px** at touch widths, `touch-action:
  manipulation` moved from buttons alone to `html` and `body`, and the Letterboxd link
  rebuilt on `letterboxd.com/imdb/<imdbId>`. **Pinch-zoom deliberately preserved** and
  guarded by four tests on the real `index.html`, because `user-scalable=no` would have
  suppressed all three gestures at once and looked like a fix. The 16px floor sits in the
  base layer with a `:not()` that lifts it to 0-1-1 so it beats Tailwind's `text-sm` without
  `!important` — `.form-control` alone would have missed `FilterBar`, `CommandPalette` and
  `SearchBar`. Probed against the shipped stylesheet at 375px: ten class combinations, all
  16px; 14px again at desktop. The slug branch is **deleted, not demoted** — it was
  unreachable on all 1,854 rows. **Two criteria stay unmet and are Craig's** — both need a
  phone — recorded as `OWNER-ACTIONS.md` **1h** rather than implied away.

- **2026-09-15 (Batch S1 — gift links removed)** — Group S batch 1 of 8, shipped as
  `43d1ecf`. Both routes, both pages, the model, router, schemas, the eight `lib/api.ts`
  client functions, the zod schemas and their tests, the nav item and the service-worker
  cache exclusion are all gone; migration `030` drops the table. **Re-measured against live
  Neon immediately before the merge: 0 rows, 0 recorded views** — so the drop destroyed
  nothing and the destructive-operation stop did not apply. `030.downgrade` recreates the
  table in full, because `018.downgrade` drops a table that must exist by the time CI's
  reversal reaches it. Production serves `43d1ecf` with `db: ok`, and `/api/v1/gift/{slug}`
  answers 404. **One CI failure:** the new restore test's retailer fixture used
  `scraper_type="generic"` against a CHECK constraint allowing only `built_in`,
  `generic_css` and `custom` — invisible locally, where all 254 Postgres-backed tests skip
  (gotcha 3), and caught the moment CI ran it against real Postgres 17.

- **2026-09-15 (snag batches entered as Group S)** — Docs only. The eight batches from the
  triage written into `docs/phase-batches.md` with acceptance criteria **authored, not
  recovered**, plus a Group S row ordering them S1 → S2 → S3 → S4 → S8 → S5 → S6 → S7.
  `/batch-start` stops on a batch it cannot grep, so the ledger entry is what makes
  `/group-start S` possible at all. Two owner actions are scoped inside their batches rather
  than made group checkpoints: S8's live import (~1,530 watch rows and **396 `movies` rows
  overwritten** with identification data) and S5's first live RSS fetch.

- **2026-09-15 (Letterboxd history retrieved)** — No code, hosting or schema changes. Both
  diaries retrieved in full from the **public** diary pages — Craig 1,173 entries back to Dec
  2013, Mark 1,149 back to Nov 2022, **2,322 total** against RSS's 100. The earlier 403 was
  curl's TLS fingerprint, not a block. 47 paced page loads, once, outside the product; files
  gitignored in `.letterboxd-export/`. Matched live: **1,530 (66%) are films they own** and
  **396 would be identified** by the import; 6 ambiguous across 2,047 distinct films.
  **Letterboxd Pro is not needed** — `OWNER-ACTIONS.md` 1g closed unused, ~£70 saved. S8
  unblocked and resequenced ahead of S5; neither ships a scraper. `DECISIONS.md` #160, #161.

- **2026-09-14 (owner snag triage)** — Docs only: no code, hosting or data changes, and no
  decisions taken. All 11 snags investigated against the code at `8e02399`, live Neon
  (read-only `SELECT`s) and the deployed app at 375×812. Six of the capture's claims corrected;
  five of its seven open questions answered and two dissolved. Seven batches proposed, two of
  them startable with no further decision. Written up in
  `docs/owner-snags-triage-2026-09-14.md`. Three new questions for Craig: Letterboxd Pro
  (~$35/yr per account), whether Mark gets write access, and whether Movie night is rebuilt or
  accepted as built.

- **2026-09-14 (owner snag capture)** — Docs only: no code, hosting or data changes, and no
  decisions. Craig listed 11 snags — Archive header and search placement, merging Calendar and
  Coming soon, page-style zoom, removing Gift links, the menu, Movie night behaviour, quick add
  with an eBay listing offer, Mark-and-Craig-only access, Letterboxd deep links, Letterboxd
  sync, and the opening screen and bottom bar. Written up in `docs/owner-snags-2026-09-14.md`.

- **2026-09-13 (Batch 21 cron diagnosis + Batch 22 §5.9 live attempt)** — Two read-only/
  reversible investigations, no code changes, no hosting changes.

  **Batch 21: root cause found.** `railway status` shows both `cron-scrape` and
  `cron-reminders` as `Crashed`, not merely un-fired. Logs from both name the same
  `pydantic` validation error: `config.py` refuses to boot without
  `JWT_ACCESS_SECRET`/`JWT_REFRESH_SECRET`/`FRONTEND_ORIGIN`, none of which
  `.railway/railway.ts` gives the cron services — only `DATABASE_URL` and the VAPID vars are
  passed by reference from `api`. Every scheduled fire since 2026-09-10 has crashed at
  import time before doing anything. Fix is a hosting change (`railway.ts` + `config apply`)
  and stays the owner's.

  **Batch 22 §5.9: attempted live, not met.** Owner logged in; `POST
  /api/v1/deals/scrape?dryRun=true` run twice, nothing written either time.
  First run: 4 of 5 enabled retailers had `dealsUrl: null` — `apply-built-ins`'s fix
  (`493f031`) was never re-run against production after shipping, so the seeded rows
  predate it. Re-ran `POST /api/v1/scrapers/apply-built-ins` (idempotent, no destructive
  effect) and all 5 gained a `dealsUrl`. Second dry run then surfaced real per-retailer
  problems, checked live in a browser against each site's actual markup:
  - **101 Films** — URL correct; its sale collection genuinely holds 0 items right now.
  - **Arrow Video** — guessed `/collections/sale` 404s; the site has no equivalent page at
    all. Its real discounts are `/c/offers/multibuy/...` bundles ("2 for £40"), a different
    shape than a per-item was/now price.
  - **Powerhouse Films** — real sale page exists (14 pages of items) but every item shows
    only "Regular price"; its discount mechanic is a "3 for 20% off" bundle badge, same
    shape problem as Arrow.
  - **Second Sight** — real sale collection (81 products); some genuinely carry a
    Regular/Sale price pair (e.g. Dog Soldiers, £24.99 → £17.99) but the scraper's selector
    isn't matching that markup, so `check_page_shape` correctly refused the page wholesale
    rather than risk 80 false discounts.
  - **Zavvi** — configured URL 404s; the real page is `/c/offers/flash-deals/film/` and
    has genuine Current-price/RRP pairs across dozens of items, but was never tried because
    the seeded URL guess was wrong.

  **§5.9 remains open.** Getting to ≥ 20 rows / ≥ 3 retailers needs real fixes — a correct
  `dealsUrl` and a markup-matched selector per retailer — not a second live run. Arrow and
  Powerhouse may need a different extraction shape entirely (bundle discount, not was/now).
  Owner decided to stop here rather than write scraper code unreviewed; this is recorded so
  the next session doesn't re-discover it from scratch. `OWNER-ACTIONS.md` 1e updated.

- **2026-09-12 (Batch 22 — deals feed shipped)** — The feature shipped as `c190129`, then
  close-out found and repaired a real configuration path: **Apply built-ins** did not copy
  the four new sale-page URLs or their `was`/`image` selectors, so only the one previously
  seeded retailer could ever contribute deals. `493f031` fixes that merge and adds a
  regression property covering all five enabled shops. Local targeted coverage: 25 deals
  tests passed; the full local ruff/format/mypy, API, shared/web test, lint, typecheck and
  build gate was green. CI `34702596864` passed all five jobs, including real-Postgres
  migration upgrade/downgrade and pytest. Production `/health` reports `493f031` and
  `/health/ready` reports `db: ok`, `push: configured`, `ai: configured`, `ebay:
  configured`. **§5.10 is met; §5.9 remains owner acceptance** — the live sale-page run
  and its ≥20 rows / ≥3 retailers observation are `OWNER-ACTIONS.md` 1e. No hosting,
  credential, destructive-data, or history operation was performed.

- **2026-09-12 (Batch 24 — barcode scan + lookup shipped)** — Fast-forwarded and deployed
  `590504d`; feature CI `34692586230` and post-merge `main` CI `34692681855` passed all
  five jobs. Production `/health` returned the exact merge SHA, `/health/ready` returned
  `db: ok` and `ebay: configured`, and Vercel served the Add Disc route with camera
  permission scoped to self. Craig explicitly deferred the owner-only real-phone timing,
  common-disc correctness and unknown-code fallback observations until after deployment;
  they remain open in `OWNER-ACTIONS.md` 1d rather than being claimed by the green suite.
  The live eBay keyset clears the runtime blocker, but its missing Railway `preserve()`
  declarations remain owner hosting drift in 1b. Decision #149.

- **2026-09-12 (Batch 24 — barcode scan + lookup, implementation complete)** — Built the
  scan-first Add Disc flow, `POST /api/v1/barcode/{lookup,confirm}`, GS1 check-digit guard,
  exact-collection duplicate signal, eBay→TMDB candidate chain, confirmation-only mapping
  cache (migration 028), manual-title fallback and barcode persistence on the added copy.
  ZXing `^0.21.3` is Node-20-compatible and loads only when the camera is requested. Added
  unit, API, wire, state-handoff and real-decoder coverage; the latter synthesizes and
  decodes EAN-13 `5051892211475`. Local gate green: 608 API passed / 405 DB-skipped,
  88 shared + 261 web passed, ruff/format/mypy/lint/typecheck/build green; migration 028
  upgrade and downgrade SQL render. Browser-checked scan and title panels at mobile width.
  **Not closed out:** a physical phone scan under two seconds and the live common/unknown
  lookup checks remain owner actions, and Railway still reports `ebay: not_configured`.
  No hosting change, push, merge or production deployment was performed. Decision #148;
  `OWNER-ACTIONS.md` 1b/1d.

- **2026-09-12 (Batch 29 — format upgrade + sale tracking)** — Shipped `f215bf3`. **Both
  criteria met**, no migration. A sold disc keeps its row and `owned_copy()` removes it
  from the views, replacing eighteen hand-written filters across seven routers (#145);
  `listed_for_sale` still counts as owned. Three defects found: no audit row was written
  at all (`listing_status` was unaudited), a bespoke `listing_sold` action type is refused
  by §3.20's closed CHECK, and `copyCount` was `ge=1` so selling your only copy 500'd the
  film's page (#146, #147). CI red once — a test borrowed a disc from the catalogue, which
  exists on Neon and not in CI's empty Postgres. Group I is complete.

- **2026-09-12 (Batch 28 — eBay integration)** — Shipped `b2a6c27`. New `src/ebay/` package
  (Browse client with a cached application token, match filter, segmented median,
  pre-filled listing URL), two admin endpoints, an `ebay` field on `/health/ready`, and a
  **Value and resale** panel on each owned copy. **4.3 met** — Option A does not exist, so
  Option B is primary and prefill was confirmed in a browser: the parameter is `title`
  (`DECISIONS.md` #142). **4.1's acceptance NOT met — a live production call and the
  owner's.** Proven instead against two captured 200-listing payloads: naive £24.74 against
  a matched £9.99 from 29 plain Blu-rays. Two guards were wrong first time and the fixtures
  caught both (#143). **Production reports `ebay: not_configured` — the Railway keyset
  variables were never set** (`OWNER-ACTIONS.md`).

- **2026-09-11 (batch criteria recovery)** — Recovered acceptance criteria for the seven
  remaining planned batches — 21, 22, 24, 29, 33, 34, 38 — verbatim from §16 at
  `d94a6b8~1`, per `DECISIONS.md` #54, and wrote them into `docs/phase-batches.md` as a new
  section. All 69 quoted lines verified against the archived document programmatically; the
  one deliberate deviation is dropping the decayed `Sonnet 4.6` / `Opus` annotation while
  keeping the tier emoji, following Batch 11's precedent. Recorded three criteria the repo
  already contradicts (Recharts, Amazon, Supabase Vault) and corrected two stale ledger
  claims (the `cryptography` risk note, Group H's eBay block on Batch 24). `DECISIONS.md`
  #141.

  Also found, while checking Batch 21's data gate: **the nightly scrape cron has not fired.**
  Applied 2026-09-10 on `0 3 * * *`, it had produced no `scrape_runs` row by 22:26 UTC on
  2026-09-11, 19 hours past its first scheduled run. §5.5 is failing rather than pending and
  Batch 21 is blocked behind it. Recorded in `OWNER-ACTIONS.md` #1; not acted on, because
  hosting is an owner action.

  Gate green locally: 508 API tests passed, 239 web + 79 shared, ruff clean, mypy clean on
  118 files, web lint 0 errors, typecheck clean, production build passes. Docs-only change.

- **2026-09-11 (brand hierarchy correction)** — A rendered design review reversed the
  over-application of photographic identity artwork from `00414f5`. Navigation and loaders
  now use the compact vector mark; desktop sign-in uses the complete 440 px horizontal
  lockup in a restrained editorial panel; mobile sign-in no longer stretches its brand
  row; onboarding keeps the personalised poster as its sole 192 px reveal; and social
  metadata again names the rights-independent 1200×630 card. Added regression coverage for
  those boundaries and for responsive lockup proportions. PR #2 merged as `d961937` and
  main CI run `34578379338` passed all five jobs. Production was rendered from Vercel at
  1440×900 and the mobile breakpoint; Railway reported that exact SHA and `db: ok`.

  One of two duplicate pre-merge CI runs hit the existing timing-sensitive SearchBar
  assertion; the identical push run was fully green and the failed job passed unchanged on
  rerun. No expectation or test was weakened.

- **2026-09-10 (evening, continued)** — **Personalised poster now visible in authenticated header and sidebar.** LoginPage mobile header simplified (removed hero photo backdrop). Sidebar and AppLayout header now display personalised-poster-icon-512.png instead of brand marks — all authenticated navigation surfaces feature the real poster stack with stills from Mark's collection (Jaws, Double Indemnity, An American Werewolf in London). Gate green: 235 web + 79 shared tests, 508 API tests, all lint/typecheck/build clean. Commit `00414f5` deployed to main; Vercel/Railway automatic deployment in progress.

- **2026-09-10 (evening)** — **Phase 1 display fixes deployed.** Photo hero logo sizing corrected on LoginPage (desktop: w-auto min-w-full preserves aspect ratio instead of stretching; overlay opacity strengthened for text contrast). Personalised poster visibility improved across all loaders (h-32 → h-40/h-48, w-auto for aspect ratio, shadow-md for separation, centered on onboarding with responsive srcset). Gate green: 235 web + 79 shared tests, 508 API tests, all lint/typecheck/build clean. Commit `fb6ecbd` deployed to main; Vercel/Railway automatic closure in progress.

- **2026-09-10** — **The approved identity is integrated into the app.** Placeholder icons
  deleted; 18 assets installed under `apps/web/public/brand/` from the untracked design
  system via the new tracked `scripts/brand-sync.mjs`. `BrandMark`/`BrandLockup` apply the
  responsive hierarchy and follow the theme without flashing. Builder extended for the 384 px
  PWA icon, a one-colour notification badge and a rights-independent share card. Fixed the
  `sw.ts` `/icons/` path that never existed, the placeholder blue in the manifest, and a
  28 px mark under its 32 px floor. 235 web + 79 shared tests, 0 lint errors, clean
  typecheck, build passing, CLS 0 on login. `DECISIONS.md` #133–#139.

  **Headless Chrome still aborts on this macOS build** (`_NSCGSTransaction dealloc`,
  reproduced) — but the **CDP route works**: a Chrome launched with
  `--remote-debugging-port` and driven over the protocol captured all 16 branded surfaces at
  2×, no credential involved. That is the mechanism `OWNER-ACTIONS.md` #14 proposes, now
  proven, and `.claude/launch.json` gained a `web-dist` entry that serves the built bundle
  so a session can verify the artefact that ships rather than the dev server.

- **2026-09-10** — **The redesign closed out, with one deliverable knowingly incomplete.**
  Gate green locally from a clean tree and green in CI (`34502543298`): ruff, 192 files
  formatted, mypy across 118 files, **508 API tests**, **213 web + 79 shared**, 0 lint
  errors, clean typecheck, build passing. Merged to `main` and deployed. **The before/after
  screenshots did not get finished** — nine before, three after — because headless Chrome
  aborts on this macOS build and the token-injection route was correctly refused; that is
  recorded as an open deliverable (`OWNER-ACTIONS.md` #14) rather than quietly dropped.
  Three design/deployment calls went to the owner as #11–#13.

  **And for the first time the deployed web bundle was actually run, not just built.**
  Gotcha 3 has always said a green web job is no evidence the app boots — Decision #22's
  white-screen is why. Post-merge, `mcu-app-fawn.vercel.app` was loaded live: the redesigned
  login page renders, **no console errors**, and `document.title` reads `Sign in · The Real
  MCU`, which is #132's single owner working in production. At **375px: zero horizontal
  overflow, one `h1`, zero controls under 44px** — so #131's `@layer utilities` fix is real
  in the shipped bundle and not only in the suite. Authenticated surfaces were not re-checked
  post-merge; they were measured live before it.

  **`docs/brand/` was deliberately not swept into the merge.** 189 files, 56 MB, untracked,
  built in a separate session that morning — and `source-images/` is third-party film
  stills gathered as reference. The committed `VERIFICATION.md` §5 already calls its
  `stack-family/` set "approved", so `main` now references a path the repo does not
  contain; closing that gap is `OWNER-ACTIONS.md` #15, because 56 MB of binaries in
  permanent history and a redistribution question are both the owner's call, not an
  agent's.
- **2026-09-10** — **The UI redesign's live pass, and three claims that did not survive it.**
  The branch's own audit recorded contrast, touch sizing and theme integrity as addressed;
  measuring them found error text at **3.13:1**, champagne on cream at **1.92:1**, and
  `.touch-target` silently inert because it was declared in `@layer components` — Tailwind
  emits that **before** `utilities`, so at equal specificity `min-h-8` simply came later and
  won. Every control that appeared to opt into a 44px floor had been unchanged. Fixed by
  splitting each tone into surface and text tokens across Tailwind's separate `textColor`
  scale (no call site touched), moving the floor to `utilities`, and rehoming ~60 raw
  palette classes. The gate now asserts all 42 contrast pairings (#130–#132).

- **2026-09-10** — **eBay connected, and the checkpoint that was supposed to gate it did not
  exist.** Research before the batch read eBay's own Buy API page — *"intended for eBay
  partners only"* — plus forum reports of small developers being rejected, and called
  production access roughly a coin toss. It is not: a self-service production keyset calls
  Browse at 5,000/day, and `q="Blade Runner 2049 Blu-ray"` on `EBAY_GB` returned **308 live
  listings**. Group I's checkpoint, `OWNER-ACTIONS.md` #5 and — less obviously — Batch 24
  are all unblocked (#126).

  **What was built:** `GET|POST /api/v1/ebay/account-deletion`, the app's **third**
  unauthenticated route, because eBay activates no production keyset until a developer
  either subscribes to account-deletion notifications or claims a "not persisting eBay data"
  exemption that carries account suspension if claimed wrongly (#127). It reads and writes
  nothing, carries **no rate limit** on purpose — eBay polls it and reads a 429 as an outage
  — and answers **503 rather than a wrong-but-plausible digest** when unconfigured. Verified
  end to end from eBay's own servers, not just our probes.

  **The endpoint URL is a literal in `.railway/railway.ts`, not `preserve()`** (#128): eBay
  hashes the URL *it* holds into every challenge, so a byte of drift fails validation with
  nothing to show for it. Both eBay variables were declared for #124's reason — undeclared,
  `apply` would have deleted them and returned the endpoint to 503.

  **And the measurement that will shape the batch** (#129): segmenting 310 live GB listings
  for one film gives **£30.45 across everything and £12.21 for the plain Blu-ray — a 149%
  overstatement**, because the query also returns 4K editions (£50.45 median), collector
  steelbooks (£105.61) and multi-film bundles. `condition` cannot fix it — it is a localised
  display string with 16 spellings for five conditions. `conditionId` can. **"We got a
  number" is not "we got the right number"** — the same lesson as `#122` and today's
  scrape-verdict bug, arriving a third time from a different direction.

  *Left for the owner:* `railway config apply` still shows one line of **pre-existing
  drift** — `deploy.restartPolicyType (null → "ON_FAILURE")`. The live `api` service has had
  **no restart policy since Batch 2** while this repo claimed otherwise; visible only because
  today was the first `config plan` run since that file was written.

- **2026-09-10** — **Checking the retailer selectors found four bugs, and the selectors were
  mostly fine.** The first unattended-shaped run logged 11 failures out of 17. Checked
  against the live sites, one at a time:

  **Eight were not failures.** Arrow answered *"Sorry We Couldn't Find Any Results"*, 101
  Films *"0 results found"*, Second Sight the same — they do not carry those films.
  `not_stocked` required `titled_cards > 0`, so it handled *"results returned, none
  matching"* and let *"no results returned"* fall through to the failure branch. Those feed
  auto-disable: **three quiet nights would have switched a working shop off**, unattended,
  and it had not bitten only because each shop happened to price one film that night.

  **Three were real, and the opposite kind of bug.** Zavvi renders two price markups on one
  page; the selector read only the variant-wrapped one, so a genuine **£16.99** on `Castle
  Freak` was fetched, parsed and discarded. Missed alerts rather than wrong ones.

  **A third, found while fixing the second.** `_select_one` used `select_one`, which for a
  comma list returns document order, not selector order — so Second Sight's
  `".price-item--sale, .price-item--regular"` never had the sale-first precedence it was
  plainly written for. Selector lists are tried in order now.

  **A fourth, found while making the first observable.** `/retailers` computed its
  denominator as `attempted - notStocked`, but `attempted` already excludes `notStocked`
  (`#107`). The real run — 17 attempted, 23 not stocked, six discs priced — rendered as
  *"Nothing to price — no shop had any of the wants"*. A docstring and the web tests both
  asserted the wrong contract, so two sources agreed with each other and disagreed with the
  producer.

  **`#125` supersedes one clause of `#107`, and it is named rather than dropped.** #107
  decided a page with no titled listing *"still takes a strike"*, so a redesign would
  eventually auto-disable the shop. Sound reasoning, wrong premise — it assumed zero
  listings means the site changed, and the measurement says it usually means the shop was
  asked a question. The redesign case survives one level up: it makes *every* want return
  nothing, which is what the new per-retailer flag says. Visibility over auto-disable, the
  owner's call.

  **CI caught what reading did not, twice.** A CHECK constraint rejected the new
  `no_results` status — Batch 16 doing its job, a new state has to be declared. And two API
  tests failed because I had changed expectations rather than fixed bugs: `attempted`'s
  meaning is #107's, not the docstring's. Both invisible locally (gotcha 15).

  Migration `027` is applied to production; 1,857 `collection_items` untouched.
  **Tonight's 03:00 cron is the verification** — and closes §5.5 in the same run.

- **2026-09-10** — **The owner applied the crons and closed three criteria; the live rows
  say which, and which are still open.** `cron-scrape` (`0 3 * * *`) and `cron-reminders`
  (`0 8 * * *`) exist in Railway, and `railway config plan` reads `0 to add, 0 to destroy`.

  **§5.6 met.** A manual nightly run attempted 17, wrote 6, and queued 2 alerts;
  *"Cross of Iron is £12.99"* was **sent and delivered** to a real iPhone. Mark's copy of
  the same alert is `suppressed` with reason `no_subscriptions` — the outbox behaving
  correctly, and the standing evidence that §6.2 is still open.

  **§9.1 met.** Two `claude-sonnet-5` calls in `ai_usage_log` with input and output tokens
  and cost recorded, no error on either.

  **§9.5 cannot be settled from data, and that is by design.** Recognition runs in the
  browser and dictation deliberately fills the input rather than sending it, so a spoken
  question and a typed one write identical rows. Only the owner can confirm it.

  **One thing to look at, not yet acted on.** That run recorded **11 failures out of 17
  attempted**, every one *"no price found — the selector matched nothing usable"*, against
  retailers where six other lookups succeeded in the same pass. 23 more were correctly
  `not_stocked`, and no retailer was auto-disabled. It is not a regression from today, but
  after `#122` — a parser that matched its own invented fixture and nothing the site
  served — "the selector matched nothing usable" is a sentence worth taking at face value
  rather than assuming it means the shop is out of stock.

  **A permanent, benign plan diff.** `api deploy.restartPolicyType` reports as changing on
  every plan: Railway stores it absent while `restartPolicyMaxRetries: 3` persists, so
  `ON_FAILURE` appears to be the default normalised to null. It was **not** removed from
  `railway.ts` — the default is undocumented, and changing a production restart policy on a
  guess is not worth a tidy plan. The number that matters is still `0 to destroy` (`#124`).

- **2026-09-10** — **`railway config apply` would have deleted two live credentials, and
  had been able to since the day they were set.** Found by running the read-only
  `railway config plan` before adding the cron services: it read `2 to add, 3 to change,
  **2 to destroy**`, and the two were `api.ANTHROPIC_API_KEY` and `api.TMDB_READ_TOKEN`.

  Both were set in the Railway console on 2026-09-09 and never declared in
  `.railway/railway.ts`. IaC removes what the file does not declare, so it read them as
  drift. Applying would have **recreated the TMDB outage of 2026-09-09 exactly** — every
  TMDB-backed feature answering 502 behind a fully green gate — and taken the assistant
  with it. The JWT secrets were a quieter version of the same thing: declared as generated
  values but sealed, so they cannot be read back to compare, so every plan reported them as
  changing and an apply would have signed both people out. `DECISIONS.md` #124.

  All ten API variables are now `preserve()` — which names a variable without putting its
  value in the repo — and the plan reads **`2 to add, 1 to change, 0 to destroy`**.

  **The two crons are declared rather than clicked.** `cron-scrape` and `cron-reminders`
  are services in `railway.ts` sharing the API's image at a different entry point, taking
  `DATABASE_URL` and the VAPID keys **by reference** from `api` so each secret has one copy.
  `restartPolicyType` is `NEVER`: they make live requests to real shops, and retrying a
  failed night automatically would turn one bad night into three. All that is left for the
  owner is `railway config apply`, which stays his because it is a hosting change.

  *What made the trap invisible:* `.railway/README.md` warned against running `apply`
  outside close-out, which reads as caution about changes you meant to make. The hazard was
  the opposite — a change nobody authored, produced by the file's silence. The README now
  says to read the destroy count first.

- **2026-09-10** — **Writing out the owner's remaining steps found a live data-loss bug.**
  §5.6 needs a want whose `max_price` sits above its current price, and there was no way to
  set one on a want you already had: the field existed on the add form and nowhere else.

  Adding that control meant reading the update path. `PUT /api/v1/wanted/{id}` **replaces
  the row** — every field on its request model defaults to `None` — and the web app's one
  call site sent `{isActive}` alone. **Every press of "Stop looking" or "Look again" also
  nulled the format, the edition, the maximum price and the notes**, silently, in
  production, with `admin_actions` recording it faithfully as a change nobody had asked
  for. `DECISIONS.md` #123.

  The endpoint is not the bug: `PUT` means replace. The client now sends the complete
  resource with only the changed field overridden, `updateWanted` takes the row's own
  `currency` instead of hard-coding `GBP` where no caller could override it, and two tests
  pin both halves — the toggle round-trips every preference, and the endpoint's
  full-replace contract is asserted so the next person reads it as the contract rather than
  patching the API to be lenient.

  **A verification note worth keeping.** Confirming the new control had deployed by
  comparing the local bundle hash against Vercel's was wrong twice over: Vercel injects
  `VITE_API_URL`, so the hashes can never match, and Vercel answers an unknown
  `/assets/*.js` with `index.html` at **200**, which reads as "the file is there". The
  reliable check is to read the deployed `sw.js` precache manifest, fetch what it names,
  and grep for a string only the new build contains.

- **2026-09-10** — **§3.7's live run found that Batch 23's scraper had never worked, and
  the fix's own re-run found a second bug.** The owner accepted `#110`'s risk and asked for
  the run (`#121`).

  **First pass: ten pages fetched, `200` on all ten, zero specs extracted.** The parser
  looked for `<div class="row"><strong>Codec:</strong>`; the site serves
  `<span class="subheading">Video</span><br>Codec: MPEG-4 AVC<br>` — section headings with
  bare `Label: value` lines and no `<strong>` anywhere. `_label_of` returned `""` for every
  node on every page.

  **The suite could never have caught it.** `test_specs.py`'s `PAGE` was hand-written to
  match the parser. Fixture and parser agreed with each other and neither had ever met the
  site; eleven extraction tests passed against markup that has never existed. This is the
  third time this project has had a green gate over a broken feature — the missing TMDB
  token, the scraper *test* button that saved nothing, and now this.

  **Second pass: one audio track where the page lists six.** With one captured fixture the
  parser passed, but `Blade-Runner-2049-4K/189774` wraps its tracks in a `<span title="…">`
  and Fight Club's page does not, so a `_lines` reading only top-level children flattened
  all six into one string — and gave that one track a channel count belonging to the line
  below it, which is worse than storing nothing. `_flatten` recurses now. **One real page is
  a sample of one**, so the 4K page is a second fixture, kept precisely because it disagrees
  with the first about its own markup. It also carried the only HDR block of the ten, which
  the flattened version was dropping too.

  **Third pass met the criterion:** 10 rows of 1,857, 10 distinct release URLs, no halt, no
  currency symbol in any derived field.

  **What held throughout.** Every one of `#110`'s bounds — sequential requests five seconds
  apart, honest user agent, no redirect following, exact release URLs, never a `403`. And
  `apply_specs` checks `is_empty` before touching a row, so two broken passes cost twenty
  wasted requests and **no data**: a parser that stops matching the site writes nothing
  rather than blanking 1,857 rows. `DECISIONS.md` #121, #122.

  **The guard that matters more than the fix.** `TestTheFixtureIsReal` asserts the fixtures
  stay captured — provenance line present, `<span class="subheading">` rather than
  `<strong>` rows, price cell still in place. A fixture written to match the parser is the
  bug; a test that says so is the guard.

- **2026-09-10** — **The two Railway crons had nothing to run.** Found while walking the
  owner through his remaining close-out steps: `OWNER-ACTIONS.md` told him to point a cron
  at `POST /api/v1/scrapers/daily` and `POST /api/v1/notifications/run-reminders`, but both
  are `AdminUser`-authed and an access token lives 24 hours. **A cron container has no
  browser, no login and nothing to refresh, so neither endpoint was callable by a scheduler
  at all** — the owner action could not have been completed as written. Batches 11 and 20
  each shipped the endpoint half and left the command half unbuilt.

  `src/scripts/daily_scrape.py` and `src/scripts/run_reminders.py` are those jobs as
  commands, matching the precedent `#60` set with `refresh_completion_sets.py` — whose whole
  point was that scheduling should be *"one console action rather than a piece of
  engineering"*. No new credential (the container already holds `DATABASE_URL` and the VAPID
  keys) and no second authentication path on the API; the endpoints are untouched. A shared
  secret was offered as the alternative and the owner chose the scripts. `DECISIONS.md` #119.

  **The exit code is the behaviour worth testing**, because it is the only thing a scheduler
  reads: a failed retailer exits 1 and names the shop and the reason, a shop that simply does
  not stock a film exits 0, and `--dry-run` is opt-in on the scrape — a nightly job that
  defaulted to writing nothing would be indistinguishable from one that works.

  **One seam moved.** `push_sender` left `routers/notifications.py` for
  `src/services/push_transport.py`, so a scheduled job does not import FastAPI and the whole
  route table to obtain a transport; the router re-exports it and a test asserts the two
  names are one object.

  **CI cannot prove the container runs these**, because it never builds the image — so
  `test_deployment_config.py` asserts the contract they depend on instead: `WORKDIR /app`,
  `PYTHONPATH=/app`, the whole `src/` tree copied, and the command line in `OWNER-ACTIONS.md`
  matching the module that exists. A moved `WORKDIR` would otherwise break both crons
  silently, and the first sign would be a scrape that never ran.

  **Also settled with the owner:** the 300 KB photo target is now a recorded decision rather
  than an inference two docs disagreed about (`#120`), and the owner accepted `#110`'s
  Blu-ray.com risk so §3.7's live run can proceed.

- **2026-09-10** — **Batch 23 built: the Blu-ray.com spec scraper, badges and filters.**
  The last of the overnight run's eight batches.

  **#110's bounds are enforced by the code rather than described by it.** Exact release URLs
  only, with the disallowed search routes refused by name; requests sequential and five
  seconds apart, with an honest user agent and no redirect following, because #110 forbids
  evasion; a `403`, `429` or `451` **halts the whole integration** and abandons the rest of
  the batch. The halt is a database row, not a variable — one held in memory lasts until the
  next deploy, and that is precisely the promise that must not break. **Nothing in the runner
  can clear it**, and a test asserts that, because #110 says resuming needs a new owner
  decision.

  **No price, rating or review is extracted, and the page carries all three in the same
  document.** #108 calls the temptation "unusually close to hand", so the parser reads an
  allow-list of labels, the forbidden ones are named, and a test proves the two sets
  disjoint. The fixture deliberately carries a list price, an Amazon price, a rating and a
  review so their absence is demonstrated rather than promised.

  Two more of #108's measured facts changed the code: **audio is rendered twice** behind the
  `(more)`/`(less)` toggle, so extraction targets DOM nodes and de-duplicates; and **Special
  Features was absent** from a real page, so it is nullable rather than assumed.

  §3.8's badges use three genuinely distinct colours — resolution, HDR and audio are three
  different claims, and a row of identical pills makes them one blur. A disc with no specs
  renders **nothing**, not a grey "unknown": the app does not know until it has asked, and a
  placeholder that looks like data is how a catalogue starts lying.

  **§3.7's acceptance is not done and is an owner action.** It needs a live run against ten
  real URLs on a site whose terms prohibit automated access; #110 is the owner's acceptance
  of that risk rather than a permission an agent inherits, and `group-start.md` puts live
  third-party runs in the owner's hands — which is how Batch 19's checkpoint worked too.
  Production reports **0 pages ever fetched**, and `DELETE /api/v1/specs` is there to make
  the whole thing reversible.

- **2026-09-10** — **Batch 25 shipped: photos of a disc.** Bytes in Postgres, resized before
  they get there.

  §3.10 says Supabase Storage and there is no Supabase project; the owner settled storage as
  Neon, so a photo is a `BYTEA` column served by the API — and a real `item_photos` table
  rather than §3.4's `photo_urls`, which designs a list of *external* URLs there is now
  nothing to point at.

  **The resize is why the batch is shaped like this.** §3.10's raw numbers are 5 MB × 5 ×
  1,857 ≈ 46 GB, in a database that measured **36 MB** live today. A phone's 4032×3024
  photo now stores at about 240 KB — measured in a test rather than asserted in a comment.

  **A disagreement between two in-repo docs, resolved by making it cheap.**
  `OWNER-ACTIONS.md` said the 300 KB cap was "proposed… not confirmed"; `STATUS.md`'s own
  run plan and the batch ledger both listed it as *"(owner, 2026-09-09)"* under "settled
  inputs, so no batch has to ask again". No `DECISIONS.md` entry exists either way. It
  shipped at 300 KB — the number both docs name — with the target as the `PHOTO_TARGET_KB`
  **setting**, so the thing that made it an owner choice ("annoying to reverse once photos
  exist") is no longer true: changing it is one variable and a re-upload.

  **Every upload is decoded and re-encoded.** EXIF orientation applied *then dropped* —
  dropping it without applying is how a gallery fills with sideways shelves; transparency
  composited onto white rather than the default black; and Pillow's pixel ceiling refuses a
  decompression bomb, which is a tiny upload that unpacks to gigabytes.

  **Two blockers turned out not to exist.** Group H said Batches 24 and 25 were "both
  blocked on the same two `vercel.json` fixes". Neither was needed: `camera=(self)` has been
  live since Batch 2, and the photos are served from the API origin `connect-src` already
  allows. **`authFetch` did need a fix** — it forced `application/json` onto every body,
  which for multipart omits the boundary and makes the server parse nothing out of a request
  that looks perfectly normal.

  **Nothing failed in CI.** Green on the first push, 21 new tests.

- **2026-09-10** — **Batch 35 shipped: movie night.** Sessions, an invite URL, a swipe deck
  and match detection over Postgres `LISTEN`/`NOTIFY`.

  **The net-new integration turned out not to be needed.** §8.4 names Supabase Realtime and
  the ledger tiered this batch 🔴 partly for it; `DECISIONS.md` #113 replaced it with
  `LISTEN`/`NOTIFY` and SSE the day before, so it shipped with no new service, credential or
  bill.

  **#113's warning shaped the whole realtime module.** `LISTEN` holds a connection for as
  long as it listens, and taking one from the request pool for a whole movie night exhausts
  the pool and reads as the entire app hanging — Batch 8's paused query in another costume.
  One dedicated connection is opened on the first watcher and closed with the last. Unlike
  #60's cron, two containers is *correct* here: both listen on the same channel.

  **A match is derived, never stored** (gotcha 1b), with `announced_at_utc` the only derived
  state kept so it is announced once. The rule is "everyone here" rather than "two" — free
  now, and the difference between a feature that grows and one with a 2 baked in. **The
  other person's votes are invisible**: the stream says only that *a* vote happened, and a
  card vanishing because they swiped it would leak which way.

  `asyncpg-stubs` went in as a dev dependency rather than a mypy override for the module,
  and immediately earned it: asyncpg's listener callback really takes `object`, not `str`,
  because a binary-mode connection delivers bytes.

  **A stale owner action closed on the way past.** `OWNER-ACTIONS.md` still asked "what
  provides realtime for Batch 35?" — a question #113 had answered as an owner decision the
  day before. Marked done rather than asked again.

  **Nothing failed in CI.** Green on the first push, 16 new tests. §8.4's notification
  *arriving on a device* is deferred with 6.2 and 5.6; the match and both notification rows
  are proved.

- **2026-09-10** — **Batch 32 shipped: voice input.** Stage 9 is complete apart from 9.6,
  which `DECISIONS.md` #16 dropped.

  On-device recognition — the browser's engine listens and nothing is uploaded by this app.
  `microphone=(self)` had been in `vercel.json` since Batch 2, so no hosting change.

  **Dictation fills the input and never sends.** The engine mishears; a button that
  submitted on the last word would put a wrong question to the assistant with no chance to
  correct it, and would also make the acceptance criterion uncheckable — "correct
  transcription" is something only the person can confirm, by reading it.

  **Two things that would have been silent bugs.** TypeScript's DOM library declares none
  of the Web Speech API, so the used surface is declared in-repo rather than casting
  `window` to `any` — which accepts a misspelled event name and yields a mic that listens
  and reports nothing. And interim results are reassembled rather than appended: the engine
  revises earlier entries in place, so concatenating each event produces "where where is
  where is Heat".

  **9.5's acceptance is deferred** — it needs a person speaking into a microphone.

- **2026-09-10** — **Batch 31 shipped: role-aware tools, streaming chat, and confirmation
  before any write.** `fe1db05`. Group J is complete.

  **The agent loop is manual and that is the whole design.** The SDK's tool runner drives
  the cycle in one process; §9.4 requires it to stop, hand a request to a browser, and
  resume when a person answers in a *later HTTP request*. So a pending write is a row, not
  an in-memory future — the latter loses every outstanding confirmation on the next deploy.

  **Every call in a turn gets a row, including the reads.** The API insists one
  `tool_result` message answers all of an assistant message's `tool_use` blocks, so a turn
  that both searches and writes cannot send half an answer while it waits. The read runs,
  its result is held, and both go back once the write is resolved. A cancelled call is kept
  and marked, with a result the model reads as a refusal — otherwise its next sentence
  cheerfully reports success.

  **`DECISIONS.md` #12 stays closed.** Tools dispatch to the same endpoint functions the web
  app calls, which are plain async functions taking `(user, db, ...)`, and results come back
  as the same pydantic models the browser parses. No envelope was needed and none was added.

  **"Write" and "admin-only" turned out to be different questions.** Watch history is
  personal — Batch 6 and Batch 37 both scope it to the caller — so `log_watch` writes and a
  viewer keeps it. One axis would have taken it from Mark for no reason.

  Messages store raw content blocks rather than text, because replaying only the text makes
  Claude answer as though a tool call never happened, silently. `sequence` orders them:
  `NOW()` is the transaction's start time and a turn writes several rows in one (gotcha 24).
  The browser parses SSE with `fetch` rather than `EventSource`, which cannot POST or carry
  an Authorization header, and buffers across chunk boundaries — a frame routinely arrives
  split across two reads, and a parser that assumes otherwise drops text with no error.

  **Nothing failed in CI.** Green on the first push, 34 new tests.

  **A stale number corrected while verifying.** The "what the live database holds" block has
  said 3 `wanted_list` rows since 2026-09-09. It is 11, 8 of them live — the three originals
  were soft-deleted and eight boutique titles added during that evening's acceptance run
  (#111). Confirmed that nothing this session wrote to production: 1,857 items untouched,
  8 `price_checks`, and `ai_usage_log` empty.

- **2026-09-10** — **Batch 30 shipped: the Claude client and the AI usage caps.**
  `ecb00dd`. Group J is half done.

  **The model id is config, validated at load.** `docs/phase-batches.md` warned "do not
  guess a model id" — the April spec predates the current lineup by two generations. The
  validator refuses an id this app has no price for, which catches the *worse* failure as
  well as the obvious one: a wrong id 404s loudly, an unpriced one works and silently logs
  every call as free, and a cost cap counting zeros never fires.

  Two more things the spec could not have known: `budget_tokens` returns a **400** on the
  Claude 5 family (adaptive thinking plus an `effort` level replaces it), and assistant
  prefill is gone, so response shaping lives in the system prompt.

  **§9.7 enforces two ceilings, before the call.** A message count alone does not bound
  spend — the same question costs more at the end of a long conversation. Checking after
  the call would still have spent the money, and a test asserts the model is never reached
  once the cap is hit. A refusal is a 200 carrying the sentence, not a 429. The day is the
  person's local day (gotcha 26), and `cost_usd` holds six decimal places because rounding
  a sub-penny call to cents records it as free.

  **Readiness now reports `ai` alongside `push` and `db`,** and live it says `configured` —
  so the Anthropic key really is in Railway, which is the one thing a green gate could not
  have told anyone.

  **Nothing failed in CI.** All five jobs green on the first push, 34 new tests.

  **§9.1's acceptance is deferred and is a one-minute job.** It needs a live call, which
  spends the owner's money on a key held only in Railway; there is no credential on this
  machine and the deployed endpoint needs a login. Open Assistant in the sidebar, ask one
  question — the token count and cost render underneath it.

- **2026-09-10** — **Batch 20 shipped: the nightly price job, drop alerts and the 90-day
  roll-up.** `464e495`. Group F is complete.

  **§5.6 as written could not be built.** *"Postgres trigger after price_check insert …
  queue push"* — a trigger runs inside the writing transaction and cannot make an HTTP
  request. Batch 11's outbox is the queue it would have needed, so detection lives in the
  scrape path and writes a `deals` notification. `price_checks.notification_sent`, the
  column §3.6 designed for the trigger, is still the flag.

  **Alerts fire on the transition, not the condition.** A price at or below `max_price`
  stays that way until the disc is bought; alerting on it nightly would train the owner to
  ignore the category. A substituted format or edition still alerts and **says so** —
  suppressing it hides a real find, sending it silently lets "Deep Red is £15" mean the
  Blu-ray when the want was the 4K.

  **`scrape_runs` is new, and #112's criterion is unverifiable without it.** The counts the
  corrected acceptance is stated in used to exist only inside one HTTP response. They are
  now a row, with every failure carrying its retailer and reason, and a run that dies
  halfway is visible as a run that died halfway rather than as no run at all.

  **One CI failure, and it was the test that was wrong.** The not-stocked fixture used a
  generic whole-page config to exercise `DECISIONS.md` #107's detection, which only exists
  on the card-by-card path — `extract` says so in its own docstring. Batch 19's conservative
  reading is left alone and the fixture is now card-shaped, which is what every enabled
  retailer is. **Recorded because the gap is real for a hand-configured generic retailer:**
  three correct refusals in a row would auto-disable it.

  Verified live: `021` applied, both new tables present, 8 `price_checks` untouched, the new
  endpoints auth-gated. `scrape_runs` is empty and correctly so — **nothing schedules the
  job**, which is why §5.5's *"first overnight run completes"* and §5.6's *"push on a test
  device"* are both deferred to the owner.

- **2026-09-10** — **Batch 11 shipped: notifications and Web Push.** `36d3efa`, plus
  `69d263e` for the readiness check. First of the eight-batch overnight run.

  §6.1's toggles, digest mode and quiet hours; §6.2's per-device subscriptions and test
  button; §5.11's seeded sale seasons and their pre-sale reminder. Web Push is implemented
  directly on `cryptography` against RFC 8291/8292 rather than pulling `pywebpush` and its
  two companions, so `tests/test_webpush.py` can derive the message keys from the
  **receiver** side — the browser's half of the algorithm — instead of proving only that a
  library agrees with itself (`DECISIONS.md` #115).

  **Everything routes through an outbox**, which is what makes §6.1 checkable rather than
  asserted: a disabled category leaves a `suppressed` row naming itself, an evening alert
  leaves a `queued` row due at 07:00, and digest mode leaves three sharing one push. Quiet
  hours carry an IANA timezone — the one place this app is deliberately not UTC, because a
  22:00 window read in UTC is an hour wrong for the seven months of BST (gotcha 26).

  **A hosting step was removed rather than performed** (#114). The plan had the owner
  setting `VITE_VAPID_PUBLIC_KEY` on Vercel; instead the API serves the public key derived
  from the private half, so the two cannot disagree and push works the moment the code
  deploys. And because the remaining key still lives only in a Railway variable — the TMDB
  shape — `/api/v1/health/ready` now reports `push: configured | not_configured | invalid`,
  loading the key rather than checking that a string is present.

  **Two debts paid.** §12.5's overdue-loan push, unmet since Batch 15, now writes that
  batch's unused `loans.reminder_sent`. Batch 9's dropped onboarding notifications step
  (`#50`) is back against real infrastructure: 7 steps for an admin, 6 for a viewer.

  **Three defects CI caught that the local gate could not.** A partial unique index is not
  an `ON CONFLICT` arbiter unless its predicate is repeated — that took down all seven
  deduplicated paths. `UUIDPrimaryKeyMixin`'s `default=` runs when SQLAlchemy builds the
  INSERT, so a hand-built one sent a NULL primary key. And two assertions read the whole
  `notifications` table, where migration `002`'s seeded profiles mean a reminder correctly
  writes more rows than the fixture creates. All three are gotcha 15: a green local run says
  nothing about SQL.

  **The dependency audit rejected `cryptography` 48.0.1** over PYSEC-2026-3552/3553/3554.
  The `<49` pin that produced it was mine, added so this laptop could install a wheel; it
  was removed rather than defended. The cost is that this machine now runs 48.0.1 while CI
  and Railway run 50.0.1 — recorded as gotcha 28 rather than hidden.

  Verified live, not merely green: `020` applied to Neon with all three tables present,
  every notification route `401` while a made-up sibling `404`s, and `push: configured`.
  **§6.2 is deferred to the owner — it needs two real devices.** A daily cron for
  `run-reminders` is a new owner action.

- **2026-09-09** — **An audit session, not a batch session. Three beliefs about what was
  blocking the queue turned out to be false, and one production outage had been invisible
  behind a green gate.**

  **`TMDB_READ_TOKEN` had never been set in Railway.** The *Add a film* panel reported "TMDB
  search is temporarily unavailable"; TMDB was fine, and both credentials in `.env.local`
  returned 200. `config.py:70` defaults the token to `""`, so the API booted happily and sent
  `Authorization: Bearer ` on every call, which TMDB answered 401 and the routers converted
  to a 502 whose wording claimed transience. The blast radius was every TMDB-backed feature in
  the deployed app. Set the same day, along with VAPID keys and `ANTHROPIC_API_KEY`; Mark's
  PIN was set too, so both profiles can now sign in.

  **The scraper acceptance run had never saved a row.** The setup steps had been done — Arrow
  corrected to `arrowfilms.com`, five shops enabled — but `price_checks` and `wanted_list`
  were both empty, so the criterion everyone believed was met had never been attempted. It has
  now produced its **first real price**: Arrow Video, *Misery Limited Edition 4K UHD*, £25.00,
  an exact 4K match with no substitution, verified independently against the live site.

  **A 4K want answered with a Blu-ray turned out to be correct.** Zavvi has no 4K *Nope* at
  all — searched with and without the format term, the only *Nope* disc on the site is
  `/p/blu-ray/nope/`. The fallback and its `substitutedFormat` flag behaved exactly as #102
  specifies. The bare-title search also returned seven Magic: The Gathering and Disney
  t-shirts, every one correctly refused: the Jaws beach towel case, caught.

  **Three working scrapers had been auto-disabled for telling the truth** (`DECISIONS.md`
  #107). 101 Films, Powerhouse and Second Sight each returned a real catalogue page for
  *Misery*, extraction parsed it correctly, and #96's title rule refused every listing because
  none of them was the film. Three correct refusals read as three failures and switched all
  three shops off. `ScrapeOutcome.not_stocked` now separates "the shop answered and has not
  got it" from "the scraper is broken", read from card counts rather than the rejection
  message — because `check_shape` stops at "no price found" before reaching its title rules,
  and Zavvi's real answer for `?q=Nope 4K` leads with a priceless *Cujo* that would otherwise
  have been filed as a broken selector. The three shops were re-enabled with their counters
  zeroed. **Zavvi still carries 2 strikes** from a genuine throttling failure.

  **Batch 23's source settled and Batch 26 dropped** (#108, #109). Specs are scraped from a
  URL supplied per film rather than from the site's search, which `robots.txt` disallows; a
  real page was measured and returns every field §3.7 asks for. **#108's reasoning that this
  therefore "stays inside what the site allows" was wrong**, and #110 — written earlier the
  same day by a parallel session — supersedes it: absence from `robots.txt` is not
  permission, and the access proceeds as an owner-accepted risk instead. Three constraints recorded: the page also carries
  third-party prices the scrape must ignore, `(more)`/`(less)` toggles duplicate the audio and
  subtitle blocks in the flattened text, and `Special Features` can be absent. Shelf QR is
  dropped — Batch 6's location filter already answers the question it existed for. Ledger
  arithmetic re-derived rather than decremented: **37 batches → 24 sessions**.

  *Storage for Batch 25 is settled as Neon* (owner), meaning photo bytes in Postgres. The
  per-photo cap and Batch 35's realtime provider are both proposed but unconfirmed, and sit in
  `OWNER-ACTIONS.md` rather than being taken silently.

- **2026-09-09** — **Batch 27's security review: no findings at its bar, four real defects anyway.**

  The review you asked for ran against `feat/27-gift-links` before the merge. It verified all
  six intended properties with file-and-line evidence and reported **no security findings at
  its confidence bar** — but it surfaced four real defects, all fixed on the branch before it
  merged:

  | Found | Fixed by |
  |---|---|
  | The retailer-link builder ran **inside** the per-film loop — 50 identical `retailers` queries for a 50-film page, on the unauthenticated endpoint | hoisted; a test asserts exactly one `FROM retailers` per page |
  | **The service worker cached `no-store` responses.** It matched any GET under `/api/v1/` by pathname alone, so a gift page a family member opened was stored for 24h in *their* browser — and the route's own comment claiming the API sets no `Cache-Control` had become false | same-origin only, both capability URLs excluded, comment corrected (`DECISIONS.md` #87) |
  | `Decimal("NaN")` **parses**, so the `<= 0` guard raised rather than being caught — a 500 on an admin field in **Batch 18's already-merged code** | `is_finite()`; tests cover NaN, Infinity and sNaN |
  | `view_count += 1` was a read-modify-write in Python | atomic `SET view_count = view_count + 1` |

  Two things it named as conscious trade-offs rather than defects: the slug is stored in
  plaintext (`DECISIONS.md` #84 — a gift link must be re-shareable, unlike Batch 17's hashed
  feed token), and it transits request logs the way any path parameter does.

  **One process failure worth keeping.** The first review attempt failed before doing any work
  (monthly spend limit) — and I had *already* written "Reviewed" into the ledger and the commit
  message. That claim was corrected in `247ee25` and the branch was held unmerged until a
  review genuinely ran. Nothing is a review until it returns findings.



- **2026-09-09** — **Batch 23's Blu-ray.com risk was accepted explicitly, not explained
  away by `robots.txt`.** The site's Legal Notices prohibit automated reuse even for
  private/internal calculations, which supersedes #108's claim that exact release-page
  fetching is allowed. The owner accepts the practical risk, including the one-time
  1,857-item backfill; #110 keeps exact public release URLs, no site search or authentication,
  sequential rate limiting, indefinite caching, provenance for reversible cleanup, and a
  hard stop on `403`, `429`, an objection or a hosting complaint. Written permission is
  preferable but no longer blocks Batch 23.

- **2026-09-09** — **A want can now name an edition, not just a format.** Arrow sells *Deep
  Red* on 4K three times — plain £25, Limited Edition £25, Arte Originale slipcover £35 —
  and page order decided which a `max_price` alert was about. `wanted_list` gained
  `preferred_edition` (migration `019`, free text, nullable; the table was empty).

  **Naming the edition is also what makes it findable.** #96's rule refuses a title with
  meaningful extra words, so the slipcover listing was being *rejected outright* — *arte*
  and *originale* read as another film. The wanted edition's words now join that item's
  allowed vocabulary. Verified live against Arrow: no edition → the plain £25 4K; "Arte
  Originale Slipcover" → the £35 disc; "Limited Edition" → the £25 LE; "Steelbook" (not
  stocked) → falls back to the plain 4K and reports `editionMatched: false`.

  **The edition never narrows the search.** Measured: edition terms promote Arrow's exact
  listing, but on Zavvi `?q=Alien Steelbook 4K` returns seven steelbooks and no Alien at
  all. It is a selection input, not a search input (`DECISIONS.md` #104–#106).

- **2026-09-09** — **A want for a format now means that format.** Asked how a want for a
  specific version of a film would behave. It mostly did — `preferred_format` picks 4K vs
  Blu-ray vs DVD — but three defects were found underneath it (`DECISIONS.md` #101–#103):

  1. **Every 4K disc also says "Blu-ray"**, and format preference matched on mention, so a
     £19.99 4K combo satisfied a want for the £9.99 Blu-ray whenever it ranked first. A
     listing is now the *highest* format it names, because that is what is in the box.
  2. **A fallback was silent.** When the wanted format was not on the shelf, a different one
     was priced with nothing said — and `max_price` compares against whatever was priced, so
     an alert was either missed or wrong with no way to tell which disc it meant. The run
     now reports the format actually priced and the UI says so.
  3. **A digital want priced a disc.** `download` had no search term, so it fell back to
     "Blu-ray". Worse, it counted as a retailer *failure* — and three consecutive failures
     auto-disables a shop, so a digital-only wanted list would have **switched off every
     enabled retailer in the app**. Digital wants are now skipped, reported separately, and
     never counted against a shop that was never asked.

- **2026-09-09** — **The Test button was sending shops an unfilled placeholder.** Reported
  from the app: *Jaws* on Zavvi returned **The Sheriff of Fractured Jaw (Dual Format
  Edition)**. The cause was the previous fix's own doing — `ScraperTester` built its search
  URL in the browser and replaced `{query}` alone, so the new `{format}` placeholder went
  to Zavvi as literal text and matched a dual-**format** western. An unfilled placeholder
  is worse than a broken URL: it is extra search terms a shop happily matches, so the
  failure arrives looking like a result.

  Fixed at the root (`DECISIONS.md` #99, #100): `apply_search_template` is now the only
  function that knows what a placeholder means, the client sends the **template**
  verbatim, and the server fills it with the same call the runner makes. The test endpoint
  also now passes the expected title, the preferred format and the retailer's host into
  `extract`/`check_shape` — it had been doing none of those, so it priced whichever card
  came first and never applied the same-site rule. **A test is now exactly as strict as the
  run it stands for.** The tester gained a format selector to match.

  Re-verified against the live shops through the fixed path: *Jaws* at Zavvi → the 4K disc
  at £19.99, all five supported shops return the right film, *Heat* still correctly refused.

- **2026-09-09** — **The scrapers now filter on films, not on names.** Reported from the
  app: searching Zavvi for *Jaws* returned **a beach towel**. It passed all five of #79's
  shape rules — the film's name in the title, £17.99, GBP, a zavvi.com URL — so the price
  of a towel was being written as the price of the film. Fixed, and two more found while
  fixing it (`DECISIONS.md` #95–#98):

  1. **Merchandise.** A listing must now name a disc format in its title or URL. Zavvi's
     first twelve results for *Jaws* were towels, jumpers, T-shirts and a resin statue.
  2. **The film the shop does not stock.** Zavvi has no Michael Mann *Heat*, so it returns
     *Heat and Dust*, *The Big Heat*, *Red Heat* and *Step Up 4: Miami Heat* — each sharing
     a significant word, each passing the generous title rule, each a different film. A
     title carrying meaningful extra words, once format and edition wording is removed, is
     now refused.
  3. **Page-wide selectors.** Each selector ran over the whole page independently, so a
     card with no price node paired its title with the *next* product's price. Extraction
     now reads product cards, which also makes `preferred_format` work for the first time:
     101 Films lists *Bad Lieutenant* on 4K and Blu-ray, and the want says which.

  **Verified against the live shops, not only fixtures.** *Jaws* at Zavvi now returns the
  4K disc at £19.99; Arrow, 101 Films, Second Sight and Powerhouse all return the right
  film; *Heat* at Zavvi and *Don't Look Now* at Second Sight are both refused with a
  legible reason. **Two built-in search templates changed** (`{format}`) and every verified
  built-in gained an `item` selector — so **"Apply these selectors" must be pressed again**
  before the next run, or the live retailer rows keep the old config.

- **2026-09-09** — **Supported retailer paths.** Live page-shape checks settled which of
  §5.3's shops can actually be scraped: **five pass** — Zavvi, Arrow (on `arrowfilms.com`,
  its UK storefront; the seeded `arrowvideo.com` is the US site and returned USD, which the
  shape guard correctly rejected), plus three UK boutique labels added as supported
  replacements — 101 Films, Second Sight and Powerhouse/Indicator. **Four are permanently
  unverified and stay listed with the reason**: HMV and CEX disallow the search routes,
  Amazon blocks automated access, Blu-ray.com is a catalogue (`DECISIONS.md` #91, #92).

  **Three real defects were found and fixed on the way, none of which a green gate would
  have caught.** (1) `_same_site` compared the last two labels, so **every `.co.uk` host was
  one shop** — a listing link off `secondsightfilms.co.uk` to any other `.co.uk` site passed
  the guard. Latent since Batch 19 because no `.co.uk` retailer had working selectors; the
  two new UK labels are the first to arm it (#93). (2) Retailer pages return **relative**
  product links, which failed `_write_check`'s `http(s)://` test — so it returned without a
  row while `written` was incremented anyway, and the same-site guard was skipped entirely
  because a relative URL has no hostname (#94). (3) A **dry run** claimed to have saved
  prices, because `written` was incremented outside the `if not dry_run` guard.

  The Retailers page now carries the whole owner checkpoint as buttons — *Add missing
  defaults*, *Apply these selectors*, *Preview live run*, *Run and save prices* — and Wanted
  gained an *Add a film* panel, because step 4 of the checkpoint previously had no UI at all.
  **The checkpoint itself is still open**: no live `dryRun=false` run has happened, and
  `price_checks` is still empty.

- **2026-09-09** — **External calendar subscription deprioritised.** The in-app release
  calendar remains primary; its RFC 5545 feed remains available as optional convenience, but
  Apple/Google device verification is no longer a current owner action (Decision #90).

- **2026-09-09** — **eBay production developer application submitted.** The owner received
  eBay's confirmation that account review is pending and takes at least one business day.
  The owner-side application action is complete; Group I remains blocked until eBay approves
  production access.

- **2026-09-09** — **Batch 37 shipped — on-this-day + rewatch** (`50a4828`). Phase 11.6:
  caller-scoped anniversary memories and high-rated, not-recently-watched suggestions are
  parsed through shared schemas and rendered on the dashboard. The acceptance is proved by a
  date-controlled Postgres test: a watch logged exactly one year earlier appears today; CI
  ran it against Postgres 17. `watch_log` remains empty in production, so the dashboard says
  why it has no memories yet rather than rendering a misleading empty card. The optional
  daily push is still Batch 11's VAPID-key-gated work.

  The first full local gate failed only because `test_health.py` deliberately pins every
  public route and needed the two new endpoints named; fixed without weakening it. The final
  local gate: 301 passed, 250 skipped (no local database URL); CI's five jobs passed,
  including Postgres-backed pytest. No hosting, credential or destructive operation. API
  production health reports the merged SHA with `db: ok`. Dashboard browser automation could
  not run: `agent-browser` is unavailable in this environment.

- **2026-09-09** — **Batch 36 shipped — command palette + keyboard shortcuts** (`1425f91`).
  Phases 6.3/6.4. A Cmd/Ctrl+K modal indexing every page, the admin-only write action, and
  films — reusing Batch 5's `/search` endpoint rather than re-implementing it — plus
  recently-viewed films in localStorage. Ten shortcuts (`g`-chords, `/`, `n`, `?`, Esc) and
  a help modal, centralized in one `useKeyboardShortcuts` hook; `SearchBar`'s pre-existing
  `/` handler now defers to it via a `mcu:focus-search` event instead of the two owning
  the same key.

  **§7.5's `.` shortcut and the palette's "recent AI-assistant conversations" index were
  dropped, not built wrong** — both depend on Batch 31's chat, which does not exist yet.
  Same treatment Batches 8/9 gave dead onboarding steps.

  **Verified live in a browser**: Ctrl+K open, the empty-query page index, fuzzy-filtering
  "wanted" to one result, Enter navigating and closing the palette, Escape closing it, and
  a `g s` chord landing on `/stats` — against the dev server with `VITE_SKIP_AUTH`, since
  the local API wasn't running (no Docker/local Postgres — gotcha 15 again, this time for
  the API itself rather than a migration). **`?` and `/` were not independently
  browser-verified** — confirmed via a raw event listener that this environment's browser
  automation tool cannot synthesize a real `key: '?'`/`key: '/'` keydown (both arrive as
  `key: ''`) — nor was "typing 'blade' surfaces Blade Runner films", for lack of a running
  search backend. All three rest on the batch's 27 new unit/integration tests, which
  dispatch real `KeyboardEvent`s and mock the search endpoint directly.

  No backend, hosting or credential changes; no destructive operation. 547 API tests and
  107 web + 65 shared tests, zero skips. Production serves the merged SHA with `db: ok`.

- **2026-09-09** — **Batch 27 closed out (`888dae7`), after its security review ran.** Gift
  links: a 128-bit slug rather than §3.21's UUID PK or §6.26's 32-bit example; four failure
  modes answering identically; a public response model deliberately unrelated to the admin
  one so no ownership, id, slug or count can leak. **The review found no security findings at
  its confidence bar and four real defects** — a per-film N+1 on the unauthenticated
  endpoint, a service worker caching `no-store` gift responses in a family member's browser,
  `Decimal("NaN")` slipping past a `<= 0` guard in Batch 18's *already-merged* code, and a
  non-atomic view counter. All four fixed with tests before the merge (`DECISIONS.md`
  #83–#87). CI green on `main` (all five jobs); production serves the merged SHA with
  `db: ok`.

  Also corrected here: nine rows of `ARCHITECTURE.md`'s §17 table still read "Not yet built"
  for work this session shipped (rows 5, 9, 12, 16, 19, 27, 42, 43, 44). The close-out step
  that would have caught it — "tick the phase line in the roadmap doc" — has been a no-op
  since Batch 10 removed §16, so eight close-outs in a row skipped it without noticing.

- **2026-09-09** — **Batch 27 built but not merged.** The security review the owner asked
  for was launched and **failed before doing any work** (monthly spend limit), so the branch
  was deliberately held — and a first version of the ledger entry claimed it had been
  reviewed, which was corrected in `247ee25`.

- **2026-09-09** — **Batch 19 shipped — scraper framework** (`bf1b4d5`), **and Group F
  stopped at its checkpoint.** Both of 5.3's and 5.4's acceptance criteria need live
  requests to real shops, which `group-start.md` reserves for the owner — so the framework
  is built and fixture-tested (33 tests) and the runs are handed over. The batch is shaped by
  its own risk note: `check_shape` asserts five properties of every result and discards
  anything that fails, because a wrong selector fetches fine and returns a plausible wrong
  number (`DECISIONS.md` #79). Every built-in reported `verified: false` at the time (#80;
  see #91 for what the live checks later settled). The fetcher
  refuses non-public addresses at every redirect hop — the app's first person-supplied URL
  (#81). CI went red because dependencies are locked with `--require-hashes` and
  `pyproject.toml` alone is not enough.

- **2026-09-09** — **Batch 18 shipped — wanted list and retailers** (`f85aa91`). §3.5 and
  §3.16 built, **paying four debts** from Batches 13, 15, 16 and 17. Two of them surfaced as
  tests that had asserted an absence and now assert the presence — which is exactly why they
  were written that way (`DECISIONS.md` #78). A wanted entry can name a film the collection
  has never seen (#75); `is_active` and `deleted_at` stay distinct (#76); the six seeded
  retailers ship with **no selectors** and say so, because a guessed selector persists a
  plausible wrong price rather than erroring (#77).

- **2026-09-09** — **Batch 17 shipped — release calendar and iCal, closing Group E**
  (`a09c172`). Live ingestion put **32 rows** in `release_calendar`; the re-run was
  idempotent. The `.ics` feed is the app's **first unauthenticated surface**, and its token
  is handled as a refresh token — hashed, rotated, one live per person, revoked-answers-like-
  never-existed (`DECISIONS.md` #71–72). **A security review found a real content-injection
  hole**: a URI property is not escaped, so a newline in `release_calendar.url` injected
  iCalendar properties. Not reachable today; **Batch 19's scrapers would have armed it**
  (#73). The first live ingestion also hit a duplicate-page defect a dry run could not reach
  — gotcha 16 again. **Apple Calendar verification is an owner action.**

- **2026-09-09** — **Batch 16 shipped — watch providers and recommendations** (`d2218ab`).
  Live: *North by Northwest* shows HBO Max plus 6 rent and 6 buy options in GB; 20
  recommendations with 7 flagged as already owned. §7.1 assumed a `streaming_region` column
  that did not exist (#70). **A defect found only in the browser, and it was mine**: a 502
  for a TMDB outage made the page say "waiting for the network" — the endpoint now answers
  200 with an `unavailable` flag, because a status code cannot carry "we are fine, they are
  not" (#68). CI went red on gotcha 21's unpinned-mypy trap and was fixed by needing no
  ignore.

- **2026-09-09** — **Batch 15 shipped — trash, audit UI and lending, closing Group D**
  (`20d1eff`). The permanent delete is the app's first irreversible operation; it gets past
  `003`'s soft-delete trigger with a transaction-scoped `SET LOCAL`, **not**
  `DISABLE TRIGGER`, which is global and would make every delete permanent if a process died
  mid-request (`DECISIONS.md` #64). Proved on live data by destroying Batch 12's leftover box
  set: row gone, cascade fired, audit trail outlived it, 1,857 discs untouched. **"Overdue
  triggers a push" is not met** — push is Batch 11 — and no fake toggle was shipped.

- **2026-09-09** — **Batch 14 shipped — stats, activity feed and export** (`20650b3`).
  Stats at 344 ms median (criterion <1s). **Two of five charts have no data** — `watch_log`
  is empty and no disc carries a price — so they say what they are waiting for rather than
  drawing zeros (`DECISIONS.md` #61). CSV/JSON/HTML export all 1,857 discs; **no
  server-side PDF renderer**, because every option needs system libraries in an image
  Railway builds and CI does not (#62). Downloads go through `fetch` into a blob so the
  token stays out of the URL (#63). Also caught and corrected a false claim in my own
  comment: the collection has **zero** non-ASCII titles.

- **2026-09-09** — **Batch 13 shipped — completion sets, closing Group C** (`22680de`).
  40 sets built live from TMDB, zero errors. Hitchcock 12 of 61, where TMDB returns 129
  crew credits and 65 director ones — the filters that get from 65 to 61 are the batch
  (`DECISIONS.md` #58), because "12 of 91" and "12 of 65" are both plausible wrong numbers
  nothing would flag. Sets are seeded from the collection's own `movie_credits`, so there
  is no name-matching step to get wrong (#57). Ownership is never stored (#59). **"Bulk add
  missing to wanted list" was dropped** — the wanted list does not exist and Batch 18 owns
  it. **"Weekly" is not scheduled**: a Railway cron is a hosting change (#60).

- **2026-09-09** — **Batch 12 shipped — box sets + smart collections** (`881f444`). Three
  tables, seven endpoints, 38 tests. The saved-filter blob is closed off twice: validated
  through a model whose fields are `GET /movies`' own parameters, and *evaluated* by the
  same function that serves `GET /movies`, so a saved collection cannot silently drift from
  the filter bar (`DECISIONS.md` #55). `isComplete` is three-valued — an unrecorded box size
  means unmeasured, not incomplete (#56). `sub_category` deliberately untouched. Driven in a
  browser against live Neon: "Unwatched 4Ks from the 2010s" listed 40 real films. CI caught
  one test of mine that assumed the local catalogue was present.

- **2026-09-09** — **`fix/date-guards-read-the-server-timezone` shipped.** A pre-existing
  red on `main` that no change caused: `date.today()` reads the *server's* timezone, so the
  watch-log default (computed in UTC) and its own future-guard (compared in local time)
  disagreed for the hour after midnight BST. Green in CI all day, red at 00:07 locally.
  Fixed at the root rather than in the assertion — `purchaseDate` carried the same guard,
  and comparing a person's calendar date against any single timezone's "today" is wrong in
  both directions. New `apps/api/src/clock.py`; the ceiling is now the latest date that is
  today anywhere on Earth (`DECISIONS.md` #53). `04bfd44`.

- **2026-09-08** — **`fix/pytest-local-live-data-collisions` shipped — the 4 pytest
  failures Batch 10 flagged are fixed, not just flagged.** Not a scheduled ledger batch;
  closed out on its own branch per the guardrail against folding a pre-existing red into a
  batch. All four were testing the wrong thing rather than merely lacking test isolation:
  one asserted current runtime state (`pin_hash IS NULL`) for a claim that's actually about
  a migration's static seed data, and was destined to fail forever the instant a real PIN
  was set — which happened, correctly, before this fix existed. Rewritten to check
  migration `002`'s seed columns directly, with the migration now exposing
  `SEEDED_PROFILE_COLUMNS` and asserting its `sa.table()` declaration matches it, so a
  future edit adding `pin_hash` to the seed fails loudly rather than silently. The other
  three assumed an empty `movies`/`collection_items` table when filtering by `section` or
  `watched`, and collided with real production rows (38 in "Top Big Cabinet", 413 in
  "Digital", ~1,843 counting as unwatched) the moment they ran against live Neon rather
  than CI's disposable Postgres. Fixed by giving each fixture a shared, implausible `year`
  and filtering on it too — the same narrow-filter-combination convention an existing,
  passing test in the same file already used, not a new pattern invented for the fix.

  All 338 `apps/api`, 26 `packages/shared` and 57 `apps/web` tests now pass locally against
  live Neon — the first time that's been true since these four tests were written. No
  schema change; migration `002` gained a runtime assertion and a renamed constant only.
  Production serves the merged SHA `959b1ca85058daee7b5c2bde5283cbe99d227423` with
  `db: ok`.

- **2026-09-08** — **Batch 10 shipped — the architecture doc is split and its decisions
  table is reconciled.** `MCU_Architecture_v2.1_FINAL.md` (2,639 lines) is now
  `ARCHITECTURE.md` plus an 18-line stub at the old path pointing to it; `§16 Build Phases`,
  an 86-phase plan that named a model ("Sonnet 4.6") which no longer exists, is replaced by
  a pointer to `docs/phase-batches.md` as the roadmap of record. `§17 Resolved Decisions`
  now carries a status verdict on all 50 rows rather than only its original April
  resolution — split into shipped, superseded (with the `DECISIONS.md` # that did it), or
  not yet built. `session-log.md.txt` is retired; its content was entirely superseded by
  the re-scaffold and already reconstructed into `DECISIONS.md` #1–8.

  **This batch had no written acceptance criteria anywhere in the repo when the session
  started** — every other batch has a `### Batch N` section in `docs/phase-batches.md`
  with a `**Goal:**`/`**Acceptance:**`; Batch 10 had only its one-line ledger title. Wrote
  the criteria into the ledger first, from `REVIEW_PLAN_2026-09-07.md` Part C's own words,
  with the owner's agreement, before touching any doc.

  **Two rows of the reconciliation were corrected by reading the code rather than trusting
  the batch log.** The working draft called Sentry, structlog and correlation-ID binding
  "not confirmed built" because no `STATUS.md`/`DECISIONS.md` entry claims them. All three
  are actually wired — `sentry_sdk` in `apps/api/src/main.py`, `@sentry/react` in
  `apps/web/src/instrument.ts`, and `structlog.contextvars` bound to `correlation_id` in
  `apps/api/src/middleware.py` — found by grepping the source before finalising those two
  rows. Web Vitals is genuinely absent, and stayed marked as such.

  **Four `apps/api` pytest tests fail locally against live Neon data** — real production
  rows they weren't written to tolerate (a real PIN where one asserts `None`, 1,857 real
  movies swamping a section-filter assertion). Confirmed unrelated to this batch: zero diff
  in `apps/`/`packages/` against `main`, and this batch's own CI run — against CI's
  disposable Postgres, not live Neon — was green. Left unfixed per the guardrail against
  folding a pre-existing red into a batch; flagged in "Next" as worth its own `fix/` batch.

  Production serves the merged SHA `d94a6b828d5e96879b5794d4d11bb308ac01803c` with
  `db: ok`. No migration, no hosting or credential change, nothing destructive.

- **2026-09-08** — **Batch 9 shipped, and Group B is complete.** Batches 7, 8 and 9 all
  landed today, which finishes the "build to first deployment" half of the ledger: the
  collection can be written to, it works with the network off, and a first-time user is
  shown a setup flow whose every step does something.

  **The wizard is rebuilt, not repaired.** Batch 3 had removed it because its completion
  flag was a Supabase column that no longer exists (`DECISIONS.md` #27), so there was
  nothing to repair — migration `010` gives it a real one and `ProtectedRoute` gates on it
  again, closing a TODO it has carried since Batch 3.

  **Half the batch definition's premise was wrong.** It says `StepInstallPWA` and
  `StepNotifications` "now have real infrastructure behind them". The install step does —
  Batch 8's manifest and service worker let `beforeinstallprompt` fire, and the new
  `usePwaInstall` catches it, preventing the default because Chromium gives no second
  chance. **The notifications step does not**: no VAPID key, no subscription, no endpoint,
  no `push_subscription` column, and six toggles for features that do not exist yet.
  Dropped rather than ported (`DECISIONS.md` #50); Batch 11 owns bringing it back with
  infrastructure first.

  **A fourth dead step that gotcha 5 never listed** — the catalogue step read
  `d?.meta?.total`, the envelope `DECISIONS.md` #6 deleted, so it rendered a loading
  skeleton for ever. A dead read can hide behind a plausible loading state indefinitely,
  which is why "no step reads a property nothing sets" was worth checking by grep rather
  than by looking.

  Verified by walking the production bundle in a browser: six steps for an admin, resuming
  at step 3 after a reload, and "Skip setup" landing on a usable `/movies`. 249 API tests
  and 83 web/shared tests, zero skips.

- **2026-09-08** — **Batch 8 shipped — the app works with the network off.** Service
  worker, manifest and icon set, an offline banner, and a durable IndexedDB write queue
  with the two states that make it safe: a write the browser never sent is re-sent
  automatically, and one that left without an answer is *read back*, never re-sent.
  Ported from `the-coupon`'s `usePickEditor` — its reasoning transfers even though its
  storage does not, and `DECISIONS.md` #44 records why this one persists where that one
  deliberately does not.

  **Two spec facts did not survive checking.** Phase 13.9 specifies last-write-wins, which
  is the exact opposite of this batch's own acceptance criterion — a queued edit flushed
  on reconnect *is* written last. Replaced by an optimistic-concurrency check (#42).
  Phase 6.5's acceptance names the wanted list, which is Batch 18 and does not exist.

  **Four defects, none visible to any green check, all found by driving the built app
  against an API that could be switched off.** React Query *pauses* mutations when it
  believes the app is offline, so `mutationFn` never ran and the queue inside it was
  unreachable — the offline write path was dead on arrival, behind a spinner that could
  not stop. The same pause stops a query issuing the fetch a service worker exists to
  answer, which is gotcha 19's empty-state lie seen from the other end. A 5xx on a write
  was treated as a refusal and the write discarded. A 5xx on the profile load signed the
  person out and destroyed the session the queued writes were made under. And
  `updated_at` used `NOW()` — transaction time — so the new concurrency token never
  advanced and the guard passed anything, which this batch's own CI tests caught failing
  *open*.

  **Criterion 3 is proved end to end in a browser**: the edit queued while offline, and on
  reconnect the server received exactly the queued body with its `baseUpdatedAt` attached.
  Criteria 1 and 2 need a phone — see gotcha 25.

  337 API tests and 77 web/shared tests in CI, zero skips. 1,857 items untouched.

- **2026-09-08** — **Batch 7 shipped — the collection stops being read-only.** Add, edit,
  soft-delete and restore, with duplicate detection and condition tracking, and an
  `admin_actions` row written in the same transaction as every change. Migration `008`
  creates the audit table, which **did not exist on the new spine** — gotcha 4's
  speculative-table warning running the other way.

  **The batch's headline criterion is proved by destroying a row.** "The audit log
  survives deletion of the target" cannot be shown by a soft delete, and
  `collection_items_soft_delete` rewrites every `DELETE` into one — so the test disables
  the trigger, genuinely deletes the item, and shows the entry still readable through
  `GET /admin/audit`. `target_id` is TEXT with no foreign key (`DECISIONS.md` #5, #38),
  which is where §3.20's schema table is wrong and the decision is right.

  **Three scope calls, all recorded** (`DECISIONS.md` #37–39): writes are admin-only, as
  §3.1's own acceptance criterion requires; optimistic UI is Batch 8's phase 6.5, not
  this batch's, because building rollback here would mean building what Batch 8 explicitly
  rejects; and the trash ships without permanent delete, leaving the one irreversible
  action with §13.5.

  **`UtcDatetime` was written for real** (#40). `AGENTS.md` has specified it since the
  re-scaffold and nothing implemented it — #14's warning found inside our own conventions
  file. It went unnoticed because Batch 7 is the **first batch to put an instant on the
  wire**: Batch 6's `watchedAt` is a `DATE`, which has no offset to get wrong.

  **Two defects that a green gate could not have caught, and how each surfaced.** A
  `field_validator` that never ran for an absent field turned a malformed body into a 500
  — caught in CI by this batch's own test, which is what those tests are for. And every
  list page claiming to be *empty* when its request had merely been paused — caught only
  by opening the pages in a browser, with the build, the types and 34 web tests all green
  (gotcha 19). The second is fixed app-wide and matters most for Batch 8.

  Also fixed on the way: two test clients sharing one actor, because
  `app.dependency_overrides` is global to the app and the admin and viewer fixtures
  overwrote each other — which would have made §3.1's "viewer immediately sees it" look
  tested without being tested.

  331 tests in CI, zero skips. 1,857 collection items untouched.

- **2026-09-08** — **Batch 6 shipped — the app finally answers "where is this disc?"**
  §6.2's promise has been in the architecture doc since April and unimplementable until
  Batch 4 added the columns; this batch is the first thing to query them. `section`,
  `shelf`, `decadeFrom`, `decadeTo`, `minRating` and `watched` on `GET /movies`, a
  facet endpoint serving the vocabularies from the data, and location on all three
  collection views. **Front 2nd shelf answers in 20 ms** including network — 0.4 ms
  execution on `ix_collection_items_section_shelf_live`, the index Batch 4 created for
  exactly this query and which nothing had used until today.

  **Two premises in the batch definition did not survive checking, and both were settled
  with the owner before any code was written.** "Watched status" was listed as a facet
  beside decade and rating as though the three cost the same. They did not: §3.7 designs
  `watch_log` and §6.5 lists its endpoints, but **no phase in §16 creates it** — checked
  against all 96 phase headings — while Batch 37 sat defined as "inert until `watch_log`
  has ~a year of history", waiting on a table nothing brought into existence. Built here
  (#35), which moved the batch 🟢 → 🟡 and unblocked Batch 37 as a side effect. And the
  124 unsectioned rows, which `STATUS.md` had flagged as this batch's open question,
  turned out to be four named cabinets covering 122 of them — now in the vocabulary and
  backfilled (#34), taking sectioned coverage from 1,733 to **1,855 of 1,857**.

  **Two real defects found on the way, neither of them in this batch's own code.** The
  shelf parser matched any bare digit, so `Top small cabinet (Arrow 4 Film Noir Classics
  Vol 2)` had been stored as shelf "4th" for four live discs — rows this batch's own
  shelf filter would have wrongly returned. `Back 6th Shelf (Arrow 4 Film Noir Classics
  Vol 1)` escaped only because `re.search` returns the leftmost match (#36, gotcha 17).
  And the year filter in `FilterBar` was generated from 1970 forward, so **517 of the
  1,085 dated films — 47.6% — could not be selected at all**; the decade range replaces
  it with bounds taken from the data.

  **The gate was green on the first CI run**, 296 API tests against Postgres 17 with zero
  skips, all five jobs passing. Because migration `007` writes to 126 live rows, close-out
  stopped for owner sign-off rather than deploying itself, per the protocol. Before asking,
  `007`'s own `WHERE` clauses were run as read-only `SELECT`s against live Neon and matched
  the parser exactly; the post-deploy counts then matched that prediction row for row —
  38 + 38 + 26 + 20 sectioned, 4 shelves cleared, 2 correctly left alone, 1,857 items and
  1,843 films unchanged. **CI cannot prove a backfill, because its migration job runs on an
  empty schema** (gotcha 18).

  **One acceptance criterion is proved indirectly, exactly as in Batch 5, and for a
  narrower reason.** The browse UI is covered by CI contract tests, by direct measurement
  against the production database, and by booting the built bundle with zero console
  errors — but **not by driving the production UI**, because that needs a PIN and an agent
  must not type one. Craig's PIN is now set, so this is a one-minute owner check; Mark's is
  still `NULL`.

- **2026-09-08** — **Batch 5 shipped — the collection is browsable, searchable, and every
  unidentified film can be settled from its own page.** List, detail, copies and tsvector
  search ship with camelCase DTOs and shared zod schemas the web app genuinely `.parse()`s
  — zero `as Promise<T>` casts. Migration `005` completes the search document that `003`
  deliberately left half-built, adding credited names and genres and re-firing when credits
  change, so a film identified in the app becomes searchable immediately.

  **The identify flow replaces the review CSV** (#33). `GET /movies/{id}/candidates` runs
  the existing `MatchingEngine` live against the stored spreadsheet title and returns the
  top five with posters, years and overviews; `POST /movies/{id}/identify` fills the §3.2
  columns and the credits. It needed no schema change — the unidentified set is exactly the
  757 movies with `tmdb_id IS NULL`, and all 757 still carry the title to search on. Either
  user can identify a film, and the same picker corrects the four wrong-sibling matches, so
  the matching ranking was left alone.

  **Measured against production, not asserted.** Search median **20 ms** and a 60-item list
  page **23 ms** against live Neon with network included — the <150 ms budget was never
  close. Zero of 1,843 movies are missing a `search_vector`. The metadata-only criterion was
  proved with **"Kubrick": 8 films returned, and the word appears in no title in the
  collection**, so the hit can only come from fetched credits; genres index too. Production
  serves the merged SHA with `db: ok` at migration 005.

  **Two failures on the way.** CI went red on run `34227781888` — the `search_vector`
  trigger could not expand `genres` when SQLAlchemy had serialised Python `None` as the
  JSON scalar `null`, which is not SQL NULL and cannot be treated as an array; `005` now
  guards on `jsonb_typeof(...) = 'array'`. Run `34228015029` was then green with 269 API
  tests and no skips, including the 16 derived-trigger tests. During close-out the local
  verification script also failed twice on its own errors — a `release_date` column that
  does not exist (it is `year`) and psycopg2 reading `%` in an `ILIKE` pattern as a
  parameter placeholder. Neither touched the app.

  **One acceptance criterion is proved indirectly, and it is worth naming.** Both profiles
  still have `pin_hash = NULL`, so nobody can log in and every read route requires
  `CurrentUser`. The deployed app boots and renders its login page with no console errors,
  but the browse grid, detail page and picker were verified by CI integration tests and by
  direct database measurement — **not** by driving the production UI. The 60fps figure in
  particular rests on all three views being virtualised with `@tanstack/react-virtual`,
  not on a frame-rate measurement. Setting the PINs closes it.

- **2026-09-08** — **Batch 4 shipped — 1,857 discs are in the database, with structured
  location, for the first time.** Migration `003` lands the §3.4 domain schema and `004`
  two fixes the live import forced. All four acceptance criteria proved against the live
  database: 1,857 `collection_items` with 1,857 distinct `import_source_row` and zero
  errors; 1,733 sectioned with zero values outside the §3.4 vocabulary; the dry run
  diffed against `matching_eval.csv`; and **14 derived-field trigger tests running in CI
  with zero skips** — the criterion Batches 2 and 3 could only defer. 1,843 movies and
  45,144 credits alongside, with `search_vector` and `best_format_owned` populated by
  trigger over real rows. 764 rows are catalogued but not yet identified and sit in a
  review queue that lists every tied candidate.

  Three decisions were taken with the owner before or during the work: §3.4's schema over
  the April one, which forced the trigger tests to be re-authored rather than resumed
  (#28); the collection is **1,857 items, not 1,866** — nine trailing spreadsheet rows are
  blank, so the number was wrong everywhere it appeared, Phase 1.5's acceptance included
  (#29); and an ambiguous match is catalogued but not enriched, which meant changing the
  matching engine against this batch's own "port `matching/` unchanged" instruction (#31).

  **Four defects, three of them invisible to a green gate.** Criterion 3 stopped the batch
  for a day when a fresh matching run against `matching_eval.csv` showed `Amistad`
  resolving to `Friendship (2023)`; a full scan found 652 rows (35%) whose film was chosen
  by TMDB popularity alone. Then the live write found three more that no test could have
  caught: the importer could not connect to any hosted database, a 300-character
  `character_name` overflowed its column and rolled back a whole item, and an idempotency
  key on item contents collapsed "French Connection" and "French Connection 2" into one
  disc. Gotcha 16 records the general lesson; #32 records the fixes.

- **2026-09-07** — **Batch 3 shipped — Craig and Mark can log in; nobody else can.**
  `main` `e89a9c6`, CI green, production serving that SHA and the deployed web app rendering
  for the first time. bcrypt PINs, HS256 access/refresh on separate secrets, rotated
  SHA-256-hashed refresh rows, durable Postgres lockout proved by 9 CI tests that dispose the
  engine between writes. Migration `002` seeds both profiles with `pin_hash = NULL`; the first
  PIN is set by `src/scripts/set_pin.py` from a hidden prompt (`DECISIONS.md` #25). Removed
  the sign-up page outright and the onboarding wizard with it (#27), and closed a hole where
  `VITE_SKIP_AUTH` was honoured in production builds (#26). Two CI failures on the way, both
  migration defects a green local gate could not see: the `user_role` enum created twice, then
  the seeded role sent as varchar to an enum column.
- **2026-09-07** — **Batch 2 shipped — the app is deployed for the first time.**
  `main` `d4190ac` pushed, CI green. Railway `api` live on the root Dockerfile; migrate-on-boot
  applied `001` to Neon; `/api/v1/health` returns the merged commit SHA and `/ready` reports
  `db: ok`. Public API `api-production-a8fe.up.railway.app`. Two failures on the way: the
  first deploy built `0419cb2` and failed on a missing Dockerfile because `main` had been
  merged locally but never pushed; the generated domain then returned 502 until repointed
  from port 8000 to Railway's injected 8080. Vercel git-connected; web ships without auth
  env vars and white-screens until Batch 3 — verified in a browser, the console throws the
  expected `Missing VITE_SUPABASE_URL` and nothing else. A third failure found during
  verification: `FRONTEND_ORIGIN` pointed at `mcu-app.vercel.app`, an unrelated third
  party's app, because Vercel had actually assigned `mcu-app-fawn.vercel.app`. CORS now
  allows the real origin and returns 400 to the stranger (`DECISIONS.md` #20–#23).
- **2026-09-07** — Batch 2 implementation prepared for review on
  `feat/2-deploy-spine-ci`: dedicated Neon Postgres connection verified; migrate-on-boot
  Dockerfile, Railway IaC, Vercel configuration, reversible `001`, commit/readiness health
  checks, Postgres-backed CI and hashed dependency gates added. Fresh-lock and disposable-
  Postgres verification green. No commit, project creation or deployment yet; those wait
  for explicit `/phase-closeout 2`.
- **2026-09-07** — Batch 1 New spine foundations shipped via PR #1 (`0910428`, `15ed148`). Async SQLAlchemy/asyncpg, fail-closed config, `models/` mixins, health-only API, async pytest harness and the first shared Zod response schema are on `main`. CI green after fixing a test that assumed pytest always started at the repo root.
- **2026-09-07** — Cross-project review complete, Parts A–E. Merged to `main` as `9084ec6`, CI green (API + Web). 38 batches in 11 groups defined; owner reinstated all Part D drops except 9.6 (`DECISIONS.md` #16). Repo confirmed **private**, which lowers the urgency on the PAT still in history.
- **2026-05-05** — Phase 3.1 Add to Collection (manual). Commits `13d5f6b`, `fe7e895`. CI green. Close-out docs were written but never committed until today.
- **2026-04-30** — Phases 2.7, 2.8 (movie detail tabs; onboarding wizard).
- **2026-04-29** — Phases 2.2–2.6 (frontend shell, collection grid, view toggle, search, detail page).
- **2026-04-25 → 04-27** — Stage 1 (Alembic schema, TMDB client, spreadsheet parser, matching engine, bulk import, derived-field triggers). The real collection import landed 2026-04-27.
- **2026-04-20 → 04-24** — Stage 0 (scaffolding, backend, frontend, Supabase auth, CI, error tracking).
