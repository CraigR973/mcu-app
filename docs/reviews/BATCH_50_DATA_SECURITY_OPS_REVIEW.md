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
