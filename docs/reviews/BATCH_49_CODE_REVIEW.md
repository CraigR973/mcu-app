# Batch 49 — Code and architecture review (wave 2, pass R1)

**Pass R1** · reviewed SHA `1668071` · lens: senior software engineer · read-only · paid calls: none.
Probes ran in a throwaway clone of the review worktree against a throwaway local Postgres 16
(pgserver, `pg_trgm` and `unaccent`); production was read only through `mcu_readonly`.

## 1. Summary

Grade **B+**. The +109k lines bought real features with tests that bite: all twelve revert-the-fix
probes across ten risky fixes fail when the fix is removed, the 30 migrations are reversible and
grant both read roles in guarded blocks, and no new god-module appeared. The weakness is the one
wave 1 named: **fixes land per site, so two of wave 1's root causes came back as a class in new
code** (an error handler that crashes after its own rollback; a fifth title rule), and "data found
for the film it was" is kept honest by three different mechanisms with gaps between them.

1. **Correct and safe:** yes on every path probed, except one error path (CR49-01, proved) that
   would abort the whole 08:00 job and repeat each morning.
2. **Honest:** the cinema run's `partial` status is constant, so the job's own outcome says
   nothing (CR49-04); a corrected film can keep sold-price evidence of the old film (CR49-02, latent).
3. **Doing its job:** Movie night, trips, the digest and Needs you hold their state across a retry,
   a second tap and two people (section 5, near-optimal).
4. **Failure noticed:** the error path in CR49-01 leaves no row and nothing watches the reminders job.
5. **Cheap to change:** module sizes are fine (four functions over 150 lines); the cost is in
   per-site rules that every new feature must remember to join (CR49-02, -03, -05).

## 2. Findings

### CR49-01 — Med-High — The weekly Letterboxd sync's error handler crashes after its rollback and takes the rest of the 08:00 job with it
- **Evidence:** `proved` — in a throwaway clone, two profiles that exist before the job's session
  starts (as Craig's and Mark's do), and the first person's `sync_watch_history` raising an
  unexpected error. `sync_due` rolls back, then its own log line reads `person.id`; the rollback has
  expired the row, the read needs the database, and async SQLAlchemy raises `MissingGreenlet`. The
  original error is masked, the second person is never synced, and the exception leaves `sync_due`.
  `implemented`: `run_reminders._run` calls `sync_due` with no guard, before push delivery, the
  reminders heartbeat, the cinema programme refresh and the cinema digest, so all four are skipped.
  The person's run row was only flushed, so the rollback erases it: no trace, and the person stays
  "due", so the same crash recurs every morning. This is wave 1's CR43-02 / garmin-coach CR236-01
  pattern; X9 fixed it at the identify site only. `observed`: it has not happened (7 syncs, all fine).
- **What the user or operator experiences:** after any unexpected import error (a constraint, a bug
  in a new matcher rule), mornings go quiet: no cinema listings refreshed, no digest, the daily
  check's pushes queued but not sent by this job, and the job exits non-zero on Railway where
  nothing reads it (L3). Craig finds out from a missing digest.
- **Fix and cost:** capture `person_id` (and display name) before the `try`; record the failure on a
  committed run row; wrap `sync_due` in `_run` as the cinema phase already is ("never roll back
  reminders"); add a test that injects a failure for the first of two pre-existing people and
  asserts the second syncs and the job carries on. Add a repo-wide test or lint rule: no ORM
  attribute read in an `except` block after `rollback()`. About half a day.
- **Where it goes:** new row in the wave 2 remediation group, first sitting; not fast lane (latent).

### CR49-02 — Medium — "Found for the film it was" is enforced three ways, and the gaps between them are unguarded
- **Evidence:** `implemented`, `computed`. After a film's match is corrected, derived data is kept
  honest by: (a) an identity stamp on the row (IMDb ratings: `imdb_ratings_id == imdb_id`, the
  self-healing kind); (b) a time rule (disc values due when `checked_utc < last_tmdb_sync_utc`);
  (c) the audit-derived `latest_corrections()` (reviews #378, disc specs #380, each found by Craig
  after the fact). Not covered: the eBay sold-price store (`ebay_used_listings` keep their
  `movie_id` for 90 days and feed `sales_price`, the effective value once three sales exist);
  rule (b) is defeated by an undo, which restores the old `last_tmdb_sync_utc`, so a value priced
  under the wrong film stays up to 30 days; `letterboxd_slug` is snapshotted and restored but
  written by nothing (0 of 2,363 rows) and still sent on the wire. `computed`: today 0 sold listings
  predate their film's correction and 339 values sit on corrected films, none older than the
  correction, so no live harm yet.
- **What the user or operator experiences:** nothing today; the next correction made after sold
  listings accrue would value the film on the old film's sales until they age out.
- **Fix and cost:** one mechanism: stamp each derived row with the TMDB id it was found for (as
  IMDb ratings do) and treat a mismatch as "not found", or one `identity_changed(movie)` hook that
  identify, undo and merge call and every consumer registers with, plus a test that lists every
  table with a film id and fails on any not registered. One to two days; retire (b) and (c) into it.
- **Where it goes:** new row after CR49-01; R4 owns which corrected films are wrong today.

### CR49-03 — Medium — Wave 1's single title rule (CR43-03) gained a fifth rival in the cinema code
- **Evidence:** `proved` — the cinema matcher's `same_title`/`normal` (AC3) and X10's
  `title_key.same_title(WORDS)` driven with 15 crafted pairs disagree on 12: the cinema rule misses
  "Cowboys v Aliens" / "& Aliens", "Dune: Part Two" / "Part 2", "Rocky II" / "2", "Vol." / "Volume",
  "Ocean's Eleven" / "11"; X10's misses "Spider-Man" / "Spiderman". `implemented`: the cinema rule
  also decides which Archive films a listing is compared with (`cinemas/films.py`), and the guard
  wave 1 named (`test_title_key.py`) imports a fixed list of seven sites, so a new site is
  invisible to it. `observed`: of 145 unlinked or review cinema films, none is a numbered-title miss
  today.
- **What the user or operator experiences:** a sequel or "Part II" rerun listed with a numeral
  spelled differently from TMDB stays unlinked: not merged across chains, not tied to an owned copy.
- **Fix and cost:** build the cinema rule on `title_key.fold` (its own extras, such as "+ Q&A", stay
  on top); add the cinema site to the pair table; make the guard structural (no
  `unicodedata.normalize` outside `title_key.py`, allow-listed). Half a day.
- **Where it goes:** new row; R4 checks the live listings it would relink.

### CR49-04 — Medium — The cinema run's status is `partial` by construction, so it carries no signal (L2)
- **Evidence:** `implemented` in `cinemas/refresh.py`: a run is `partial` when any venue's complete
  dates differ from the 14-day window, which Vue's two-day reads make true every day; `healthy` is
  unreachable. The heartbeat records the same word. `observed`: 14 of 14 runs `partial`, including
  the nine with no failed venue; P1's five failed runs looked identical. Separately,
  `metadata_is_paused` reads every run's full `report` JSON each morning (bounded only by
  `limit(10000)`), a cost that grows with the table.
- **What the user or operator experiences:** P1: four cinemas dark for five days, unnoticed.
- **Fix and cost:** judge each venue against what its source can read (Vue: two days), keep
  `failedVenues` as the alarm figure, and give the daily check a cinema row. A few hours.
- **Where it goes:** the P1 fast lane (#381, in flight; drift, not judged here) or R2's noticing row.

### CR49-05 — Low — A merge moves a hand-kept list of tables; later tables are not on it
- **Evidence:** `implemented`: `move_references` moves 12 kinds of row by name; the source film is
  then hard-deleted. `cinema_films.movie_id` (AC3, `SET NULL`) is not on the list, so a merge
  silently unlinks a cinema film the merged-away row was agreed to be; the cascades drop its values,
  sold listings and reviews, which an undo cannot restore. No test enumerates foreign keys to
  `movies`. `observed`: 12 merges since 11 Oct; impact on cinema links not measured.
- **Fix and cost:** a test that walks the metadata for every foreign key to `movies.id` and fails
  unless it is moved or listed as deliberately dropped; add `cinema_films`. Two hours.
- **Where it goes:** fold into CR49-02's row.

## 3. Follow-through corrections (rows of the pack's table in this lens)

| Row | Pack says | Corrected to | Evidence |
|---|---|---|---|
| CR43-02 | fixed | fixed at the identify site; class recurred in the Letterboxd weekly sync (CR49-01) | proved |
| CR43-03 | fixed | fixed for seven sites; the cinema code added its own rule (CR49-03) | proved |
| Guard 4 | run loops survive an injected failure | covers identify, series, recheck; the Letterboxd weekly loop has only a happy-path test | implemented |
| Guard 6 | one title-key table | a fixed list of sites; cinemas not on it | implemented |
| Guard 1 / CI counts | 2,855 passed, 0 skipped | holds; local run 2,845 passed, 9 skipped (need a `localhost` host), 1 failure my own two databases caused (a role left by `test_backup_restore`) | proved |
| ab2 `ownedWatchedMovies` | R1 to check | holds: optional in the shared schema, the ledger says "Unavailable" when absent; no schema is `.strict()`, so an older client ignores new fields | implemented |
| L2 | `partial` permanent | confirmed (CR49-04) | implemented, observed |

**Revert-the-fix (all in the throwaway clone; fails = good):**

| Fix | Core removed | Tests |
|---|---|---|
| #378 reviews re-lookup | forgetting corrected films' reviews | 3 fail |
| #380 disc specs re-lookup | forgetting corrected films' discs | 3 fail |
| #377 night just started | the night read at the tap | 2 fail (web) |
| X1 mark | read ignores a future mark / mark = pass start | 1 / 4 fail |
| X5 year rule | a known year never excludes | 2 fail |
| AC3 famous classic | "others obscure" / "unread votes" guards | 1 / 2 fail |
| AC5 revision | the trip revision check | 1 fails |
| AC6 claim timing | quiet hours, baseline, a return's first listing | 1 / 1 / 1 fail |
| AE7 whole words | strict word similarity for "close" | 1 fails |
| AF1 App rows | App rows on top of Home's five | 1 fails (web) |

## 4. Queued and parked items in this lens, re-verified

| Item | Verdict |
|---|---|
| Batches 24, 29, 37 ledger headings | accurate: 24 still 🟡 (Craig's physical checks), 29 and 37 🟢; nothing to re-plan in code |
| X12c tidying (CR43-08) | accurate: no stale agent-doc claims found in this pass |
| Onboarding more people | not in code yet; CR49-02's single mechanism should land first, as a third person multiplies corrections |

## 5. For reconsideration · Hypotheses · Limitations · Probe log

**Near-optimal, leave alone:** trip writes (row lock plus revision, 409 on a stale reply); AE10's
match logging (row lock, logged once, and a Letterboxd entry claims the app's viewing instead of
doubling it); the digest's claim and delivery split; the eBay pass's error path (run id taken first,
fixed as a class within that module); migrations 049–078 (CI reverses them; every new table granted
in one guarded block). Size: four functions over 150 lines (digest `evaluate` 228, identify
`_decide` 169, cinema `promote` 165, digest `_claim` 159); `web/lib/api.ts` is 218 thin fetchers.

**For reconsideration:** none of #250–#380 is re-argued. #378 and #380 state "a merge is not a
correction"; true for the kept row, but CR49-05 shows the merged-away row's cinema link is lost.

**Hypotheses:** a deploy where Vercel goes live before Railway would briefly fail any screen whose
new schema field is required (not probed). `cinema_digest/delivery.py` imports a private helper
from `notifications.py`, a coupling a refactor could break silently.

**Limitations:** no Railway reads (token rejected), so CR49-01's exit code was not checked live; e2e
not run (CI ran it green at `1668071`); web tests run only for the two web fixes.

**Probe log:** production, all through `mcu_readonly`, projected: 1 count of Letterboxd slugs; 2
joins of corrections to sold listings and values (counts only); 3 cinema-film counts and one title
list (titles only); 1 movie-night status count. Local: full API suite twice, 14 revert or crafted
probes, one throwaway clone with `pnpm install --offline`. Outside calls: none. Paid calls: none.
