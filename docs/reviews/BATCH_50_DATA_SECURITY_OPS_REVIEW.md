# Batch 50 — Data, security and operations review (wave 2, pass R2)

**Pass R2** · reviewed SHA `1668071` · lens: security and site-reliability engineer · read-only · paid calls: none.

## 1. Summary
_(written last)_

## 2. Findings (at most ten, Highs first)

### DS50-01 — High — The daily check watches four of the eight scheduled jobs, so a dark cinema, a dead 08:00 job or a failed backup reaches no one (P1, noticing half)
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
