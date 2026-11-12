# Watch-history recovery proposal — 12 Nov 2026

**For Craig's decision. Nothing has been written, fetched or applied.** Live rows were read
19:44–19:52 UTC on 12 Nov through the read-only role. Sources: `docs/reviews/outstanding-work-reconciled-2026-11-08.md`
§1, `OWNER-ACTIONS.md` 1j and X5 in `docs/phase-batches.md`.

## Answer

- **635 watches are ready to write: yours 480, Mark's 155.** Each was re-checked against
  today's rows: no duplicate, no missing film, no target in the Trash.
- All 7 saved corrections are still valid. 101 doubtful entries need judgement, and 14 of
  those are now plain.
- **No new Letterboxd read is needed.** The diary files and the feed overlap for both of you,
  so every unrecorded viewing is already in the saved plans.
- There is no deadline. Mark's first sync on 10 Nov removed the only time limit, while his
  feed still reached 13 days back into his diary file.

## Risks

- **What you will see change.** Your "films watched ever" goes from 501 to 925, and Mark's
  from 918 to 1,062. 421 films join the catalogue as watched but not owned. They show in
  search and on person pages, never in collection counts or value (#269).
- Movie night's "in neither diary" pool loses 88 owned films. One of you has seen each of them.
- The diary files date from 15 Sep. An edit or deletion made on Letterboxd since then to an
  older entry won't show. Where Mark's file and feed overlap, 13 of 13 entries were unchanged
  (same date, title and year).
- Each person's apply is a single database transaction. A dropped connection writes nothing,
  and a re-run is safe.
- Until these entries are written, the only copy the project knows of is the gitignored
  folder on your Mac.

## What would be written

### Yours: 480 watches

| Where each watch lands | Watches | Films |
|---|---:|---:|
| A film already in the catalogue, as planned on 14 Oct | 57 | 41 |
| A film added since 14 Oct, found by its TMDB id | 17 | 15 |
| A new film row, filled in from TMDB | 406 | 371 |

They were watched between Dec 2013 and Feb 2026. 136 carry your rating, 53 are rewatches, and
71 land on films you own today.

### Mark's: 155 watches

| Where each watch lands | Watches | Films |
|---|---:|---:|
| A film already in the catalogue, as planned on 14 Oct | 56 | 52 |
| A film added since 14 Oct, found by its TMDB id | 22 | 20 |
| A new film row, filled in from TMDB | 77 | 73 |

They were watched between Nov 2022 and Aug 2026, and 76 land on films he owns today. 28 of his
73 new films are also in your set, so if his apply runs after yours it adds only 45.

**In total: 635 watches and 416 new film rows** (421 with the corrections). The new films
bring about 18,000 cast and crew rows, at today's average of 42.5 per film.

### Checked against today's rows

- **The recount matches the apply's own check:** by Letterboxd viewing id, soft-deleted rows
  included. You have 480 absent, unchanged since 8 Nov. Mark has 155, down from 158, because
  his 10 Nov sync wrote 3, each on the film the plan chose.
- Neither of you has a soft-deleted watch, or a watch logged in the app (such as a movie
  night), so neither route can double a viewing.
- 0 entries have a row for the same film within a day under another viewing id. 0 pairs inside
  the plans share both a film and a date.
- 0 planned films are gone or in the Trash, and no trashed film holds a new film's TMDB id.
  Today's title rule picks the same film for all 113 title matches, each one identified and
  of the diary's exact year.
- The database refuses a second row with the same viewing id for the same person, so a repeat
  apply writes nothing.

**The plans have been accurate where we can check them.** Twenty plan entries were later
recorded by the feed, with the feed's own TMDB id. For the 16 non-doubtful ones (13 yours,
3 Mark's), the plan had chosen the same film every time. The other four were doubtful
entries, which the feed has now settled. Of the 537 entries TMDB identified, 523 carry the
diary's exact year.

## The seven corrections

All 15 saved re-pointings were re-read. Each watch is live, unchanged since 14 Oct and still on
its old film. Seven of them move: six are Mark's and one is yours.

| Logged as | Now on | Moves to |
|---|---|---|
| And Then There Were None (1974) | the 1945 film | a new row |
| Cape Fear (1962) | the 1991 film | the owned 1962 film |
| Dad's Army (2016) | the 1971 film | a new row |
| Godzilla (1998) | the 2014 film | a new row |
| The 39 Steps (1959) | the 1935 film | a new row |
| The Enforcer (1951) | the 1976 film | the owned 1951 film |
| The War of the Worlds (1953) | the 2005 film | a new row |

Each moved watch also gets its TMDB id. Cape Fear (1991) is left with no watch, so it goes back
into movie night's "in neither diary" pool.

## Doubtful entries: which need your eye

101 of the 105 doubtful backfill entries are still unrecorded: 83 yours and 18 Mark's. The
feed has settled the other four. They are sorted below using only the candidates the plans
saved, with no new lookup.

| Tier | Yours | Mark's |
|---|---:|---:|
| 1. Now plain: one catalogue film matches, with the exact year | 8 | 6 |
| 2. Likely: TMDB offered exactly one film from the diary's year | 40 | 8 |
| 3. A real choice: several films from that year, or none | 35 | 4 |

- **Tier 1** was doubtful on 14 Oct only because of duplicate catalogue rows (two Titanics,
  two Dunkirks and the like), which X10 has since tidied. All 14 are on owned films and pass
  the duplicate checks. **Recommended: write them in the main run.**
- **Tier 2** needs a yes or no on each. For 27 the plan saved the full candidate list, with
  one film from that year. The other 21 need a TMDB look first, because only a shortened list
  was saved.
- **Tier 3** needs your choice, or "set aside". Mark knows his own better than anyone: 4 here
  and 8 in tier 2.
- **The 8 doubtful corrections** (5 yours, 3 Mark's) are a judgement list, not write authority:
  Alice in Wonderland (logged 2010), An Inspector Calls (2015), Carrie (2013), Journey to
  the Center of the Earth (2008), Obsession (2025), Salem's Lot (1979), The Heat (2013) and
  The Thing (2011). For six of them, the logged year points to one well-known film. Two need a
  real choice: TMDB holds 51 films called Obsession, and the 1979 Salem's Lot is a TV
  mini-series there.

The full list stays private and is not committed: `.letterboxd-export/recovery-2026-11-12/doubtful-review.csv`
on the Mac.

## Is a source read needed? No

```
Craig  file   Dec 2013 ──────── 9 Sep
       feed        22 Feb ─────────── now
Mark   file   Nov 2022 ──────── 14 Sep
       feed               1 Sep ───── now
```

- The 9 Nov preflight saved a copy of Mark's feed (one approved request). It reached back to
  1 Sep, and all 13 of his diary entries from 1–14 Sep were in it. His 10 Nov sync wrote 38
  entries from after the file and 4 from the plans.
- Your 18 Oct sync wrote entries going back to 22 Feb, and 16 of them were already in your file.
- So every viewing not yet recorded is in the saved plans: all 563 of yours and all 173 of
  Mark's.
- **One thing no source we hold can show.** That is an entry added on Letterboxd after 15 Sep
  for a viewing dated before the feed's reach (back-logging an old viewing). The feed is
  ordered by viewing date (true of the saved copy), so it never brings those in. Only a full re-read of the diaries
  would find them. I don't recommend one (#160, #161): there are likely few or none.
- **TMDB:** the apply makes 421 detail requests, one per new film, and no searches. The later
  doubtful pass would need at most 29 searches: 21 for tier 2 and 8 for the doubtful
  corrections.

## Alternatives

| Option | Cost | Verdict |
|---|---|---|
| A. Write the 635 (+14) and the 7 now; doubtful later | ~40 min, 421 TMDB lookups | **Recommended** |
| B. As A, but film rows left bare | 421 films with no poster or cast until Sync now fills them, 20 per press | No |
| C. Owned films only first (147 watches) | ~20 min; 488 left for later | Safe, but slower |
| D. Re-run the plans from scratch | ~450 TMDB searches, ~30 min more | Not needed |
| E. Leave it | None | Fine; nothing is being lost |

## Steps and time, if approved

```
backup → re-check → yours → Mark's → 7 moves → read-back
```

| Step | Time |
|---|---|
| Run the weekly backup by hand (GitHub Actions) | ~2 min |
| Re-run this check on fresh rows (read-only, no TMDB) | ~10 min |
| Your apply: 480 (+8) watches, 371 films | 3–5 min |
| Mark's apply: 155 (+6) watches, 45 films | 1–2 min |
| The 7 corrections, 5 films | <1 min |
| Read back through the read-only role, then record it | ~15 min |
| **Total** | **35–45 min** |

- **Stop rules.** Don't write if the re-check differs from these counts, other than entries a
  sync has recorded since. Stop if any step prints different counts. Yours should print
  480 written and 13 recorded since the plan; Mark's 155 and 3; the corrections 7 moved.
- **Expected read-back:** your watches go from 622 to 1,102 (1,110 with tier 1) and Mark's from
  1,014 to 1,169 (1,175 with tier 1). There are 421 more film rows, and no doubtful entry is
  written.
- **When:** not between 08:00 and 08:15 UTC, while the daily job is syncing. Your next sync is
  due 15 Nov and Mark's 17 Nov. Neither clashes, because the apply skips anything already
  recorded.
- **Where:** on the Mac, using X5's own commands (`import_watch_history apply` and
  `repoint_watches apply`), with the live database URL and the TMDB token exported from
  `apps/api/.env.local` (#191). No code changes, so there is no CI gate.
- **Undo:** every watch written carries its viewing id, which is listed in the private
  manifest. Removing those watches and the new films would be a destructive step, taken only
  at your word.

The doubtful pass would come later: about 30 minutes of your time and 20 of an agent's.

## Decisions

1. **Write the backfill: 635 watches (480 yours, 155 Mark's) and 416 new film rows, filled in
   from TMDB.** Recommend yes. Every entry was re-checked today, nothing doubles, and no
   source read is needed. Cost: about 40 minutes of agent time, 416 TMDB lookups (free) and
   about 18,000 cast and crew rows. Undoing it would be destructive.
2. **Make the 7 corrections in the same run** (5 new film rows). Recommend yes: all 7 are still
   exactly as saved. Cost: under a minute, and each one can be moved back.
3. **Add the 14 now-plain doubtful entries** (8 yours, 6 Mark's) through an amended copy of
   the plans, with its hash recorded. Recommend yes: the reason they were doubtful has gone.
   Cost: about 5 minutes.
4. **Leave the other 87 doubtful entries and the 8 doubtful corrections for a later pass.**
   Recommend a short later session that sends you the tiered list, with Mark answering his
   own and up to 29 TMDB searches. Cost: about 30 minutes of your time. The alternative is to
   set them aside for good.

A reply like "1) yes 2) yes 3) yes 4) later" is enough.

## Evidence and method

- **Live reads:** 12 Nov, 19:44–19:52 UTC, using `src.scripts.live_sql` as `mcu_readonly`, one
  SELECT per call. They covered profiles, every watch row (1,636), every film row with its
  owned flag (1,949, 12 in the Trash), every sync record, and credit counts.
- **Syncs:** yours ran 11 Oct (manual, 4 written), 18 Oct (20), 25 Oct (1), 1 Nov (3) and
  8 Nov (0). Mark's ran 10 Nov 08:04 UTC: 50 read, 42 written, 8 already imported, 0
  ambiguous, no error.
- **Saved files, unchanged and gitignored:** `craig-backfill.json` (sha256 `52df2a55…`),
  `mark-backfill.json` (`720781da…`, the hash recorded on 8 Nov), `repoint.json`
  (`33461cbd…`), and both 15 Sep diary files.
- **How the comparison works.** It mirrors the apply code. Presence is by viewing id across
  all of a person's rows. A planned film that is gone or in the Trash is skipped. A new film
  reuses a live row with its TMDB id, and is skipped if a trashed row holds that id. It adds
  three checks the apply doesn't make: today's title rule, rows within a day, and viewings
  logged in the app.
- **New private files** (gitignored, mode 600), in `.letterboxd-export/recovery-2026-11-12/`:
  `manifest.json` (sha256 `1264c16d…`), `doubtful-review.csv` (`443f4c51…`) and a README.
- **Not done:** no write, no Letterboxd or TMDB request, no import or backfill command (not
  even a dry run), and no push. Mark's 9 Nov feed was read from the preflight's saved copy.
