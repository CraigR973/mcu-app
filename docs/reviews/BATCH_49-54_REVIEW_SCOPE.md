# Batches 49–54 — full-app review (wave 2)

Opened 16 Nov 2026. Reviewed SHA `1668071` (`16680718f1e41533742fb726d151a5c4e0a4eb8d`):
production's `/api/v1/health` reported it at check-in (09:08 GMT), and `/api/v1/health/ready` read
`db: ok` with push, AI, eBay, TMDB and Brave configured. Since the last review (wave 1, `527522d`,
11 Oct): 473 commits, 115 merged PRs, 30 migrations, decisions #250–#380, and 681 files changed
under `apps/` and `packages/` (+109,441 −5,245 lines). The procedure is
`docs/agent-commands/review-wave.md`.

## The app, in one screen

- **Who, and the job.** Two people: Craig (admin; builds and runs it) on an iPhone and Mark
  (viewer) on Android (Craig confirmed Mark's on 16 Nov), as an installed web app. The job: know what they own and where each disc is (1,932
  copies at check-in, 62 added since 11 Oct), who has one on loan (4 loans ever), what to watch
  together (Movie night, 11 nights), what is on at the cinema (10 venues), and what to buy next at
  a fair price (10 active wants).
- **Decisions it makes for them.** Which film and edition each copy is (TMDB matching, search-assisted
  identification, year doubts), and which film each cinema screening is. Each disc's specs and
  Blu-ray.com review score, found by Brave search, and looked up again when a film's match is
  corrected (#378, #380). What the collection is worth (eBay asking prices). Whether a price is a
  deal (shops nightly, eBay every two hours). What each person's Needs you lists (#373), what is
  closest to complete, and when to remind and alert.
- **What it changes outside itself.** Web push to the two phones and a calendar feed. Reads TMDB,
  eBay, Brave Search, Blu-ray.com, the shops, Letterboxd and the cinemas' listing sources
  (CinemaTimes and venue sites). Selling is only a pre-filled eBay link. No money moves.
- **Data and how sensitive.** PIN hashes, two watch histories (2,288 watches), assistant chats
  (8), eBay OAuth tokens (encrypted), loans with borrowers' names, push subscriptions and feed
  tokens (withheld from the read-only role). Personal, not special-category. The repo is public
  (since 10 Nov; Craig chose on 16 Nov to keep it so, DS50-03), so every committed report is written
  for publication.
- **AI.** One assistant: Claude through the Anthropic SDK, with read tools and confirmed write
  tools. Two model calls in the last 30 days, the last on 18 Oct.
- **Where it runs.** Neon (192 MB at check-in), Railway (the API and the scheduled jobs: specs and
  reviews 02:00, shops 03:00, values 04:00 on set days, reminders and the cinema programme 08:00,
  eBay every two hours), Vercel (the web app, a PWA).
- **What has gone wrong since wave 1.** Wrong matches that carried the wrong film's specs and
  scores (Bad Lieutenant, Salem's Lot, Dead Man's Shoes; #378, #380); `main` red on browser cases
  during Group AF (#377, #379); two dependency advisories (#371); the cinema gap below (P1). The
  pack lists the rest from STATUS and the close-out notes.

## The panel

| Batch | Pass | Lens | Deliverable | Prefix | Model · effort |
|---|---|---|---|---|---|
| 49 | R1 | Code and architecture | `BATCH_49_CODE_REVIEW.md` | CR | Opus 5.5 · high |
| 50 | R2 | Data, security and ops | `BATCH_50_DATA_SECURITY_OPS_REVIEW.md` | DS | Opus 5.5 · high |
| 51 | R3 | AI and LLM engineering | `BATCH_51_AI_ENGINEERING_REVIEW.md` | AI | Opus 5.5 · high; canary |
| 52 | R4 | Catalogue integrity, with cinema listings | `BATCH_52_CATALOGUE_INTEGRITY_REVIEW.md` | CT | Opus 5.5 · high |
| 53 | R5 | Prices, value and deals | `BATCH_53_PRICES_VALUE_DEALS_REVIEW.md` | MK | Opus 5.5 · high |
| 54 | R6 | Product and UX, two-person scorecard | `BATCH_54_UX_LIVE_APP_REVIEW.md`, `BATCH_54_SCORECARD.md` | UX | Opus 5.5 · high |

Order: the pack (Sonnet 5.5 · high), then R1, R2, R3, R4, R5, R6 one at a time, then the synthesis
(Opus 5.5 · extra-high). Nothing at max. Finding IDs take the batch: `CR49-01`, `DS50-01`, and so
on. Each report lives in `docs/reviews/`.

**Why each lens is here.**
- R1: +109k lines in five weeks across 115 PRs, many fixed per site; catches defects that recur as
  a class, and code that has drifted from its docs.
- R2: scheduled jobs of which the daily check watches four, 30 new migrations, new outside sources
  (the cinemas), weekly backups since X4; catches failures that never reach Craig.
- R3: an assistant with write tools and almost no use; catches steerable writes, silent model
  failures, and whether it earns its keep.
- R4: every feature hangs off which film each copy and each screening is; three wrong matches
  surfaced in a week; catches confidently wrong data, which reads as right to every other lens.
- R5: the app values the collection, calls prices deals and alerts; catches a plausible wrong
  number on the one path that spends money.
- R6: two people on phones and five more rounds of Craig's snags (Groups AA–AF); tells one story
  across every pass.

**Considered and rejected.** A cinema-listings lens of its own (folded into R4 for which film each
screening is and R2 for the feed's health; Craig's default, 16 Nov). Coaching, strength, sports
medicine and statistics (no training or health data; medians and a usual price are R5's). Privacy
as its own lens (two consenting adults; R2 asks what each sees of the other's data). Performance
and the PWA (R6 and R1).

## The five questions

1. Is it correct and safe?
2. Is it honest with its user: does what they read match what the app decided and what the data
   shows?
3. Is it doing its job for the user: knowing what they own, finding it, lending it, watching
   together, going to the cinema, buying well?
4. Would a failure be noticed, by the app, by Craig and by the person it affects?
5. Can it be run and changed cheaply: complexity, cost, data, hosting?

**Weight most:** what changed most since wave 1 (Groups X–AF: Needs you, Movie night, At the
cinema, re-lookups after a corrected match); whether a failure reaches anyone (P1 below is live);
wave 1's 44 findings and the guards it named; the users' own words.

## Decisions at scoping (Craig: plan of 15 Nov, go on the morning of 16 Nov)

1. **Panel:** a full review, the six lenses of wave 1; cinema listings inside R4 and R2.
2. **Production access:** read-only, as in wave 1. The database only through the `mcu_readonly`
   role with `src.scripts.live_sql`; Railway only through read-only CLI calls (`deployment list`,
   `logs`, `config plan`). Outside services only by reads with the app's own keys, logged per call:
   at most 50 eBay Browse calls, 100 TMDB calls and 20 cinema page reads in the whole review; no
   Brave calls (paid credit); never a person's eBay token.
3. **Paid cap:** $0.50 in all: the assistant canary (about $0.08, stopping before $0.25), asked
   for here, and at most one small R3 probe. The Anthropic key is read only inside Railway's run
   environment and never printed.
4. **Batch numbers:** 49–54, the next free numbers in `docs/phase-batches.md` (later groups use
   letters).
5. **Unattended run:** one orchestrator session starts each step as a linked session, one at a
   time, with permissions bypassed; only the hard rules keep the steps read-only. The Mac is held
   awake for 30 hours from 09:10 on 16 Nov.

## Decisions during the review

6. **Repository visibility** (Craig, 16 Nov, after DS50-03): keep the repo public for now. Every
   committed report is written for publication; R6's scorecard and anything personal stay in
   scratch. Switching on secret scanning and push protection is Craig's to do. A scan of the whole
   history on 16 Nov (1,002 commits, every PR's head, no value printed) found one credential, the
   April GitHub token, which the owner record says is revoked; only `.env.example` files were ever
   committed. The synthesis records the decision in `DECISIONS.md`.

## Live constraints

- No protected window. Craig may run batches on `main` while the review runs: every pass judges
  the snapshot at `1668071` and reads code from the review worktree, never the main checkout.
- The 02:00 specs batch on 16 Nov re-looked-up 9 discs and Salem's Lot's review (#378, #380); its
  read-back is Craig's (STATUS), and R4 may observe it.
- Claude Pro limits: each step paces itself on the 5-hour window and stops above 85% of the week
  (27% at check-in, resets 20 Nov 02:00 UTC).

## Guardrails

The skill's `RULES.md` and the hard rules in `docs/agent-commands/review-wave.md`, as they apply
here: read-only; never `cd`; the database only through the read-only role, never `DATABASE_URL`;
tests with `env -u DATABASE_URL`; credential tables counted from `pg_stat_user_tables`, never
selected; no personal data committed; at most one step at a time.

## Pre-review findings (each labelled; each seeded into a named pass)

**P1 — four ODEON cinemas have shown no new listings since 12 Nov, and nothing says so.**
`observed`: the cinema programme job returned 0 rows for ODEON Braehead, East Kilbride, Glasgow
Quay and Kilmarnock on each of its five runs from 12 to 16 Nov, each with "CinemaTimes venue
identity differs from the approved branch"; the programme's rows fell from 2,247 on 11 Nov to 888
on 16 Nov. Every one of its 14 runs since 3 Nov ended "partial", including the nine where no venue
failed, so the status carries no signal. `implemented`: the parser refuses a CinemaTimes page
unless it holds exactly one cinema whose name equals the approved venue name; the daily health
check watches four jobs (shops, specs, eBay, values), not the cinema programme or reminders, so all
16 checks read OK on 16 Nov. Seeded into R2 (noticing) and R4 (which screenings are real); put to
Craig as a fast-lane item on 16 Nov.

**P2 — the assistant is barely used.** `observed`: two model calls in the last 30 days (the last on
18 Oct), eight chats in all. Seeded into R3 (weigh its cost and upkeep against its use; the canary
is the main live evidence) and R6.

## Paid-call log

| When (UTC) | Pass | Purpose | Model | Tokens in / out | Cost |
|---|---|---|---|---|---|

No paid call so far (R1–R4).

## Outside-call budget (decision 2)

| Service | Cap for the review | Used | By |
|---|---|---|---|
| TMDB | 100 calls | 4 | R4, 16 Nov 14:33–14:35 UTC: three film reads, one release-dates read |
| Cinema listing pages | 20 reads | 1 | R4, 16 Nov 14:38 UTC: one CinemaTimes page (the fast lane's own reads were its batch's) |
| eBay Browse | 50 calls | 0 | |
| Brave | none allowed | 0 | |

Other outside calls so far, all reads: the API's health endpoints (the pack), GitHub metadata
through `gh` (R2 and the orchestrator), one unauthenticated GET of the repository (R2), and Railway
CLI attempts, rejected each time.
