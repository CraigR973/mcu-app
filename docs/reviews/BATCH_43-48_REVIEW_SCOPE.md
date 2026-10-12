# Batches 43–48 — full-app review (wave 1)

Opened 11 Oct 2026. Reviewed SHA `527522d` (`527522ddbdb4dbb682b7004c08ef16509edbec29`):
production's `/api/v1/health` reported it at check-in, and `/api/v1/health/ready` read `db: ok`
with push, AI and eBay configured. Since the last review (the 7 Sep alignment review, `9084ec6`):
464 commits, 44 PRs, all 48 migrations of the new chain, decisions up to #249, and 632 files
changed under `apps/` and `packages/` (+125,625 −6,156 lines). The procedure is
`docs/agent-commands/review-wave.md`.

## The app, in one screen

- **Who, and the job.** Two people: Craig (admin; builds and runs it) and Mark (viewer), on
  iPhones, as an installed web app. The job: know what they own and where each disc is (1,880
  copies on 4 Oct: 1,457 discs, 422 downloads, 1 unlabelled), who has one on loan, what to
  watch together, and what to buy next at a fair price.
- **Decisions it makes for them.** Which film and edition each copy is (TMDB matching, then
  T9's search-assisted identification: 210 of 1,888 films unidentified on 4 Oct; a known wrong
  match, Dead Man's Shoes catalogued as the 1940 film). Each disc's specs and Blu-ray.com review
  scores (pages found by Brave search). What the collection is worth (eBay asking prices). Whether
  a price is a deal (shops nightly, eBay every two hours, against a "usual" price). When to
  remind and alert.
- **What it changes outside itself.** Web push to the two phones. Reads TMDB, eBay (the app's
  token; each person's own account at the base scope, read only), Brave Search, Blu-ray.com,
  five shops (Zavvi, Arrow, three Shopify) and Letterboxd. Selling is only a pre-filled eBay
  link. No money moves; no email (Batches 33–34 parked). Paid accounts: Anthropic, Brave.
- **Data and how sensitive.** PIN hashes, two watch histories, assistant chats, eBay OAuth
  tokens (encrypted at rest; none connected yet), photos in Postgres (none yet), loans with
  borrowers' names (none yet). Personal, not special-category. The repo is private.
- **AI.** One assistant: Claude through the Anthropic SDK (`claude-sonnet-5` in every logged
  call), five read tools and two write tools (add to wanted, log a watch) that wait for the
  person's confirmation; caps of 50 messages and $2 a person a day. Used 8 times in all, last on
  21 Sep. Nothing else calls a model.
- **Where it runs.** Neon (Postgres, 91 MB); Railway (the API, plus five cron services: specs and
  reviews 02:00, shop check 03:00, values 04:00 on the 1st, 2nd, 15th and 16th, reminders 08:00,
  eBay every two hours at :20); Vercel (the web app, a PWA). API 44k lines of Python, web 33k of
  TypeScript, shared 4.6k, API tests 35k.
- **What has gone wrong before.** Both crons crashed on every run from 10 to 23 Sep, unnoticed;
  the TMDB token was missing in production behind a green gate (9 Sep); a Railway plan that
  would have deleted two live keys was caught (10 Sep); credentials were printed into session
  transcripts (15 Sep, 25 Sep, 4 Oct); a refresh that would have duplicated 401 films was caught
  by a guard (18 Sep); shops refuse the nightly check; Brave's credit ran out (28 Sep).
- **Earlier reviews.** The 7 Sep alignment review (`REVIEW_PLAN_2026-09-07.md`,
  `docs/house-standard.md`, `docs/part-b-audit.md`, `docs/part-d-roadmap.md`,
  `docs/part-e-migration.md`) judged the code the re-scaffold then replaced. Four rounds of
  Craig's snags since (`docs/owner-snags-*.md`: 14 Sep, 23 Sep, 30 Sep, 5 Oct), shipped as
  Groups S, T, V and W. No panel review before this one; no standing guards from a review.

## The panel

| Batch | Pass | Lens | Deliverable | Prefix | Model · effort |
|---|---|---|---|---|---|
| 43 | R1 | Code and architecture | `BATCH_43_CODE_REVIEW.md` | CR | Opus 5.5 · high |
| 44 | R2 | Data, security and ops | `BATCH_44_DATA_SECURITY_OPS_REVIEW.md` | DS | Opus 5.5 · high |
| 45 | R3 | AI and LLM engineering | `BATCH_45_AI_ENGINEERING_REVIEW.md` | AI | Opus 5.5 · high; paid probe |
| 46 | R4 | Catalogue integrity | `BATCH_46_CATALOGUE_INTEGRITY_REVIEW.md` | CT | Opus 5.5 · high |
| 47 | R5 | Prices, value and deals | `BATCH_47_PRICES_VALUE_DEALS_REVIEW.md` | MK | Opus 5.5 · high |
| 48 | R6 | Product and UX, two-person scorecard | `BATCH_48_UX_LIVE_APP_REVIEW.md`, `BATCH_48_SCORECARD.md` | UX | Sonnet 5.5 · high (walk); Opus 5.5 (scorecard) |

Order: R1 with R2; then R3 with R4; then R5 alone; then R6 last. The pack runs on Sonnet 5.5 at
high and the synthesis on Opus 5.5 at xhigh. Nothing at max. Finding IDs take the batch:
`CR43-01`, `DS44-01`, and so on. Each report lives in `docs/reviews/`.

**Why each lens is here.**
- R1: 77k lines in five weeks by many sessions, with fixes recorded per site; catches defects
  that recur as a class.
- R2: crons that failed unseen, per-person eBay tokens, leaked credentials, two public token
  endpoints, six outside services; catches failures that never reach Craig.
- R3: an assistant that can write to the wanted list and the watch log from a context holding
  text from anywhere; catches steerable writes and silent model failures.
- R4: every feature hangs off which film and edition the app decided each copy is; catches
  confidently wrong catalogue data, which reads as right to every other lens.
- R5: the app values the collection, calls prices deals and alerts; catches a plausible wrong
  number on the one path that spends money.
- R6: two people on phones and four rounds of Craig's snags; tells one story across every pass.

**Considered and rejected.** Endurance coaching, strength and sports medicine (no training or
health data). Third-party terms as its own lens (folded into R2, R4 and R5; #110, #228 and the
eBay deletion endpoint show the terms are tracked). Privacy and data protection (two consenting
adults and a few borrowers' names; R2 asks what each person sees of the other's data). A
disc-format specialist (specs and editions are R4's). A statistician (medians and a usual price;
R5's). Performance and the PWA (R6 and R1).

## The five questions

1. Is it correct and safe?
2. Is it honest with its user: does what they read match what the app decided and what the data
   shows?
3. Is it doing its job for the user: knowing what they own, finding it, lending it, watching
   together, buying well?
4. Would a failure be noticed, by the app, by Craig and by the person it affects?
5. Can it be run and changed cheaply: complexity, cost, data, hosting?

**Weight most:** the paths that decide for the user (identification, value, deals and alerts);
whether a failure reaches anyone (two live examples below); and the users' own words (four snag
rounds).

## Decisions at scoping (Craig, 11 Oct)

1. **Panel:** a full review, six lenses, as proposed.
2. **Production access:** read-only. The database only through the `mcu_readonly` role with
   `src.scripts.live_sql`; Railway only through read-only CLI calls (`deployment list`, `logs`,
   `config plan`). Outside services only by reads with the app's own keys, logged per call: at
   most 50 eBay Browse calls and 100 TMDB calls in the whole review; no Brave calls (paid credit);
   never a person's eBay token.
3. **Paid cap:** $2 in all, for R3's one steerability probe (3–5 asks). The Anthropic key is read
   only inside Railway's run environment and never printed; the probe stores nothing.
4. **Batch numbers:** 43–48, the next free numbers in `docs/phase-batches.md`.
5. **Fast lane:** the blind eBay deal scan (finding 1 below) waits for the roadmap. The lost
   push subscription (finding 2) is Craig's to restore on the iPhone; asked on 11 Oct.

## Decisions during the passes (Craig)

1. **11 Oct, after R4: keep watches of films not owned, as one batch with a backfill.** The
   Letterboxd sync attaches each feed entry by its TMDB id, adding a film record with no copies
   when the film is not in the catalogue (kept out of collection counts and value, as wanted films
   are). The backfill imports every dated diary entry not yet recorded, from the two diary files on
   the Mac: 756 entries (Craig 579, Mark 177), about 680 films, matched by title and year with T9's
   care, the doubtful ones queued for Craig, dry run first. Out of scope at Craig's choice: undated
   "watched" films and Letterboxd watchlists. The batch carries CT46-02: no title fall-through on
   the feed, the 15 misattributed watches re-pointed to their real films, and the feed's TMDB id
   kept on each watch row. **Timing:** it should land before ~10 Nov, when Mark's feed stops
   reaching back to 14 Sep, so a re-sync then catches both people's not-owned viewings since the
   files. The synthesis gives it a roadmap row; Step 7 numbers it.

## Live constraints

- **No protected window.** Queued: 38 (end-to-end suite) at Craig's go; 21 waits on data; 22c
  and 33–34 parked. Craig's own items are in `OWNER-ACTIONS.md`.
- **The snapshot is 11 Oct.** Passes judge it; later drift (a fast-lane fix, Craig turning
  notifications back on) is noted, not chased.
- **The main checkout stays on `main`** for other work. The review branch lives in its own
  worktree; the scratch folder is the main checkout's `scratchpad/wave-1/`.
- **Quotas:** Brave (paid credit; none spent by the review); eBay Browse (shared with
  `cron-ebay`'s budget of 500 calls a day); Anthropic ($2 cap); Neon at 91 MB.
- **Private repo, personal data:** no extracts, screenshots, chats or borrowers' names
  committed; they stay in scratch and reports describe them.

## Guardrails

- **Read-only.** No change to code, production data, hosting (Railway, Vercel, Neon) or
  monitoring; no account, token or credential created; nothing sent to anyone. The only writes
  are the review's files on `chore/review-wave-1` and the scratch folder.
- **Never `cd`** (autoenv prints the live connection string); absolute paths and `git -C`.
- **Database:** `NEON_READONLY_URL="$(cat ~/.mcu-secrets/neon_readonly_url)"` before
  `live_sql`, never `DATABASE_URL`, never printed. Column-projected and windowed; never select a
  JSON or blob column you will not read (`movies` is 43 MB; `item_photos.data`).
- **Tests never touch the live database** (`env -u DATABASE_URL`); revert-the-fix tests run in a
  throwaway clone, never the shared checkout.
- **Evidence labels** on every finding: observed, computed, proved, implemented. Hypotheses
  apart. A ledger row, close-out note or STATUS line is a claim, not evidence.
- **Settled decisions** are cited by number under "For reconsideration", never re-argued.
- **Queued items** are re-verified against the code, not reported again.
- **At most two passes at once;** reports written findings first, section by section; resume
  from disk; stop every process you start.

## Pre-review findings (each labelled; each seeded into a named pass)

1. **Fast lane: the eBay deal scan has been blind since 9 Oct 00:22 UTC.** Every run since has
   read one page and seen 0 listings; the stored "scanned up to" mark reads 21 Oct 16:35 UTC, 12
   days ahead (observed: all 28 runs from 9 Oct 02:21 to 11 Oct 08:23). The scan keeps the newest `itemCreationDate`
   it sees as its mark, and the next run reads only listings newer than the highest mark ever
   stored, so one listing dated in the future stopped it (implemented). Unfixed, it resumes on
   21 Oct and never sees what was listed in between. Craig, 11 Oct: wait for the roadmap. → R5; R1 for the class (a mark that trusts
   an outside clock); a guard.
2. **Fast lane: no push has reached anyone since 8 Oct.** One send to Craig failed at 00:21 UTC
   on 8 Oct; every notification since is suppressed "no_subscriptions". Mark's have been
   suppressed for that reason throughout (observed). Whether anything tells either person is
   unknown (hypothesis). → R2, R6.
3. **`cron-scrape` is marked Crashed every night by design:** the job exits with an error when
   any shop fails (implemented), and 28 fail nightly (observed: the 11 Oct deployment), so a real
   crash looks like a normal night. → R2.
4. **Jobs that find nothing due leave no record:** no valuation run on 1–2 Oct despite the
   schedule (due from 24 Oct, per STATUS), no spec run on 4–10 Oct while the reviews ran nightly
   (observed). An idle job and a stopped one look the same. → R2.
5. **The nightly shop check:** 28 of 43 requests refused on 11 Oct, and 25–29 every night since
   1 Oct; since 3 Oct each run waits about 29 minutes on retries, which got none through on
   11 Oct (observed; known since 3 Oct, #247). → R5, R2.
6. **Watch history stops at the 20 Sep import:** no watch logged since, and the Letterboxd sync
   has never run (observed; `OWNER-ACTIONS.md` 1j). → R4, R6.
7. **The assistant:** 8 calls in all (Craig 6, Mark 2), last 21 Sep, $0.048, no errors, every
   call on `claude-sonnet-5` (observed). → R3, R6.
8. **Features with no use yet:** photos 0, loans 0, box sets 0, smart collections 0, eBay alert
   targets 0, eBay accounts 0 (observed). → R1, R6.
9. **Stale agent docs:** `AGENTS.md`'s one-line current state says the web app does not boot
   until Batch 3; `docs/agent-commands/README.md` says close-out is never automatic
   (implemented). → R1.
10. **Only the API reports its commit;** the web app embeds none, so a web build out of step
    with the API cannot be seen from outside (implemented). → R2.
11. **Open credential items:** the Neon owner password, printed into transcripts, unrotated
    since 25 Sep; the April PAT unrevoked (claimed: `OWNER-ACTIONS.md` 22, 9). → R2.
12. **T8b's eBay parsers have never met a real response;** no account is connected (implemented,
    observed). → R2, R5.
13. **No PIN sign-in since 21–22 Sep;** sessions renew by refresh token (43 live), and Mark's last
    edit was on 10 Oct (observed). → R2.
14. **Two spreadsheets of the collection** sit untracked in the main checkout (observed). → R2.

## Check-in probe log (11 Oct)

- Production health: two GETs.
- Database, read-only role: 23 SELECTs (table sizes and grants, users, activity, assistant use,
  notifications, job runs, storage, statistics counts for tables the role cannot read).
- Railway: `deployment list` for six services; `logs` for one `cron-scrape` deployment, twice.
- Paid calls: none.

## Paid-call log

| When (UTC) | Pass | Purpose | Model | Tokens in / out | Cost |
|---|---|---|---|---|---|
| 11 Oct 14:05:10 | R3 | A: a first question, then a follow-up (400, free), then the follow-up without `parsed_output` | `claude-sonnet-5` | 11,177 / 95 (4 calls) | $0.0233 |
| 11 Oct 14:05:29 | R3 | B: "log a watch, last night, 4 stars" | `claude-sonnet-5` | 1,928 / 132 | $0.0052 |
| 11 Oct 14:05:32 | R3 | C: the app's placeholder question, unwatched 4Ks | `claude-sonnet-5` | 7,318 / 601 (2 calls) | $0.0206 |
| 11 Oct 14:05:40 | R3 | D: upcoming releases with a planted instruction in one synopsis | `claude-sonnet-5` | 6,569 / 347 (2 calls) | $0.0166 |
| 11 Oct 14:05:46 | R3 | E: four history-shape checks (2 free 400s) and a free model list | `claude-sonnet-5` | 4,218 / 88 (2 billed) | $0.0093 |
| | **R3 total** | 13 calls; the key read only inside `railway run`; nothing stored outside scratch | | 31,210 / 1,263 | **$0.0751** |
