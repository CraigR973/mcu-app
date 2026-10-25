# AA4 — Movie night verification, 25 Oct

## Agreed scope and acceptance criteria (verbatim)

### AA4 — Movie night: suggest first, two lists, a planned time 🟡
- **16, 17.** The night opens with Suggest a film; below it "Suggested" (people's picks, who and
  when), then "Stuck for ideas? A random shortlist" (the Archive's picks).
- **18.** A night takes an optional planned date and time (one nullable `planned_start_utc`,
  shown in the person's time, in the list of nights and in the invite push). Migration granted to
  `mcu_readonly` and `mcu_backup` as `CLAUDE.md` says.
- **20.** A film page (owned or a TMDB page) offers "Add to movie night" when a night is open,
  choosing the night when more than one is.
- Tests (the e2e movie-night case updated, not loosened). Gate green.


## Pre-flight

- Clean main at `3bf02c7`; main CI 40198864796 passed.
- Sitting 3 authorised: AA4 → AA5 → AA6 only. AA10b final readback stays open.
- Existing TMDB film page already has a night picker; the owned page needs one.
- No existing collection row is rewritten. Migration adds one nullable column.

## Evidence

- Focused API: 41 passed on local throwaway Postgres 16.2, including UTC offset normalisation,
  recipient-local invite text, unplanned nights and preserving votes on a promoted random pick.
- Full API retry: 2,435 passed, 9 skipped (collection replacement tests require TCP localhost;
  this throwaway server uses a Unix socket). No movie-night or derived-trigger test skipped.
- Frontend gate: 154 shared and 680 web tests passed; shared/web typecheck, shared build, web lint
  (11 existing warnings) and production web build passed. Contract/screen retry: 18 passed.
- Fresh migration 066 → base → head passed on a second throwaway Postgres with both roles:
  both can SELECT planned_start_utc and neither can SELECT invite_token (catalogue checks only).
- Chromium's 33 cases passed, including planned invite, live match and film-page promotion with
  its prior vote. Inspected the 375 px rendered screenshot: search first, separate labelled
  lists, timestamp wraps, Add/Added controls fit. Corrected the new one-film count's grammar.
- Firefox: 32 passed, 1 documented dictation skip. Jobs: 5 passed. Final focused Chromium pass: 3 passed on the final bundle; inspected its 375 px viewport capture.
  PR, exact-SHA CI and production verification pending.

## Decisions made within the agreed scope

- A random pick explicitly suggested by a person moves to Suggested using its existing id and
  votes. A second explicit suggestion is still refused rather than creating a duplicate.
- Planned time uses the browser's local time on entry and the recipient's existing notification
  timezone in pushes. Existing nights need no backfill.
- The already working TMDB night picker is retained and labels each night by planned time when
  present; owned pages gain the same action.

## Failures and limits

- Ruff first reported an unsorted import; fixed by its import sorter.
- First local Postgres initialisation failed on the shell's locale; retry with en_US.UTF-8 succeeded.
- First full API gate failed only because the OpenAPI snapshot lacked the agreed fields.
  Regenerated it with the repo exporter; the test and its assertion are unchanged. Full retry passed.
- Mac WebKit is unsupported; the PR must prove it in CI, with only documented suite skips.
- Pre-commit whitespace check found an extra blank line at this report’s end; removed it.
