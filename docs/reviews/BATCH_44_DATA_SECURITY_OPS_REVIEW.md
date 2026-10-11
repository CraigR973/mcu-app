# Batch 44 — Data, security and ops review (wave 1, pass R2)

**Pass R2** · reviewed SHA `527522d` · lens: security and site-reliability engineer (DS) · read-only ·
paid calls: none. Written 11 Oct 2026.

## 1. Summary

Grade **C**. Sound locks, no alarms, no backup: the security work is careful, but no failure
reaches anyone, and nothing beyond Neon's six hours could undo a bad day.

1. **Correct and safe:** the locks hold (PIN design, sealed eBay tokens, per-person scoping, a
   read-only role that cannot see a credential, a clean history apart from the known PAT). The
   exposure is recovery: no backup outside Neon's six-hour window, while the owner password sits
   in two transcripts and in a file one `cd` from a third (DS44-03).
2. **Honest:** a phone the server has dropped still says "Notifications are on", and the eBay run
   records "5 pushed" for pushes nobody received (DS44-02).
3. **Doing its job:** alerts, the one way the app reaches out, have never reached Mark and lapsed
   unseen for Craig from 8 to 11 Oct (DS44-02).
4. **Noticed:** no. No error reporting runs, the only red light is lit every night by design,
   idle and stopped jobs look alike, and every failure so far was found by someone looking
   (DS44-01; table after the findings).
5. **Cheap to run:** yes today (91 MB of a 1 GB cap), but two unmeasured allowances, Neon's
   compute hours and egress, would stop the whole app if used up, and CI runs near GitHub's
   allowance (hypotheses).

## 2. Findings (7: 3 High, 1 Medium, 3 Low)

### DS44-01 — High — Nothing that fails reaches Craig; every failure so far was found by someone looking
- **Evidence:** `computed` — no error reporting runs. The API starts Sentry only if
  `SENTRY_DSN_BACKEND` is set, and Railway's plan reads "0 to destroy" with every variable managed
  by the repo, so no undeclared variable exists on any service (observed). The served web bundle
  has no Sentry DSN (observed); the crons never start Sentry (implemented). A cron reports only
  through its exit code and log, kept 7 days on Hobby (Railway's pricing); `/health/ready` is read
  at deploy and never again. Only the valuation's last error reaches Home; every other job's state
  waits on its own admin page (implemented).
- **The one alarm is noise:** `cron-scrape` exits non-zero whenever a shop refuses, so Railway
  shows it Crashed every night (observed; 21–29 refused requests a night since 30 Sep) and a real
  crash would look the same. **Idle looks like stopped:** the spec, valuation and eBay jobs write
  no row and exit 0 when nothing is due or the budget is spent (implemented): no spec row 4–10 Oct
  (only the reviews row shows the job ran) and no valuation row on 1–2 Oct (observed).
- **Track record:** crons crashed on every run 10–23 Sep, noticed on 11 Sep by an agent looking for
  a row that never came; the TMDB token was missing until someone added a film (9 Sep); Brave's 402 on
  28 Sep was found by an agent's check that day; the eBay scan has been blind since 9 Oct (28 runs
  ended "finished") and Craig's push died on 8 Oct, both found by this review's check-in; Mark's
  push has never worked (DS44-02). The app raised none of them.
- **What the user or operator experiences:** Craig hears of a failure only when he or an agent
  goes looking, days later and sometimes after the 7-day logs are gone; Mark never does.
- **Fix and cost:** one daily check pass inside the 08:00 reminders job, reading tables the app
  already writes: each job's last row within its cadence (with a "nothing due" heartbeat row), the
  eBay scan seeing listings in its last six runs (R1's guard for CR43-01), each person holding a
  live device with recent notifications not all suppressed, the spec integration not halted,
  readiness all configured, the database under half its cap, and any lockout (DS44-05). It reaches
  Craig two ways: a "Needs attention" row at the top of Home, which works when push is what broke,
  and a push. `cron-scrape` exits 0 when only shops refused (#240: refusals are not failures). About
  a day with tests. Backend Sentry (one Railway variable, Craig's) would add crash reports, but its
  "new issue" rules fire once per issue, so it complements the pass rather than replacing it.
- **Where it goes:** new row, first in the roadmap's ops group; the delivery half of R1's eBay
  guard and of DS44-02.

### DS44-02 — High — A phone's notifications die silently, and the phone keeps saying they are on
- **Evidence:** `observed` — Mark has never received a push: 102 notifications since 10 Sep,
  0 delivered (101 suppressed for want of a device, 1 failed). In the 24 Sep 08:04 reminder pass
  his first send failed and every later one in that pass was suppressed: the code's signature of
  the push service answering 404 or 410 and the device being deleted (implemented). Craig's went
  the same way at 00:21 on 8 Oct; Railway's log reads "push_subscription_gone status_code=410", and
  his next 5 notifications were suppressed. `implemented` — a 404 or 410 deletes the device row
  with an info log and nothing else. The settings page decides "Notifications are on for this
  device" from the browser's own subscription, never the server's, so it can show that line above
  "No devices are registered yet", and it hides "Turn on" meanwhile. Nothing registers a device
  again: the service worker's subscription-change handler only asks the page to re-read local
  state. The eBay run counts deals queued as "pushed", so its rows read "5 pushed" a day while all
  of Mark's were suppressed.
- **Drift after the snapshot:** Craig turned notifications back on at 08:39 UTC on 11 Oct (one
  movie-night push delivered, one new device row). Mark's are still off.
- **What the user or operator experiences:** Mark has had no deal, release or movie-night alert in
  a month and nothing tells him; Craig lost three days of deal alerts without knowing.
- **Fix and cost:** on app open, compare this phone's subscription with the server's list and
  register it again if the server has lost it (registration is already an upsert on the endpoint);
  have the subscription-change handler do the same; when a person's last device goes, show them a
  banner ("Notifications stopped reaching this phone on 8 Oct — turn them on again") and tell
  Craig through DS44-01; count delivered, not queued. Half a day with tests. Mark still has to turn
  notifications on once (`OWNER-ACTIONS.md` 16b).
- **Where it goes:** new row beside DS44-01; R6 owns the wording.

### DS44-03 — High — No copy of the database exists outside Neon, and Neon's free plan keeps six hours
- **Evidence:** `observed` — the server reports `neon.max_cluster_size` 1,024 MB, the free plan's
  cap (#17 chose Neon's free capacity). Neon's plan terms (read 11 Oct): restore has a "6-hour
  limit, capped at 1 GB of change history"; "1 manual snapshot"; "scheduled backups are not
  available on the Free plan". `implemented` — no dump, export job or restore runbook exists;
  app-starter's scheduled backup did not come across in the re-scaffold; Part D re-scoped Phase
  13.7 to "confirm PITR is on and write the re-import runbook", and no ledger row holds it.
- **What a loss beyond six hours costs** (`computed`): 191 film changes from the 25 Sep identify
  run, 146 editions, 729 discs' specs and 616 review scores (about 2,000 Blu-ray.com page fetches
  since 24 Sep, plus Brave credit), 1,300 valuations (about 1,600 eBay calls), 1,566 watches
  (rebuildable only while the CSVs survive on the Mac), and Mark's edits, the wanted list, 271
  deals, chats and movie nights, which nothing rebuilds.
- **Aggravating** (`observed`, booleans only): the Neon owner password, with full rights and used
  by the API and every cron, is in two session transcripts (25 Sep, 4 Oct; `OWNER-ACTIONS.md` 22,
  unrotated), and `apps/api/.env` still holds it, so the next `cd apps/api` prints it a third
  time. Migrations run on every boot and close-out merges without a second confirmation (#24); the
  10 Sep plan and 18 Sep refresh near-misses show how close a destructive change can come.
- **What the user or operator experiences:** a bad migration, import or data fix noticed the next
  morning cannot be undone; the catalogue would be rebuilt from the spreadsheet, losing weeks of
  curation and paid lookups.
- **Fix and cost:** a weekly `pg_dump` (a GitHub Actions schedule or a Railway cron) to storage
  outside Neon, 8 copies kept, through a role like `mcu_readonly` that reads all but credentials (a
  restore then signs both people out and asks for push again: acceptable), and a monthly restore
  drill into a scratch database that counts rows; the drill is the guard. Weekly, not nightly: a
  dump moves about the database's size in egress, 0.4 GB a month of the free 5 GB, where nightly
  takes over half. About half a day; where to store it is Craig's choice (Actions artifacts need
  no new account and keep 90 days). Neon's paid plan widens the window instead (Craig's call, at
  Neon's price). `OWNER-ACTIONS.md` 22 step 3 is one line out of a file on the Mac.
- **Where it goes:** new row, early in the roadmap; the drill joins the guard list.

### DS44-04 — Medium — The gate cannot see a missing outside key or a web build left behind
- **Evidence:** `implemented` — `/health/ready` reports push, the assistant and eBay but not TMDB
  or Brave; the TMDB client sends an empty token when its variable is missing, which TMDB refuses:
  the 9 Sep outage that the readiness code names as its reason, still unreported. The close-out
  gate reads only `db: ok` and the API's commit. `observed` — the web bundle does carry its commit
  (the Sentry build plugin injects it as the release id: `527522d` on 11 Oct, matching the API,
  which corrects scope finding 10), but nothing compares the two. A Vercel build that fails after a
  merge leaves the web a commit behind, and with closed enums a new API value fails a screen
  (CR43-04).
- **What the user or operator experiences:** search, identify and the calendar answer "temporarily
  unavailable" with every check green; a stale web build fails one screen.
- **Fix and cost:** TMDB and Brave (presence only) in readiness; the gate asserts every field
  "configured" and that the served bundle's release id is the merged commit (two GETs). Under an
  hour. Both checks are guards.
- **Where it goes:** new small row; guard list.

### DS44-05 — Low — PIN guessing is slowed, not stopped, and nobody would know
- **Evidence:** `implemented` — five wrong PINs lock a profile for 15 minutes, the count restarts
  at each lock with no escalation, and the lock is a log line only. From many addresses a guesser
  gets 480 tries a day per person, so a four-digit PIN (9,966 allowed) falls in about ten days on
  average. Names are guessable, and a lock (423) confirms one exists. Nobody has typed a PIN since
  22 Sep, so neither person would meet a lock. `observed` — no login attempt at all in the API's
  logs 5–11 Oct (4 renewals): no sign of guessing. PIN lengths are unknown (the hash is withheld).
- **Fix and cost:** lockouts reach Craig through DS44-01; each further lock in a day doubles
  (15 minutes, 1 hour, 4 hours, 24 hours); six digits for the admin at the next change. An hour.
- **Where it goes:** fold into DS44-01's row.

### DS44-06 — Low — Two outside services' terms are not met
- **Evidence:** Brave's API terms (§3(b)(i)) bar storing "a database of Search Results" beyond
  transient storage. `spec_candidates` holds 15,283 Brave results (address, title, snippet;
  9.2 MB), 8,868 of them for discs already decided (observed); they are deleted only when a disc is
  searched again (implemented). No decision weighs the clause (#202). Brave may suspend "after a
  five day cure period" on written notice, which stops spec, review and identify searches. TMDB's
  terms require its logo and a "not endorsed" notice (neither is in the web app, implemented) and
  bar caching "for longer than 6 months": the 1,680 films were last synced 8 Sep–10 Oct, most on
  8 Sep (observed), so most pass six months on 8 Mar 2027, with no refresh scheduled.
- **Fix and cost:** delete a lookup's candidates once decided (keep the accepted address); one TMDB
  attribution line in Settings; refresh TMDB fields older than 150 days inside the calendar
  refresh. About two hours.
- **Where it goes:** new small row; the TMDB refresh has a date trigger (before 8 Mar 2027).

### DS44-07 — Low — The web page's security policy still trusts any Railway app and a database it left
- **Evidence:** `observed` (response headers, 11 Oct): `connect-src` allows any `*.up.railway.app`,
  `*.supabase.co` and `*.sentry.io`; `img-src` allows `*.supabase.co`. The app talks to one Railway
  host, Supabase is gone (#17) and Sentry is off. Scripts are same-origin only, so this matters
  only after an injection, where it lets a script post to any Railway app.
- **Fix and cost:** name the one API host; drop Supabase, and Sentry until it is on. 15 minutes.
- **Where it goes:** fold into DS44-04's row (Part D's D5 residue).

### Failure classes: who would know today

| Failure | Caught today by (reaches Craig?) | What Craig and Mark see |
|---|---|---|
| A cron crashes or never fires | A red job on Railway, unwatched (no) | Stale data, no message |
| An idle job, or a stopped one | Nothing: both write nothing (no) | Nothing |
| A shop refuses | A count in the run row (no) | Fewer prices |
| Brave credit out (402) | The run's error on Disc specs (if he looks) | Specs stop arriving |
| eBay keyset or a person's token lapses | Run "stopped"; a refused token is deleted (no) | 502 or 503 on value and eBay screens |
| Anthropic refuses (credit or cap) | The usage log's error (no) | An error in the chat (R3) |
| A variable goes missing | Readiness for 3 of 5 keys, read by nobody (no) | "Temporarily unavailable" |
| Neon down, a connection dropped | Readiness 503, read by nobody (no) | Error screens; writes queue offline |
| Web and API out of step | Nothing compares them (no) | One screen fails |
| A push never arrives | A deleted row, an info log (no) | Silence; "on" in Settings |
| Neon hours or egress used up | Neon's own email, if any (unverified) | Whole app down until next month |
| The database fills (1 GB) | Nothing; 91 MB today (no) | Every write fails |
| A backup does not restore | There is no backup | — |

## 3. Follow-through corrections (rows of the pack's table in this lens)

| Row | Pack says | Corrected to | Evidence |
|---|---|---|---|
| Scope 10 | Only the API reports its commit | The bundle carries it as the Sentry release id; nothing compares the two (DS44-04) | `observed` |
| LIVE, scope 13 | 43 refresh tokens live | 43 rows, revoked ones included: each renewal revokes a row and adds one, and none is deleted. Open sessions unknown (the role cannot read the table) | `implemented`, statistics |
| LIVE | `push_subscriptions` count ambiguous | None live from 8 Oct 00:21 (the 410 and the delete path agree); one since 08:39 UTC 11 Oct, Craig's (drift) | `observed` |
| Scope 2 | Mark's suppressed "throughout" | Mark had a device on 24 Sep; the push service refused its first send and it was deleted. No delivery ever | `observed`, `implemented` |
| `OWNER-ACTIONS.md`, AGENTS | The API has no restart policy, so a crash never restarts; the plan's change is worth applying | Railway's docs: "The default is `On Failure` with a maximum of 10 restarts", so the apply would cut retries from 10 to 3. Likely, not proved: the docs do not say what an unset policy means | primary source |
| DIGEST §1 | Neon, 91 MB, plan unstated | The free plan: 1 GB cap (9% used), 6-hour restore, no scheduled backups | `observed`, Neon docs |
| Scope 4 | Idle jobs leave no record | Confirmed; only the reviews row shows `cron-specs` ran 4–10 Oct, and `cron-values` leaves no trace | `observed` |
| Lens brief | Migration 018 still creates `gift_links` | Migration 030 drops it; chain and database agree | `implemented` |

## 4. Queued and parked items in this lens, re-verified

| Item | Verdict |
|---|---|
| `OWNER-ACTIONS.md` 22, rotate the Neon owner password | Accurate and weightier than it reads: step 3 is undone (observed), and with no backup a misused owner credential is unrecoverable after six hours (DS44-03) |
| `OWNER-ACTIONS.md` 9, revoke the April PAT | Accurate: a `ghp_` token in `0bfb672` and `9084ec6` only. Ten credential shapes scanned across all history found nothing else (a Neon address in a test is a fake: other host, other password) |
| `OWNER-ACTIONS.md` 16b, Mark turns notifications on | Incomplete: he did once, and it died unseen on its first send (DS44-02) |
| `OWNER-ACTIONS.md` 28, Batch 22c, a fixed outbound address | Accurate (fixed addresses need Railway Pro). Today's cost: the 29-minute nightly wait (scope 5) and the false Crashed alarm (DS44-01) |
| T8b, Connect eBay (scope 12) | Sound in this lens: tokens sealed with AES-GCM under a key derived from the app's secret and bound to the person; a sign-in state is one-time, lasts ten minutes and only its starter can finish it; every route uses the caller's id. Real eBay answers unproved (R5) |
| #74, iCal token in a query string | Holds: 256-bit, hashed, rotated, rate-limited, no personal data in the feed. Caveat: the server's access log writes the address, token included, into Railway's 7-day logs |
| #127, eBay deletion notices | Holds: 204 without touching the database; 17 arrived in 14 minutes on 11 Oct (about 1,750 a day) |
| Scope 14, two spreadsheets | Accurate: untracked and not ignored; each 1,886 rows of title, format, location and category, no personal column. Ignore `*.xlsx`; as the only import source they belong in DS44-03's backup |

## 5. For reconsideration · Hypotheses · Limitations · Probe log

**For reconsideration.** #17 (Neon's free capacity): the free plan's six-hour restore and its bar on
scheduled backups are new evidence; reconsider only if Craig prefers paying Neon to running a dump.
#24 (close-out deploys without a second confirmation) stands; a tested backup is what keeps it safe.

**Already near-optimal (no change):** the PIN design beyond DS44-05 (bcrypt, timing padding, a
durable counter, separate secrets, rotation on every renewal, every session revoked on a PIN
change, a web server that refuses weak secrets); eBay token sealing; the iCal feed; per-person
scoping of chats, usage, notifications, devices and eBay data (watch history and loans are shared by
design); a read-only role that cannot read any credential table or the PIN hash (proved from the
catalogue, never by selecting); the API's headers and CORS; live streams that carry the token in a
header; and a history with no credential beyond the PAT and no personal data file.

**Hypotheses** (no evidence of harm yet):
- **CI minutes:** about 11 billable minutes a run; 100 runs on 1–11 Oct is a pace of about 3,000 a
  month, GitHub Pro's private allowance and above Free's 2,000 (GitHub's docs). Plan unknown; on Free
  with no payment method CI "is blocked" mid-month and close-out stalls. Overage: $0.006 a minute.
- **Neon compute hours and egress are unmeasured:** five crons wake the database about 16 times a
  day and the shop check holds it 29 minutes a night. Using up either "suspends compute until the
  next billing period": the whole app. One look at Neon's usage page settles it.
- **Why Mark's device was refused on its first send** went with the logs (7 days). The usual causes
  are the app removed and re-added, or permission withdrawn; re-registering on open covers the first.

**Limitations.** No access to Neon's, Vercel's or GitHub's billing pages; Railway keeps 7 days of
logs and its edge log showed 14 minutes; backend Sentry's absence is inferred from the plan; the 12
app screenshots in `docs/ui-redesign/` were not opened.

**Probe log** (11 Oct):
- Production, read-only role: 19 SELECTs, each under 25 rows, no JSON, blob or credential column:
  columns of 16 ops tables; the role's privileges on 14 tables (catalogue only); every row of the
  scrape (19), spec (14), review (8) and valuation (6) runs; eBay runs by day (16); notifications by
  role and status, and in three windows (time, role, category, status); device-table statistics; a
  fixture username against profiles (booleans); Neon's size settings; edits by table; four counts
  of hand-made rows; the films table's timestamp columns and sync ages; four lookup tables' column
  names; one table's size; stored search results by decision.
- Railway, read-only: `deployment list` for six services (two at 200); `logs` for `cron-ebay`
  (filtered, 1 line), `cron-reminders` on 24 Sep (empty, past retention; one timeout), `api` since
  5 Oct (filtered, counts only) and the edge log (counted, no addresses printed); `config plan` once
  (two tries before it stopped on the Node version; values masked).
- HTTP: 2 GETs to Vercel (page, bundle) and 2 to Railway (`/health`, `/health/ready`). GitHub: run
  list (300, metadata), timing and jobs for 3 runs, repo visibility; billing refused (needs a scope).
- Public documents: Neon pricing and plans; Railway pricing and restart policy (one search); TMDB
  and Brave API terms; GitHub Actions billing; eBay's licence page refused (403).
- Local: a credential-shape scan of all history (counts and commits only), blob sizes, file types
  ever added, two spreadsheets' headers, two booleans from `apps/api/.env`. Outside services (eBay,
  TMDB, Brave, Anthropic): none. Paid calls: none.
