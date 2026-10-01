# The next cloud session — after the Mac's one-off setup

**Start it with:** "Read and follow `docs/next-cloud-session.md` on `main`." Top-tier model
at `xhigh`, because V7 needs it if Craig's pick comes in the same session.

**Before it:** Craig has run `docs/mac-cloud-setup.md` on his Mac and added the variables to
the cloud environment (`OWNER-ACTIONS.md` 27). **Craig is there:** decisions are his, asked in
the chat and numbered. Nothing below runs on a guess.

## Rules

- `AGENTS.md`, all of it, and its "Cloud sessions" section above all: read the live database
  only through `src.scripts.live_sql`; never print `NEON_READONLY_URL` or a token; make no
  write to live data; run `railway config plan` freely, and `config apply` only on Craig's
  explicit word in this chat.
- Batches land as the overnight run's did (#230): a `feat/` or `fix/` branch from `main`, a
  pull request, CI green, a merge commit, production's `/api/v1/health` reporting the merge
  SHA with `db: ok`, then a `chore/close-out-…` pull request. Never weaken the gate.
- Write to Craig the way he reads, on his phone: the answer first, short, decisions numbered
  so he can reply "1) yes 2) no".
- The first `live_sql` call may take a few seconds while Neon's compute wakes.

## 1. Check the setup, and record it (`OWNER-ACTIONS.md` 27)

1. The startup hook's line must list `NEON_READONLY_URL`, and `RAILWAY_TOKEN` (or
   `RAILWAY_API_TOKEN` and `RAILWAY_PROJECT_ID`). If one is missing, stop: tell Craig which,
   and point him to `docs/mac-cloud-setup.md`, step 3.
2. The role: `SELECT current_user, current_setting('default_transaction_read_only') AS
   read_only, (SELECT count(*) FROM movies) AS films` should answer `mcu_readonly`, `on` and
   about 1,887. `SELECT pin_hash FROM profiles LIMIT 1` must be refused (permission denied).
3. Railway: `railway --version` says 5.63.1; `railway config plan` from the repo root (with an
   account token, `railway link -p "$RAILWAY_PROJECT_ID" -e production` first) should plan
   nothing to add, change or destroy. **Never apply.**
4. Record it: item 27 struck as done in `OWNER-ACTIONS.md`, a dated line in `STATUS.md`'s Log.
   If anything failed, record what and stop there.

## 2. The checks that waited for the database (read-only)

- **V5's open check:** the Highlights query plans on production's own rows. Capture the four
  statements the endpoint runs (`routers/highlights.py`), as `DECISIONS.md` #234 did: a
  `before_cursor_execute` listener while calling `highlights()` against the local test
  database, then the parameters written in as literals. Run each with `live_sql --explain`.
  Report the execution times and the plan shapes against the scratch figures (3.1, 0.8, 1.9
  and 8.4 ms). Close the open item in `docs/phase-batches.md` (V5) and §17 row 33.
- **The 1 Oct 03:00 UTC shop check**, which Craig's go on 20b and 22c waits for:
  `scrape_runs` since 30 Sep (attempted, succeeded, failed, and `failures` by shop and
  reason): how many `429`s, from which shops, against 30 Sep's 21 of 33. This is also the
  read-only diagnosis 20b's first criterion asks for; add `railway logs` for `cron-scrape`
  if a token is set. Write it into 20b's section of `docs/phase-batches.md`.
- **Batch 21's start condition:** three wants with prices from two shops on two days (from
  `price_checks`), and seven days of scheduled scrapes (`scrape_runs` with `trigger = 'cron'`).
  Say whether both hold. 21 starts itself once they do, and 2 Oct is the earliest.
- **The bid trial**, if Craig has run it (`valuation_runs` with `trigger = 'trial'`): read
  its report (`live_sql --json` on the `report` column) and summarise it by format for his
  pick: films with a bid price, bids against asking, auctions ending within 24 hours, results
  cut at 200, and the totals on each basis (`DECISIONS.md` #235 says what each means). If
  he has not run it, remind him (`OWNER-ACTIONS.md` 26).

## 3. Ask Craig, then carry on

One message: what sections 1 and 2 found, then the decisions, numbered:

1. **Blend or bids only**, if the trial has run. That starts V7, then V8.
2. **Go on 20b**, given what the 1 Oct check showed. Then 22c, which uses 20b's pacing.
3. Anything in `OWNER-ACTIONS.md` that would unblock more: allowing blu-ray.com and
   avforums.com (V9), the eBay sign-in settings (item 18, for T8b).

Then run what he approved, in the plan's order, each batch on its own: V7 → V8 (sitting 2),
20b → 22c. Read each batch's criteria, model and effort in `docs/phase-batches.md` before
starting it; if one needs a different model or effort from this session's, say so and give
Craig a one-line prompt for a new session instead. **Not without Craig:** V9 (its first
requests go to two outside sites, after his network step), T8b (item 18), and 38, which is
last. 21 starts itself once its condition holds.

## 4. Close

Each batch keeps its own close-out (`docs/agent-commands/phase-closeout.md`). At the end,
`STATUS.md`'s Now block says where things stand; the final message to Craig says the same,
with each pull request, its merge SHA and its production check, and what is still his.
