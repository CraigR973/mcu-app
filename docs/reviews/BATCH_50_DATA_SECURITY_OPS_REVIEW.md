# Batch 50 — Data, security and operations review (wave 2, pass R2)

**Pass R2** · reviewed SHA `1668071` · lens: security and site-reliability engineer · read-only · paid calls: none.

## 1. Summary
Grade **C**. The data layer and auth are sound; the failure path still misses half the jobs, and the
repository is public while every record says private. 5 findings: 0 High, 2 Med-High (DS50-01,
DS50-03), 1 Medium, 2 Low.
1. **Correct and safe:** grants on all 30 new tables are right for both roles and no credential is
   readable (catalogue-proved); login lockout, refresh rotation and PIN-change revocation hold. One
   gap: PIN change takes unlimited guesses (DS50-02).
2. **Honest:** the daily check said "all OK" for five mornings while four cinemas were dark (DS50-01).
3. **Doing its job:** backups run weekly and the restore drill passes, but nobody has opened an
   encrypted copy and its only recorded key is on one Mac (DS50-04).
4. **Noticed:** the check watches 4 of 8 scheduled things; the cinema half is fixed by the P1 drift
   commit, which would have named P1 on 12 Nov; reminders, backup and the TMDB refresh stay unwatched
   (DS50-01, DS50-05).
5. **Cheap to run:** yes: Neon 192 MB of 1 GB, backups 0.4 GB egress a month by design; Railway's
   side is unread (token rejected).

## 2. Findings (at most ten, Highs first)

### DS50-01 — Med-High — The daily check watches four of the eight scheduled jobs, so a dark cinema, a dead 08:00 job or a failed backup reaches no one (P1, noticing half)
*Severity settled at Med-High by the synthesis (16 Nov), matching this report's summary; the heading said High.*
- **Evidence:** `implemented` — `JOBS` in `services/health_checks.py` lists the shop check, the spec
  job, the eBay scan and the valuation job. Not on it: the cinema programme, the 08:00 job itself
  (reminders, digest, Letterboxd), the weekly backup and the calendar refresh. The cinema phase
  (`cinemas/refresh.refresh_due`) catches every exception, logs a warning to Railway, returns
  `failed` without a heartbeat, and its status is kept out of the job's exit code by design. A host
  refusal switches a venue off (`collection_enabled = false`, an audit row) and the next run simply
  skips it. The daily check runs at 08:01, *before* the 08:02 cinema refresh, so even a cinema row
  would judge yesterday's run. `observed` — 4 of 10 venues returned 0 rows with `failed = true` on
  each of the 5 runs 12–16 Nov; the heartbeat read `partial` with `failedVenues 4` every morning;
  the 16 `health_checks` rows all read OK on 16 Nov 08:01; no push, no Home row.
- **What the user or operator experiences:** Craig and Mark lost four of ten cinemas for five days
  (Braehead, East Kilbride, Glasgow Quay, Kilmarnock) and nothing told either of them; the digest
  kept arriving, built from six venues. The same blindness covers the 08:00 job crashing on CR49-01's
  path (R1), a backup run failing (GitHub emails the repo owner only if notifications are on for
  scheduled workflows; nothing in the app), and the TMDB six-month refresh (DS50-04).
- **Fix and cost:** one rule, not a list: every scheduled thing writes a heartbeat with a cadence and
  a per-run failure figure, and the check reads all of them. Add the cinema programme (per venue:
  failed or zero rows; job quiet or wholly failed; a venue switched off by refusal), the reminders job
  (26 h), the backup (read the workflow's last run, or have the workflow write a heartbeat through the
  API: 8 days), and the calendar refresh (DS50-04). Run the cinema rows again after the refresh.
  Half a day to a day.
- **Where it goes:** the cinema half is drift — the P1 fast lane (`a2caf8c`, PR 161, #381, not
  judged here) adds `check_cinemas` and an after-refresh pass; read in the commit, it names each
  switched-on venue whose latest read failed or found nothing, so **it would have caught P1 on
  12 Nov**. It does not cover a venue switched off by a host refusal (only switched-on venues are
  read), the reminders job, the backup or the calendar refresh: those go in a new row, first sitting
  of the wave 2 group.

### DS50-02 — Low — Changing a PIN accepts unlimited guesses of the current PIN
- **Evidence:** `implemented` — `POST /api/v1/auth/pin` (`routers/auth.py` `set_pin`) checks
  `currentPin` with bcrypt but carries no `@limiter.limit` and never charges `failed_login_count`;
  only `login` does. A success revokes every refresh token. Access tokens last 24 h and sit in
  `localStorage` (`lib/auth-tokens.ts`, which says so).
- **What the user or operator experiences:** nothing today. Whoever holds one stolen access token can
  try every 4-digit PIN within its 24 hours, set a new one, and sign the owner out for good; the
  lockout check on the daily list never sees it.
- **Fix and cost:** count a wrong `currentPin` against the same durable lockout as login, and give the
  route the login limit. An hour with a test.
- **Where it goes:** new row, any sitting.

### DS50-03 — Med-High — The repository is public, while the project's records and this review's rules say private
- **Evidence:** `observed` — GitHub reports the repo `public` (`private: false`), and it answers an
  unauthenticated request (HTTP 200). Its event log records it made public on 10 Nov, 23:49 UTC;
  agents' notes already called it public on 3–4 Nov (`ab7-implementation-2026-11-03.md`, #334), and
  no decision records Craig choosing it. Records that still say private: the review brief, the
  digest, `OWNER-ACTIONS.md` 9 (the reason given for not rewriting history). Secret scanning, push
  protection and Dependabot alerts are all disabled (free on a public repo); `main` has no branch
  protection. `implemented` (counts only, no values printed): Mark's Letterboxd username appears in
  10 tracked files; Craig's surname in 5; 937 commits carry Craig's personal email address; 201
  screenshots under `docs/reviews/assets` (the one opened shows seeded test data); the feedback
  reconciliations quote both people. No live credential found: the April PAT in `0bfb672` is dead
  (owner record).
- **What the user or operator experiences:** anyone can read two people's names, a handle that leads
  to Mark's public diary, the household's collection, its value and its cinemas. Every review that
  pushes adds more: wave 2's own reports would publish on the synthesis's push.
- **Fix and cost:** Craig's choice, ten minutes either way. Make it private again (Actions minutes
  then count against the free 2,000 a month; CI's seven jobs and the e2e job would need measuring
  first), or keep it public deliberately: record the decision, switch on secret scanning and push
  protection, and scrub names and handles from new docs. A history rewrite is not needed for this.
- **Where it goes:** Craig's decision before the wave 2 synthesis pushes (orchestrator); then a
  decision row and, if public stays, a short hygiene row.

### DS50-04 — Medium — The backup's only recorded key is one file on one Mac, and the drill never decrypts
- **Evidence:** `observed` — 8 Backup runs, all `success`, 14 Oct–15 Nov; scheduled ones started
  5–8 hours after 03:30. `implemented` — the drill restores the plaintext copy *before* encryption
  ("the runner never holds the private key"), so no run has ever proved an artifact opens. `proved`
  (public half only, the private key never printed): the key file on the Mac derives exactly the
  public recipient in `.github/backup-age-recipient.txt`. `OWNER-ACTIONS.md` still asks Craig to copy
  that key into his password manager (open since 14 Oct: "it exists only on the Mac"); the runbook
  assumes the copy exists.
- **What the user or operator experiences:** if the Mac dies or is wiped, every one of the eight
  copies is unreadable, the same day Neon's six-hour restore window may matter.
- **Fix and cost:** Craig copies the key (2 minutes); a quarterly hand drill decrypts the newest
  artifact on the Mac with the runbook (15 minutes), or the monthly drill also encrypts and
  decrypts with a throwaway key pair to prove the format round-trips. Record the custody in
  `OWNER-ACTIONS.md` when done.
- **Where it goes:** `OWNER-ACTIONS.md` item (already listed: raise it); the drill change is a small
  row.

### DS50-05 — Low — The TMDB six-month refresh runs only when someone opens Releases, and 24 films are never refreshed
- **Evidence:** `implemented` — `refresh_stale_fields` (100 films, stalest first) is called only from
  `refresh_calendar`, which a calendar read triggers at most daily, or an admin's forced refresh;
  films with no `last_tmdb_sync_utc` are skipped by design. `observed` — 1,064 live films last synced
  over 60 days ago, oldest 8 Sep; none yet past 150 days; 24 identified films have no sync date.
  The 1,064 cross 150 days from about 5 Feb 2027 and six months on 8 Mar: the batch then needs a
  calendar read on at least 11 of those ~30 days. Nothing watches it (DS50-01).
- **What the user or operator experiences:** nothing until March; then TMDB data held past the
  terms (DS44-06), unnoticed.
- **Fix and cost:** call the refresh from the 08:00 job, which now holds the TMDB token for the
  cinema programme; refresh films with no sync date once; a daily-check row when any film passes
  165 days. Two hours.
- **Where it goes:** fold into DS50-01's row (guard 20 of wave 1).

### The failure table (headline question 1), at `1668071`
| Failure | Reaches Craig today | What each person sees |
|---|---|---|
| Shops, specs (Brave, Blu-ray.com 403/429), eBay scan, values: job quiet | yes: `job:*`, `specs:halted`, `ebay:listings`, push + Home row | a stale price or spec, no word |
| TMDB, eBay, Brave, Anthropic keys missing at boot | yes: `api:readiness` | the feature fails in words |
| Anthropic 400s (credit, spend cap), timeouts, malformed output | only if a failure row lands in a day: `assistant:failures` reads the usage log | the assistant's error text |
| A cinema source's identity or shape changes (P1), a venue switched off on refusal, the whole cinema phase failing | **no** (fixed for switched-on venues by the drift commit) | fewer cinemas; stale showings hidden or marked (R4) |
| The 08:00 job crashing (CR49-01) or not running | only as a Home row after 26 h (`check:stale`): no push | no digest, no reminders |
| Letterboxd sync failing | no (and on CR49-01's path, not even recorded) | the diary stops filling |
| eBay sold-store run dying (2 abandoned 11 Nov) | no | thinner values later (R5) |
| Database near full | yes at 512 MB (192 MB now) | — |
| Backup failing or unrestorable | GitHub's own email to the owner only; nothing in the app; decryption never proved (DS50-04) | — |
| A phone's push refused | yes, per person, `notifications` | nothing arrives; re-registers on open |
| Web and API out of step | close-out step only (DS44-04, manual) | a stale page until reload |
| TMDB data past six months | no (DS50-05) | — |

## 3. Follow-through corrections (rows of the pack's table in this lens)
| Row | Pack says | Corrected to | Evidence |
|---|---|---|---|
| DIGEST §1, brief | private repo | **public** since at least 10 Nov (DS50-03) | observed |
| DS44-01 / guard 9 | fixed, 4 of 8 jobs | holds; and the check is pull-only when the 08:00 job itself fails (no push) | implemented |
| DS44-03 / guard 17 | fixed, drill passes | the drill proves the dump, never the encrypted artifact; key custody unconfirmed (DS50-04) | implemented, proved |
| DS44-05 | fixed | holds for login; the PIN-change path has no limit (DS50-02) | implemented |
| DS44-06 / guard 20 | claimed | the refresh exists and works by reads; 24 films never refreshed (DS50-05) | implemented, observed |
| DS44-07 CSP | claimed | not re-read in this pass | — |
| L3 | 4 of 8 jobs unwatched | confirmed; the drift commit covers the cinema half (DS50-01) | implemented |
| L7 | runs only on a read | confirmed (DS50-05) | implemented |
| L8 | Railway token rejected | still rejected at 10:46 UTC, 16 Nov; the file is dated 1 Oct | observed |
| Grants on 30 new tables | to check | **all good**: every table is readable by both roles except the 6 credential tables; the only withheld columns are `profiles.pin_hash` and `movie_night_sessions.invite_token`; no credential is readable by either | observed (catalogue) |
| Spec job gap 26 Oct → 5 Nov | miss or nothing due? | nothing due: a run row is written only when work exists; the heartbeat beats daily | implemented |

## 4. Queued and parked items in this lens, re-verified
| Item | Verdict |
|---|---|
| Railway restart-policy drift (unapplied since 26 Sep) | unverifiable here (token rejected); the code still says `ON_FAILURE`, 3 retries for `api` |
| `OWNER-ACTIONS.md` 9, revoke the April PAT | decayed premise: it reasons "the repo is private"; the token is dead, so no rewrite still holds |
| `OWNER-ACTIONS.md` backup key into a password manager | still open; raised by DS50-04 |
| `OWNER-ACTIONS.md` 22, Neon password rotation | still open; not re-checked (a credential change, Craig's) |
| #371 dependency audit | accurate: CI's audit job runs `pip-audit` and `pnpm audit` on every push; Dependabot alerts are off, so an advisory on a quiet week waits for the next push |

## 5. For reconsideration · Hypotheses · Limitations · Probe log
**For reconsideration:** #257 (backups as Actions artifacts) holds, on one condition: the key's second
copy (DS50-04). Its premise "the repo's owner holds the only key" is the single point of failure.

**Hypotheses:** the two abandoned sold-store runs on 11 Nov (00:21 and 02:21, "No heartbeat for 30
minutes") look like the process dying mid-pass, perhaps a Railway limit; only the deployment's logs
can say. `refresh_tokens` is never pruned (100 rows, hashes only): harmless at this size. CR49-01
(R1) is the likeliest way the 08:00 job goes dark; DS50-01's reminders row is what would name it.

**Limitations:** no Railway read (token rejected), so no cron execution history, exit codes, logs,
variables, plan, or whether a Sentry DSN is set. The ODEON fix (`a2caf8c`, PR 161) was read in its
commit only, as drift. CSP and the web token storage were not re-tested. No cinema page, robots or
terms read (0 of 20): the fetch is a bounded client with a named user agent, 49–99 requests a run.

**Probe log** (no paid calls; no TMDB, eBay, Brave or cinema calls):
- 11 projected `SELECT`s via `mcu_readonly`: table and column privileges for both roles (4), role
  attributes, RLS count, credential-like column names, TMDB sync ages, Letterboxd usernames (2 rows,
  held in scratch, grepped as counts only), table live-row counts, profile column names.
- 1 Railway CLI call (`deployment list`), rejected. GitHub: repo metadata, events, security settings,
  Dependabot and secret-scanning endpoints, branch protection, backup runs (8 `gh` calls) and one
  unauthenticated GET to the repo's API URL (HTTP 200).
- 1 local derivation of the backup key's public half, compared to the recipient file; nothing printed.
