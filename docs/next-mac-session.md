# The next Mac session — 20b's second half, then V9

**Start it with:** "Read and follow `docs/next-mac-session.md` on `main`." Top-tier model at
`max` effort: V9 needs it (20b alone needs `high`). Pull `main` first.

**Craig's word, 2 Oct:** "give me a prompt to do 20b and the blurray,com/avforums work on a
session on my mac". That is his go on 20b's second half and on V9, run on the Mac because the
cloud environment cannot reach blu-ray.com or avforums.com. **Craig is there:** decisions are
his, asked in the chat and numbered. Nothing below runs on a guess.

## Rules

- `AGENTS.md`, all of it, and its Mac rules above all: **never `cd`** (autoenv prints
  `apps/api/.env`, which still holds the live connection string, `OWNER-ACTIONS.md` 22);
  absolute paths and `git -C`; Python 3.12 from the API venv; Node 20 through nvm.
- **Tests never touch the live database.** Run pytest without `DATABASE_URL` in the
  environment: the Postgres-backed tests skip on the Mac (`STATUS.md` gotcha 15) and CI runs
  them against Postgres 17. Never export `apps/api/.env.local` into a test run, and treat a
  green local run as silent about SQL.
- **Live data is read through the read-only role only.** Put
  `NEON_READONLY_URL="$(cat ~/.mcu-secrets/neon_readonly_url)"` before
  `PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.live_sql "<one SELECT>"`
  (`--explain`, `--json`). Never print the variable. No write to live data.
- **Railway:** the token is in `~/.mcu-secrets/railway_token`; reach the CLI as
  `.railway/README.md` says ("Two things that will bite"; gotcha 29). `config plan` freely,
  `config apply` only on Craig's word. A cron job's logs belong to the deployment that ran it
  (`AGENTS.md`, "Cloud sessions": `railway deployment list --service cron-scrape`, then
  `railway logs <id> --service cron-scrape --lines 500 --json`).
- Batches land as the overnight run's did (#230): a `fix/` or `feat/` branch from `main`, a
  pull request, CI green, a merge commit, production's `/api/v1/health` reporting the merge
  SHA with `/health/ready` saying `db: ok`, then a `chore/close-out-…` pull request. Never
  weaken the gate.
- Write to Craig the way he reads, on his phone: the answer first, short, decisions numbered so
  he can reply "1) yes 2) no".

## 1. The shop checks since 2 Oct (read-only)

20b's section of `docs/phase-batches.md` holds 2 Oct's read-back: every refusal a `429` with
`retry-after 60`, Cloudflare, "Too many requests", no `cf-mitigated`; each Shopify shop
refused its first request of the night; 4 of 29 retries got through two seconds later. For
each night since that is not recorded: the `scrape_runs` row, the five enabled retailers
(`enabled`, `consecutive_failures`, `last_scrape_status`, `last_scrape_error`), and the
`cron-scrape` log of the deployment live at 03:00 (`scrape_refused` lines per shop, whether
each Shopify shop's first request was refused, what `Retry-After`, `cf-mitigated`, `server`
and the title said, how many retries got through). Add it to 20b's section and a `STATUS.md`
Log line. If the pattern has changed (a block rather than a rate limit, or no refusals), stop
and tell Craig before step 2.

## 2. 20b's second half — top tier · high

Rewrite the second half's acceptance in 20b's section from that evidence before any code
(#54). The proposal Craig said go to on 2 Oct:

- A refused request waits for the shop's `Retry-After` before its one retry, instead of two
  seconds, bounded at 90 seconds; a missing or larger value keeps today's pause and says so in
  the refusal's record. Still one retry, still sequential per shop.
- The sale-page check (22b) follows the same rule.
- The run's record says, for each refusal, whether the retry after the wait got through.
- The first scheduled check after the merge is read back: refusals that survive a minute's
  wait are named. If most do, tell Craig, with the remaining option: a fixed outbound address
  for Railway, a hosting change and his call.
- Tests (a refused request's wait is bounded, honoured and reported). Gate green.

A refused night may then take up to about 30 minutes at 03:00, unattended; that was the stated
cost. Then the close-out.

## 3. V9 — reviews: links, lines and scores — top tier · max

Read V9's criteria in `docs/phase-batches.md`, #110 and #228, and build them. On the Mac:

- **Craig's network step is not needed:** the Mac reaches both sites. Ask him to raise Brave's
  monthly limit only if the month's credit has run out when you get there (#202's total).
- **Before any code:** capture one Blu-ray.com review page and one AVForums review page as
  real fixtures (exact page addresses, one request each, paced), and read AVForums' terms and
  `robots.txt`. If AVForums forbids automated access, it stays links-only and the app says so;
  its scores then need Craig's decision, asked numbered.
- **#110's bounds hold:** exact page addresses only, no search routes, sequential and paced, a
  `403` or `429` halts the integration, and every stored row names its source.
- Browser check at 375 px, light and dark, by `DECISIONS.md` #169's method; delete
  `apps/web/.env.local` afterwards.
- Then the close-out, with V5's "Best reviewed" row in the result.

## 4. Close

Each batch keeps its own close-out (`docs/agent-commands/phase-closeout.md`). At the end,
`STATUS.md`'s Now block says where things stand; the final message to Craig says the same, with
each pull request, its merge SHA and its production check, and what is still his.

**Not in this session:** 22c (after 20b's second half shows the wait works), T8b
(`OWNER-ACTIONS.md` 18), and 38, which is last. Batch 21 starts itself once a third want has
two shops' prices on two days.
