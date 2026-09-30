# Group V's overnight run — the prompt

**Start it with one line, in a new cloud session on this repo:** "Read and follow
`docs/group-v-overnight.md` on `main`, unattended, to the end." Craig's go and the reasons for
this scope are `DECISIONS.md` #230; the batches are Group V in `docs/phase-batches.md`. Before
starting, allow `api-production-a8fe.up.railway.app` in the cloud environment's network settings
(`OWNER-ACTIONS.md` 25). Model and effort: the top tier at `xhigh` (V6 needs it).

**Already done on 30 Sep, in the planning session:** `main`'s red fixed (`urllib3` 2.8.0,
[#4](https://github.com/CraigR973/mcu-app/pull/4)) and this plan merged. So the run starts at V1.

---

You are running unattended overnight on CraigR973/mcu-app for Craig, who is asleep. Work through the items below in order, one pull request per item, and finish them, or stop cleanly with a report, by morning. Never wait for an answer: answer from the repo whatever the repo can answer; when a stop condition hits, stop and report.

## Your authority (Craig, 30 Sep: DECISIONS.md #230)

This is his standing authorisation, as `/group-start` is, for exactly these items and nothing else:

- Create and push one branch per item: `feat/v1-…`, `feat/v3-…` and so on for batches, `chore/close-out-…` for close-out docs, and `fix/…` only for a pre-existing red on `main` (preflight 2).
- Open a pull request per item into `main`. When CI is green on its head, merge it yourself with a **merge commit** (not squash or rebase), so the batch's small commits stay in `main`'s history and the merge commit is what deploys.
- Merging to `main` deploys to production (Railway API, Vercel web). That is intended: AGENTS.md's close-out protocol.

GitHub work goes through the `mcp__github__` tools: load them with ToolSearch (`create_pull_request`, `merge_pull_request` with the merge method `merge`, `pull_request_read`, `update_pull_request_branch`, `actions_list`, `get_job_logs`). `subscribe_pr_activity` and `send_later` are in the claude-code-remote tools.

## Read first, in order

AGENTS.md; STATUS.md (Now and Gotchas); DECISIONS.md #228, #229 and #230 (grep `^228\. ` and so on); docs/phase-batches.md, the section "Group V — the 30 Sep snags" and Group V's rows under "Batch groups"; OWNER-ACTIONS.md item 25; docs/agent-commands/group-start.md, batch-start.md, batch-verify.md and phase-closeout.md; docs/owner-snags-2026-09-30.md.

## Set up once (tested in a cloud container on 30 Sep)

Shell state does not persist between commands, so put variables inline every time. Never `cd` at the top level: use absolute paths and `pnpm -C`. The repo is at `/home/user/mcu-app`; adjust if yours is elsewhere.

```
/usr/bin/python3.12 -m venv /home/user/mcu-app/apps/api/.venv
/home/user/mcu-app/apps/api/.venv/bin/pip install --require-hashes -r /home/user/mcu-app/apps/api/requirements-dev.lock
pnpm -C /home/user/mcu-app install --frozen-lockfile
mkdir -p /tmp/mcu-pg && chown postgres:postgres /tmp/mcu-pg
su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /tmp/mcu-pg/data -U postgres --auth=trust"
su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /tmp/mcu-pg/data -o '-p 5433 -k /tmp/mcu-pg -c listen_addresses=localhost' -l /tmp/mcu-pg/log start"
psql -h localhost -p 5433 -U postgres -c 'create database mcu_test'
```

The container's Node 22 is fine (engines: >=20.18). The local Postgres is 16; CI's is 17, and CI is the authority. Below, DBENV means `DATABASE_URL=postgresql://postgres@localhost:5433/mcu_test JWT_ACCESS_SECRET=ci-access-secret-with-at-least-32-characters JWT_REFRESH_SECRET=ci-refresh-secret-with-at-least-32-characters`.

## The gate (batch-verify.md, adapted to the container)

Read the counts, not the colour.

```
/home/user/mcu-app/apps/api/.venv/bin/ruff check /home/user/mcu-app/apps/api
/home/user/mcu-app/apps/api/.venv/bin/ruff format --check /home/user/mcu-app/apps/api
PYTHONPATH=/home/user/mcu-app/apps/api /home/user/mcu-app/apps/api/.venv/bin/mypy --config-file /home/user/mcu-app/apps/api/pyproject.toml /home/user/mcu-app/apps/api/src
DBENV PYTHONPATH=/home/user/mcu-app/apps/api /home/user/mcu-app/apps/api/.venv/bin/alembic --config /home/user/mcu-app/apps/api/alembic.ini upgrade head    (then downgrade base, then upgrade head again)
DBENV /home/user/mcu-app/apps/api/.venv/bin/python3.12 -m pytest /home/user/mcu-app/apps/api/tests    (30 Sep: 1,634 passed, none skipped; many skips mean DBENV was missing)
pnpm -C /home/user/mcu-app -r test    (not --filter, which skips packages/shared)
pnpm -C /home/user/mcu-app --filter @mcu/shared typecheck
pnpm -C /home/user/mcu-app --filter @mcu/shared build
pnpm -C /home/user/mcu-app --filter @mcu/web lint
pnpm -C /home/user/mcu-app --filter @mcu/web typecheck
pnpm -C /home/user/mcu-app --filter @mcu/web build
```

**Browser checks** use DECISIONS.md #169's method: the dev server with `VITE_SKIP_AUTH=true` in `apps/web/.env.local` (gitignored; delete it after), against a throwaway stub of the API in your scratchpad serving the reads the page needs. Drive it with Playwright; Chromium is preinstalled at `/opt/pw-browsers` (never run `playwright install`). Record in the close-out what you looked at, at which widths and in which theme.

## Preflight, before anything else

1. `curl -sS -m 20 https://api-production-a8fe.up.railway.app/api/v1/health` must return JSON with `commitSha`. If the proxy refuses it, you cannot verify a deploy. Take V1 to a green pull request, merge nothing, and stop with the report: Craig must allow the host (OWNER-ACTIONS.md 25, step 3).
2. `main`'s latest CI run must be green. It was made green on 30 Sep ([#4](https://github.com/CraigR973/mcu-app/pull/4), `urllib3`). A new red is a pre-existing red: fix it first on its own `fix/` branch, through the same pull-request cycle, if it is small and obvious (a new advisory is usually a one-package lock bump, as #4 was); otherwise stop.

## The run, in order

Never start an item until the one before is merged, verified in production and closed out.

**Pause:** merge nothing between 02:45 and 03:45 UTC on 1 Oct. The 03:00 UTC shop check is 20b's first evidence, and a deploy while it runs could cut it short. Resume with `send_later` at 03:45. If `main` moves while a pull request is open (another session may push), bring `main` in and let CI run again before merging.

**For every item:** a branch from the latest `origin/main`; small Conventional Commits, staged by explicit path (never `git add .` or `-A`); tests with the change; the whole gate green locally; push; a pull request whose body lists each acceptance criterion with its evidence and the gate's counts. Then **subscribe to the pull request's activity** (`subscribe_pr_activity`) and end your turn: a CI result wakes you. Arm one `send_later` check-in about 30 minutes out as a safety net, and never poll with `sleep`. When CI is green on the head: merge (merge commit). **Verify the deploy**: load the Monitor tool and wait with an until-loop, at most 20 minutes, until `/api/v1/health` reports the merge commit's SHA as `commitSha`; then `/api/v1/health/ready` must answer `"db":"ok"`. Then the close-out, per phase-closeout.md steps 9–11: strike the batch in docs/phase-batches.md with its merge SHA and a result paragraph listing any criterion still open and whose it is; update the relevant rows of ARCHITECTURE.md §17 (grep, never read it whole); overwrite STATUS.md's Now block (up to `## Next` only, then `grep -n '^## ' STATUS.md` must still list Now, Next, Gotchas, Log) and prepend a dated Log line; append to DECISIONS.md any durable choice you made. Land the docs through a `chore/close-out-…` pull request, merged when green.

1. **V1**, then 2. **V3**, then 3. **V4**, then 4. **V5**, then 5. **V6**: each through batch-start → gate → pull request → merge → verify → close-out. The criteria are below, verbatim from docs/phase-batches.md. In V1's close-out, tick OWNER-ACTIONS.md 25 step 3 if preflight 1 passed.

A lock needing a one-package bump is regenerated from the repo root in a subshell, so the lock headers keep their relative paths: `(cd /home/user/mcu-app && uv pip compile apps/api/pyproject.toml --output-file apps/api/requirements.lock --generate-hashes --upgrade-package <pkg> && uv pip compile apps/api/pyproject.toml --extra dev --output-file apps/api/requirements-dev.lock --generate-hashes --upgrade-package <pkg>)`.

**Then stop.** Do not start V7, V8, V9, 20b, 22c, 21, T8b or 38: #230 says why each waits.

## Stop conditions, absolute (group-start.md)

Stop, write the report and end:

- CI not green after three attempts on the same check. Never merge red.
- Production does not report the merge SHA within 20 minutes, or `/health/ready` is not `db: ok`. Merge nothing further.
- A spec fact is wrong in a way that changes what a batch should build.
- Anything needing a credential, a hosting console, or a Railway, Vercel or Neon change.
- Anything that deletes or rewrites collection data.
- Any live request to eBay, a shop, Blu-ray.com or AVForums. Fixtures only. V6's trial run is Craig's, not yours.
- The working tree holds anything outside the item in hand.

Never weaken the gate: no deleted test, loosened assertion, `type: ignore` or eslint-disable as a route to green. V3's removal of the deck's tests is the one planned exception, and its close-out names each removed test and why. Never force-push, never amend a pushed commit, never bypass hooks.

## Gotchas that bite here (STATUS.md, by number)

- **15 and 18:** CI's migration job proves apply and reverse on an empty schema, nothing about rows. V4's migration writes none.
- **17:** a bare digit in a location is not a shelf.
- **19:** any new list uses `listState()` (V5's rows).
- **20:** a rule spanning fields is a `model_validator(mode="after")`.
- **9 and 21:** mypy is strict with `warn_unused_ignores`; write code that needs no ignore.
- **22:** any new QueryClient keeps `networkMode: 'always'`.
- **26:** dates come from `src/clock.py`, never `date.today()`.
- **8 and 10:** `pnpm -r test`, and `ruff format` as well as `ruff check`.

## Notes on the batches (from the 30 Sep reconciliation, docs/owner-snags-2026-09-30.md)

- **V1:** the 20 classes are in OfflineBanner, AppLayout (the top bar), MobileTabBar, FormatBadge (four), ViewToggle, ui/badge (five), ui/button (two hovers), ui/state-panel, MovieNightSessionPage and NotificationSettingsPage (three). The phone's top-level test is `isTopLevel` in `apps/web/src/lib/nav-items.ts`. The film page's "Back to collection" is in `MovieDetailPage.tsx`. Loans hides through `showWhen: 'loans'`.
- **V3:** the list and the deck are both in `MovieNightSessionPage.tsx`, and "Start swiping" is on `MovieNightPage.tsx`. Every detail the deck shows is already in each candidate the list receives.
- **V4:** `SECTIONS` is in `apps/api/src/models/collection_item.py`; the parser's `_SECTION_PREFIXES` in `apps/api/src/spreadsheet/parser.py`. The form's picker reads `GET /collection/facets`, which lists only populated sections (`routers/movies.py`). Its migration is 042.
- **V5:** there is no production database here, so read the query plan against the local database and say so. The check against real row counts stays open, as Craig's or a later session's.
- **V6:** no captured search holds an auction with a bid. `tests/fixtures/ebay_browse_blade_runner_2049.json` holds one auction with Buy It Now (`bidCount` 0, `currentBidPrice` present). Build from that real shape, and say in the test where a copy changes the bid count. The estimator's search (`src/ebay/estimate.py`) sends no `filter` today; `EbayClient.search` already takes one.

## The batches' criteria, verbatim

### V1 — Top bar, tints, back arrows and Loans 🟡
**Covers snags 7, 5 and 3. Carries what was V2 (#229).** Mid tier · high / mid tier · High.
Sitting 1, first. **The top bar has had no background since 10 Sep (`9afc173`):**
`bg-background/94` names an opacity step Tailwind 3 does not have, so the class is never built,
and only the blur is left. 20 classes in 10 files share the fault: the bottom tab bar (`/96`),
every tinted badge and notice (`/12`), the format badges (`/14`) and the filled buttons' hover
(`/88`). The back arrows change the same top bar, which is why V2 joined it.

**Acceptance:**
- The missing steps (12, 14, 88, 94, 96) are added to the Tailwind theme, so all 20 classes
  are built as written. Proved by the built stylesheet containing them.
- A test fails when any class in `apps/web/src` names an opacity step the theme lacks, so a
  dropped class cannot recur silently.
- On a phone the top-level pages are the four bottom-tab pages (Home, Archive, Add, Movie
  night) and You. Every other page shows the top bar's back arrow. It goes back through
  history; with none (a notification, a link) it goes to You for a page listed there, and to
  the page's parent otherwise.
- The film page's back button returns to where the person came from, and to the Archive when
  there is no history. Below 1024 px it is hidden, since the top bar's arrow does that job.
- **Loans is always listed, for Mark and Craig** (#228), in the sidebar and on the You page.
  Box sets, Collections and Deals keep hiding while empty (#154). The navigation test's count
  moves, with the reason beside it. Lending and "Mark returned" stay admin-only.
- Browser check at 375 px, light and dark: the top and bottom bars are opaque with content
  scrolled under them; the Deals discount badge, a movie-night vote chip and a format badge
  show their tint; Wanted, Deals and Settings opened from You show the arrow and return to You;
  a film opened from Deals returns to Deals, at 375 px and at 1280 px.
- Gate green.

### V3 — Movie night on one screen 🟡
**Covers snag 4.** Mid tier · high / mid tier · High. Sitting 1, second. Craig chose the list
over the swipe deck (#228), which retires Phase 8.4's "swipe-like UI" and #207's arrow-key rule.

**Acceptance:**
- A night is one screen, the shortlist. Each film has one Add / Added control; tapping Added
  takes the vote back. The swipe deck, its gestures, its arrow keys and its "N of M" count are
  removed, and "Start swiping" is renamed where it starts a night.
- Tapping a film opens its details in the row: synopsis, runtime, genres, cast, who else has
  seen it and when, where it streams, and a link to its page.
- A match is still everyone adding the same film, announced once, with its push. The other
  person's votes stay hidden (#157). The API does not change: `record_vote` already replaces
  a vote.
- The deck's tests are replaced by tests of voting on the list, and the close-out names each
  test removed and why: a feature removed, not a test weakened.
- Browser check at 375 px and 1280 px. The two-phone match check is Craig's, as T4's was.
- Gate green.

### V4 — Craig's house 🟡
**Covers snag 6.** Top tier · high / top tier · High. Sitting 1, third. "Craig's house is
fine" (#228): that name, one place with no shelves, counted like any other disc.

**Acceptance:**
- "Craig's house" is a section: in `SECTIONS`, in the location parser (typing "Craig's house"
  or "Craigs house" lands there), and in the `ck_collection_items_section` CHECK through a
  reversible migration. The apostrophe is escaped in the SQL, with a test: migration 007's
  `_check_clause` pastes names inside quotes and would break on it.
- The copy form's Section picker offers every section, including one with no discs yet. The
  Archive's section filter still lists only sections that hold a disc.
- The migration writes no rows. Its downgrade clears `section` on rows using the new name
  before narrowing the CHECK, and leaves `location` alone, as 007's does.
- Browser check at 375 px: a disc moved to Craig's house, then found by the section filter.
- Gate green.

### V5 — Highlights on Home 🟡
**Covers snag 9.** Mid tier · high / mid tier · High. Sitting 1, last. "A mix of all" (#228).

**Acceptance:**
- Home gains a Highlights panel of short poster rows, each film opening its page:
  - **Top rated:** films on the shelf rated 4½ or 5 stars, with whose rating it is. Craig rates
    on Letterboxd and Mark does not (#159), so the row says so rather than implying both.
  - **Most rewatched**, across both diaries.
  - **Most valuable discs**, at their stored value, with its basis.
  - **Best reviewed** is V9's to add, once review scores exist.
- A row with nothing in it is not shown.
- One request for the panel, its query plan read against the real row counts.
- Browser check at 375 px.
- Gate green.

### V6 — Trial: pricing from live bids 🟡
**Covers snag 2, first step.** Top tier · xhigh / top tier · Extra High. Sitting 2, first.
"Lets trial first" (#228). Sold prices stay out of reach, signed in or not (#16, #126, #228).
**The sitting stops here** once V6 is live: Craig taps "Try bid prices" on Home and picks a
blend or bids only from its report (#229).

**Acceptance:**
- An admin-only "Try bid prices" on Home searches eBay once per film and format for a sample
  of up to 100 priced films across 4K, Blu-ray and DVD, asking for Buy It Now and auctions
  together (`buyingOptions:{FIXED_PRICE|AUCTION}`). Its calls count against the day's
  valuation share (#209). **It saves no prices.**
- An auction counts only with at least one bid, and passes the same matcher: standard edition,
  the right film and format, a UK seller.
- The report says, by format: how many films had three or more auctions with bids; for those,
  the bid median against the asking median; how many of those auctions end within 24 hours;
  whether sharing the 200 results with auctions cost Buy It Now listings; and what the sampled
  discs total on each basis.
- The report is kept where a later session can read it, not only shown once.
- Gate green. The run is Craig's, and his pick of blend or bids only follows it.

## The morning report

When you stop, whether finished or halted, the last close-out's STATUS Now block is the report, and your final message says the same:

- each item: its pull request, merge SHA, and the production check;
- every failure on the way, including ones fixed first time;
- anything left open, and whose it is;
- Craig's next steps: tap "Try bid prices" on Home and pick blend or bids only (then V7 and V8); the two-phone check of V3; allow blu-ray.com and avforums.com before V9; his go on 20b and 22c.

If the PushNotification tool is available, send Craig one push with the one-line outcome.
