# Group AE — the plan for Craig's 8 Nov feedback — 9 Nov 2026

**Craig gave the go on 9 Nov.** A copy of Group AE as drafted on 9 Nov, for reading on a phone. The
live record is Group AE in `docs/phase-batches.md`; the decisions are `DECISIONS.md` #355; the
reconciliation is `docs/reviews/feedback-reconciliation-2026-11-08.md`.

**Drafted 9 Nov from Craig's 18 points and his six answers (#355). Craig gave the go at
about 21:00 GMT on 9 Nov ("yes codex is done").** The points and their reconciliation against the code are in
`docs/reviews/feedback-reconciliation-2026-11-08.md`. Ten batches in five sittings: one branch
and PR per batch with normal verification and automatic close-out (#24), clean `main` between
batches, sequential, no stacked branches. Point 11 (pricing accuracy) needs no new batch: AA10c
from 25 Nov answers it. Asking Mark about three copies is Craig's (`OWNER-ACTIONS.md`).

**Before sitting 1 the checkout must be clean** (close-out conditions 3 and 4). At 19:30 GMT on
9 Nov it held the 8 Nov reconciliation's uncommitted record corrections (`STATUS.md`,
`OWNER-ACTIONS.md`, this file), five untracked 8 Nov reports, a local docs commit not yet
pushed (`b92d710`, Mark's username save) and this plan with #355. Once Craig confirmed Codex
had finished, one docs-only commit settled them, pushed with `b92d710` before sitting 1, and
two stray blank lines were dropped.

Settings: Deep = Opus 5.5 / GPT-5.6 Sol; Standard = Sonnet 5.5 / GPT-5.6 Terra. The strictest
batch sets its sitting's effort. Resolve an unavailable model with Craig.

| Sitting | Ordered work and checkpoints | Claude Code / Codex |
|---|---|---|
| 1 | AE1 → AE2 → AE3 | Opus 5.5 `high` / GPT-5.6 Sol High |
| 2 | AE4 → AE5 → AE6; AE4's owed enable and read-back the morning after it deploys | Opus 5.5 `xhigh` / GPT-5.6 Sol Extra High |
| 3 | AE7 | Opus 5.5 `xhigh` / GPT-5.6 Sol Extra High |
| 4 | AE8 → AE9 | Opus 5.5 `high` / GPT-5.6 Sol High |
| 5 | **checkpoint: Craig picks from AE10's sketch** → AE10 | Opus 5.5 `xhigh` / GPT-5.6 Sol Extra High |

The sittings do not depend on each other, so the order is by value: the copy trap Mark has
already hit, then Home, cinema, search, people, and movie night last because it waits for
Craig's picks. AE10's sketch is made at the start of the run, so Craig can answer while
sittings 1–4 run; only sitting 5 waits. Within a sitting the order is fixed: AE3 follows AE2 on
the same Home page, AE5's view needs AE4's tenth cinema, and AE9 links the names AE8 labels.
Cost: ten PRs, each with the full local gate, seven-job CI and a production deploy; one owner
stop (the movie night picks); one live write (enabling the Omniplex, covered by #355).

| Batch | Scope and size | Claude Code / Codex | Status |
|---|---|---|---|
| AE1 | A copy's formats: one box or a separate copy (point 10), 🟢 ~1.5 h | Sonnet 5.5 `high` / GPT-5.6 Terra High | drafted |
| AE2 | Home: the rewatch card, the estimate note, Highlights opens on Recently added (points 1, 2, 15, 17), 🟢 ~2.5 h | Sonnet 5.5 `high` / GPT-5.6 Terra High | drafted |
| AE3 | Closest to complete names what is missing; a film can be set not to count (point 3), 🟡 ~3 h | Opus 5.5 `high` / GPT-5.6 Sol High | drafted |
| AE4 | Cinema sources: TMDB's own budget, three title patterns, the Omniplex (points 7, 18), 🔴 3–5 h | Opus 5.5 `xhigh` / GPT-5.6 Sol Extra High | drafted |
| AE5 | The day-by-day cinema view, All / None, folded sections (points 4, 8, 13), 🟡 ~3 h | Opus 5.5 `high` / GPT-5.6 Sol High | drafted |
| AE6 | Cinema film page: IMDb and Letterboxd; who has seen it when inviting (points 5, 6), 🟡 ~2.5 h | Opus 5.5 `high` / GPT-5.6 Sol High | drafted |
| AE7 | Search that finds what you mean (point 12), 🔴 3–4 h | Opus 5.5 `xhigh` / GPT-5.6 Sol Extra High | drafted |
| AE8 | Needs you shared, each item labelled by owner (point 16), 🟡 2–3 h | Opus 5.5 `high` / GPT-5.6 Sol High | drafted |
| AE9 | A page for each person (point 14), 🟡 3–5 h | Opus 5.5 `high` / GPT-5.6 Sol High | drafted |
| AE10 | Movie night that reaches a match (point 9), 🔴 sketch ~0.5 h, then 4–8 h | Opus 5.5 `xhigh` / GPT-5.6 Sol Extra High | drafted; sketch before build |

**About 28–38 hours of agent work**, plus 30–60 minutes of gate per batch (5–10 hours across
the ten).

*Why those settings.* AE4 is Extra High: it changes what feeds every morning's identity links and
AC6's pushes, and adds a source; a wrong link mislabels showings silently. AE7 is Extra High: it
adds two database extensions to production through the boot migration and changes the search
behind every screen. AE10 is Extra High for several people's state on one night and its pushes,
as AC5 was. AE3 (a new table) and AE8 (who sees what) are Deep High; AE5, AE6 and AE9 are Deep
for design judgement, the premium bar. AE1 and AE2 alone need only Standard; they run at their
sitting's setting.

*Choices made while drafting, open to Craig's overrule.*

- Highlights opens on Recently added on every visit; the last tab picked is not remembered, so
  new additions are always the first thing seen. Order: Recently added, Most valuable, Most
  rewatched, Best discs.
- Closest to complete gets the report's options a and b (name the missing films with a Want
  button; a per-film "Doesn't count"), not franchise sets or ordering by recent change.
- "Doesn't count" can be set by either person and undone, and is per set, so the film still
  counts in other sets.
- TMDB gets its own cap of 120 requests a run, separate from the unchanged 120-request ceiling on
  cinema sites, rather than one larger shared ceiling.
- The date strip opens on Today and keeps the existing all-days view as its last option. Times
  already past today are hidden.
- A combo pack stays one copy. "Separate copy" opens Add a copy with the new format chosen and
  leaves the existing copy alone. A new copy has no default format.
- Needs you's shared list is for the people who keep the shelves (Craig and Mark); a later
  onboarded profile still sees only their own.
- The person page shows photo, films watched this year and in total, the last ten diary entries
  with ratings, copies they added recently, their wants and their loans. Your own name opens You.
- Search aliases are a short fixed list in code, reviewed in the PR.

## AE1 — A copy's formats: one box or a separate copy 🟢

- Ticking a second disc format on an existing copy asks "One box with both discs, or a separate
  copy?" before saving. One box saves the combo as today. Separate copy leaves the existing copy
  unchanged and opens Add a copy for the same film with the new format chosen.
- A new copy starts with no format; saving without one says to choose a format. No silent
  Blu-ray.
- Digital formats are not disc formats and do not trigger the question.
- The duplicate prompt ("This is an upgrade" / "Add another copy") keeps its meaning; its words
  say "separate copy" where that is what they mean.
- No migration and no change to stored copies. King Arthur: Legend of the Sword and Silent
  Running stay as they are until Mark answers (`OWNER-ACTIONS.md`).
- Regress: the combo save, the separate-copy path, a required format on add, the offline queue,
  375 px in both themes; E2E covers the separate-copy path.
- Full gate and E2E; after deploy, health and readiness on the merged SHA.

## AE2 — Home: the rewatch card, the estimate note, Highlights opens on Recently added 🟢

- **Worth a rewatch (point 1):** poster and title side by side at the top; "Open the film",
  "Deal another" and, when shown, "Start again" on one row across the full card beneath,
  unwrapped at 375 px; "Only films I haven't watched" under the row; no empty band under the
  poster. Poster and title open the film too.
- **How this estimate works (point 17):** opens as a full-width panel under both figures, not
  inside the left half; closed by default as now.
- **Recently added (points 2 and 15, #355):** the first Highlights tab, newest first, from owned
  copies added in the app (the spreadsheet's rows carry no added date), each card naming who
  added it, when and the format ("Mark · 5 Nov · 4K UHD"). A film appears once, at its newest
  copy; copies in Trash or no longer owned are left out; twelve cards, as the other tabs have.
  Order: Recently added, Most valuable, Most rewatched, Best discs; it opens on Recently added
  every visit. With nothing added in the app the tab hides and the next one opens, as today.
- An additive field on the Highlights read, with its zod schema in `packages/shared` in the same
  PR; existing fields unchanged.
- Regress: each tab; loading, empty, offline and failed states; both people; 375 px in both
  themes.
- Full gate and E2E; after deploy, a read-only check that Recently added matches the newest owned
  copies with an added date (60 such copies, 10 Oct–5 Nov, at 8 Nov's count).

## AE3 — Closest to complete names what is missing; a film can be set not to count 🟡

- Each set in Home's Closest to complete names its missing films, up to three, with "+N more"
  opening the set; each has a Want button using the existing wanted-list path, and a film already
  wanted reads "Wanted".
- "Doesn't count" on a missing film, for lost films, TV episodes and alternate versions. Either
  person can set it, and "Count it again" undoes it. It is per set: the film still counts in
  other sets. Each change is audited in `admin_actions`.
- A set whose only missing films do not count reads complete and leaves the row; the set's own
  page lists them, struck through.
- One migration: a small table (set, film, who, when) with a UUID key and UTC timestamps; guarded
  SELECT grants to `mcu_readonly` and `mcu_backup` in one block; the downgrade refuses while a row
  exists.
- The completion read's changes carry their zod schema in the same PR.
- Regress: setting Eastwood's Piano Blues not to count moves the row on, and undoing it restores
  the row; both people see the same; offline and failed states; 375 px in both themes.
- Full gate and E2E; after deploy, the table exists and is empty, both roles can read it, and the
  row names Eastwood's, Kubrick's and Hitchcock's missing films as live data has them. The agent
  sets nothing not to count in production.

## AE4 — Cinema sources: TMDB's own budget, three title patterns, the Omniplex 🔴

- **Budget (#355, changing AC3's 48 in #335):** TMDB lookups get their own cap of 120 requests a
  run, separate from the unchanged 120-request ceiling on cinema-site reads, which the programme
  still spends first. The run report records both counts. The caches are unchanged (30 days for a
  film found, 7 for one not found), and the run's deadline still stops it.
- **Title cleaner:** "Access Film Club: The Grand Budapest Hotel" links to the film as a special
  screening; "Arthur Christmas (15th Anniversary)." loses its trailing full stop before the
  suffix rule, so it reads as an anniversary showing; "CBeebies Panto 2026: Treasure Island" is
  an event and never links to a film. A regression test per real title; no other identity rule
  changes (#335, #339).
- **The Omniplex, Renfrew Street (#355):** a tenth venue, read from its CinemaTimes page as the
  four ODEONs are. The reader accepts Omniplex's booking host and showtime ids alongside ODEON's
  and still rejects any other host. The web app's booking allow-list and short names include it,
  and the "all nine" wording counts the venues instead. The end-to-end suite's fake listings gain
  an Omniplex page. One more page read a morning, inside the unchanged ceiling.
- **Enabling stays guarded:** the existing enable step needs fresh accepted coverage, so the
  Omniplex shows only after a natural morning run has read it. The morning after deploy: a
  read-only check of its coverage, then the existing enable command for exactly one venue,
  audited, then a read-back. #355 is the word for this one write; no manual refresh.
- Regress: CinemaTimes fixtures for ODEON and Omniplex; a foreign booking host rejected; the three
  titles; the TMDB cap independent of the programme's count; the run report's two counts.
- Full gate and E2E; after deploy, health and readiness. **Owed the next morning, without holding
  the sitting:** the Omniplex's coverage accepted and the venue enabled; its showings in both
  people's cinema filter; the lookup queue at or near zero; both counts within their caps; the
  nine unchanged.

## AE5 — The day-by-day cinema view, All / None, folded sections 🟡

- **Day by day (point 4):** a date strip is the top control of Movie night's At the cinema view,
  sticky while scrolling. Today is selected on arrival; the strip runs as far as any cinema
  lists, a day with nothing showing greyed out, and the existing all-days view stays as its last
  option. The day is kept in the address, as the other filters are.
- With a day picked, each film lists that day's times grouped by cinema, each time a chip with its
  format that opens the booking page under AB7's rule. Times already past today are hidden; when
  none are left today, the view says so and offers tomorrow.
- The run and cinema filters stay, under the strip.
- **All / None (point 8):** at the top of the Cinemas list; with none ticked, the existing "Select
  at least one cinema" shows.
- **Folded sections (point 13):** "Not matched to a film yet · N" and "Events and double bills · N"
  are closed by default, with the count in the heading.
- No new request: every showing is already in what the view loads.
- Regress: switching days; an empty day; a cinema listing only to an earlier date; past times
  today; ten cinemas; 375 px in both themes. E2E updated for Today as the default.
- Full gate and E2E; after deploy, a read-only check of today's times for both people against the
  stored showings.

## AE6 — Cinema film page: IMDb and Letterboxd; who has seen it when inviting 🟡

- **Links (point 5):** a matched film's cinema page links to IMDb (when its IMDb id is known) and
  to Letterboxd (`letterboxd.com/tmdb/<id>`), opening outside the app; an unmatched listing gets
  a Letterboxd search link only. The film-facts read gains an additive `imdbId`, with zod, in the
  same PR.
- **Who has seen it (point 6):** "Who to invite" in Propose a trip shows beside each person
  "Seen · 12 Mar 2024" (their latest watch) or "Not seen", from their watch history, for a matched
  film; an unmatched listing shows neither. The same rule as movie night's "who else has seen
  it" (S7), so nothing new is exposed.
- Regress: matched and unmatched; several watches show the latest; a person with none; 375 px in
  both themes.
- Full gate and E2E; after deploy, a read-only check of both people's seen dates against their
  watch rows for three matched films. Mark's diary is current only from his first sync (#354;
  first eligible 10 Nov, 08:00 UTC).

## AE7 — Search that finds what you mean 🔴

- One migration (#355): Postgres's `pg_trgm` and `unaccent` extensions, an immutable
  accent-folding function, and trigram indexes for titles and people's names; a downgrade that
  removes what it added. The app's Neon role can create both: a read-only check on 9 Nov found it
  a member of `neon_superuser`, with both extensions available and neither installed.
- Title matches rank first (exact, then starts-with, then close), then the existing full-text
  matches on cast, crew, genre and plot.
- These searches, each failing on 8 Nov, find the right films first: "godf", "godfathr",
  "jurasic", "hitchcok", "spiderman", "leon" (Léon) and "lotr"; and "bond" lists the Bond films
  before Joan of Arc.
- Aliases are a short fixed list in code (LOTR, T2, MI and the like), reviewed in the PR.
- Every existing search keeps working: filters, paging, the search page and the top bar's search.
  The response shape is unchanged, or additive with zod.
- `docs/restore-runbook.md` names the two extensions. There is no new table, so the backup's
  grants are unchanged.
- Regress: the examples above as tests on real Postgres; accents and hyphens; an empty and a
  one-letter query; ranking ties.
- Full gate and E2E (the boot job proves the migration on CI's Postgres); after deploy, both
  extensions installed on production and an `EXPLAIN` through the read-only role showing the
  indexes used.

## AE8 — Needs you shared, each item labelled by owner 🟡

- **#355 supersedes the private visibility in #351 and AC1's per-person list (#336) for the
  people who keep the shelves.** Craig and Mark each see every item for both, their own first,
  each labelled "You" or with the other's name. A later onboarded profile still sees only their
  own.
- An item offers its action only to whoever can act now: loan jobs to both shelf keepers, as
  today; a trip reply only to its invitee; an assigned review's answer only to its assignee
  (#351's answer rules unchanged). Another person's item opens its page to read.
- Home keeps its five-item limit; the overflow lists every item for both, labelled.
- Pushes are unchanged: nobody is pushed about another person's item.
- An additive owner field per item (id and name), with zod; existing clients keep working.
- Regress: each item type for Craig, Mark and a third active profile; AD1's forged cross-profile
  write tests still refuse; empty, offline and failed states; 375 px in both themes.
- Full gate and E2E; after deploy, a read-only check that both readers get the same labelled
  list, matching the loan, trip and review rows.

## AE9 — A page for each person 🟡

- A page per active person: photo and name; films watched this year and in total; the last ten
  diary entries with ratings; copies they added recently; their wants; their loans. Read-only.
  Your own name opens You.
- Names and avatars link to it: Needs you's labels, movie night, trips and Most rewatched.
- Never shown: PINs, sessions, notification settings, connected accounts or anything else from
  Settings.
- One new read with its zod schema; no migration.
- Regress: your own page and another's; a person with no diary; an inactive profile not found;
  375 px in both themes.
- Full gate and E2E; after deploy, a read-only check of both pages' counts against live data.
  Mark's diary is current from his first sync (#354).

## AE10 — Movie night that reaches a match 🔴

- **Checkpoint before build:** a 375 px sketch in both themes, with real data, of the report's
  five proposals (invite when starting; a shorter shortlist with filters that matter on the
  night; the other person's progress without their picks; at the match, where the disc is and
  "Log it for both of you"; closing nights nobody touched), with a recommendation. Made at the
  start of the run; Craig picks; no build before his answer.
- The acceptance follows his picks and is written into this entry before the build. Fixed
  whatever he picks: the other person's votes stay hidden until a match (#157) unless he chooses
  otherwise; no push is sent twice; a closed night keeps its history.
- Size 4–8 h, by the picks.
