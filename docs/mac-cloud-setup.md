# Cloud sessions without the Mac — the one-off setup on the Mac

**Who runs this:** a local Claude Code session on Craig's Mac, once, with Craig at the
keyboard for two clicks in Railway and one paste into the cloud settings.
**Start it with:** "Read and follow `docs/mac-cloud-setup.md` on `main`."

**Why** (`DECISIONS.md` #236): cloud sessions can already run the whole gate, ship, merge and
check production. Two things still need the Mac, because the credentials live only here:

- **Reading the live database.** The cloud container's proxy carries HTTPS only, so no
  Postgres connection leaves it. Neon also answers SQL over HTTPS (`POST https://…/sql`), so
  a cloud session can read the database through that with a **read-only role** made here.
- **Railway's CLI.** `config plan` needs a token. Applying stays Craig's word, as now
  (`CLAUDE.md`, "Still explicit").

On 1 Oct a cloud session reached both through its proxy, so no network setting should need
changing: Railway's API (`backboard.railway.com`) answered "Unauthorized" to a made-up token,
and Neon's SQL endpoint answered "password authentication failed" to a made-up user, which
is Neon reading the request, not the proxy refusing it.

## Rules for this session

- **Never print a secret** — not the owner `DATABASE_URL`, not the new role's password, not
  a Railway token. Secrets go into files in `~/.mcu-secrets/` (folder mode 700, files 600)
  and reach the clipboard with `pbcopy`, so they never appear in the transcript or in a
  chat. Print hosts, counts and yes/no results only.
- Never `cd` into `apps/api` (autoenv). Use absolute paths and `git -C`.
- `DATABASE_URL` in `apps/api/.env.local` is unquoted and contains `&` (`STATUS.md`
  gotcha 27): read it with `grep '^DATABASE_URL=' … | cut -d= -f2-`, never by sourcing the
  file. Pass it to Python through an environment variable, not a command-line argument.
- **No data is written.** The only database changes are one role and its grants.
- Railway: `config plan` only. **Never `config apply` here.**
- Nothing to commit. The next cloud session checks the result and records it.

## Step 1 — the read-only role (the session does this)

1. `git -C /Users/craigrobinson/mcu_app pull` on `main`.
2. With the API venv's Python (`apps/api/.venv/bin/python3.12`) and **psycopg2**, which takes
   Neon's URL exactly as `.env.local` holds it, connect as the owner and, in one
   transaction:
   - Generate the password inside the script (`secrets.token_urlsafe(32)`). Build the
     read-only connection string from the owner's: same scheme, host, port, database and
     query string (`sslmode=require` and so on), user `mcu_readonly`. Write it to
     `~/.mcu-secrets/neon_readonly_url` (mode 600). Never print it.
   - `CREATE ROLE mcu_readonly LOGIN PASSWORD …`, or `ALTER ROLE mcu_readonly PASSWORD …`
     if it exists already (a re-run rotates the password).
   - `GRANT CONNECT ON DATABASE <current_database()> TO mcu_readonly`,
     `GRANT USAGE ON SCHEMA public TO mcu_readonly`,
     `GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcu_readonly`.
   - **Then take back whatever holds a credential:**
     `REVOKE SELECT ON refresh_tokens, calendar_feed_tokens, push_subscriptions,
     rate_limit_counters FROM mcu_readonly`. For `profiles`, revoke the table and grant
     every column **except `pin_hash`** (a four-digit PIN's bcrypt hash falls to 10,000
     guesses); for `movie_night_sessions`, every column except `invite_token`. Then query
     `information_schema.columns` for any other column whose name contains `hash`, `secret`,
     `password` or `p256dh`, or ends in `_token`, and leave it out the same way (the AI
     usage counts, `input_tokens` and the like, are only counts and stay). Report each table
     and column excluded.
   - `ALTER ROLE mcu_readonly SET default_transaction_read_only = on`, and
     `ALTER ROLE mcu_readonly SET statement_timeout = '30s'`.
   - **No default privileges.** A table added later stays unreadable to the role until its
     own migration grants it (`AGENTS.md`), so a new table holding a credential cannot leak
     by being forgotten.
3. **Prove it**, printing results only:
   - As `mcu_readonly` over psycopg2: `SELECT count(*) FROM movies` returns a number;
     `SELECT pin_hash FROM profiles` is refused; `UPDATE movies SET title = title WHERE
     false` is refused; `SELECT count(*) FROM refresh_tokens` is refused.
   - **Over HTTPS, as a cloud session will**, with curl, the URL read from the file and the
     output limited to the HTTP status and the row count:
     `POST https://<host>/sql`, headers `Neon-Connection-String: <the read-only URL>` and
     `Content-Type: application/json`, body
     `{"query": "SELECT count(*) AS films FROM movies", "params": []}`. Expect `200` and a
     JSON `rows` holding the count. If that host answers an error, try
     `https://api.<host without its first label>/sql` the same way. **Record which form
     answered**; `src/scripts/live_sql.py` tries both, in that order.
4. Tell Craig the **host** (it is not a secret), then run
   `pbcopy < ~/.mcu-secrets/neon_readonly_url` and tell him it is on his clipboard for step 3.

## Step 2 — a Railway token (Craig makes it, the session tests it)

1. The session reports `railway --version` and runs `railway status` in the repo, with Node 22
   first on `PATH` and the CLI by its full path (`.railway/README.md`, "Two things that will
   bite"), and reports the project and environment names.
2. **Craig:** Railway → project `mcu-app` → Settings → Tokens → create a **project token**
   for the `production` environment, and copy it. Then tell the session, which saves it with
   `pbpaste > ~/.mcu-secrets/railway_token` and `chmod 600`, without displaying it.
3. The session runs a **plan**, read-only, with the token from the file:
   `RAILWAY_TOKEN="$(cat ~/.mcu-secrets/railway_token)"` before the same Node 22 + full-path
   `railway config plan`.
   - **Plan succeeds** → the cloud variable is `RAILWAY_TOKEN`.
   - **Refused for permissions** → Craig creates an **account token** instead (Account
     settings → Tokens; a workspace token if he has a workspace), saved the same way; the
     session retries with `RAILWAY_API_TOKEN`, and reports the project's ID
     (`railway status --json`; an ID is not a secret). The cloud then needs
     `RAILWAY_API_TOKEN` and `RAILWAY_PROJECT_ID`.
   - Report the plan's summary line. Expect nothing to add, change or destroy: the last
     apply was 28 Sep (U4) and nothing in `.railway/railway.ts` has changed since.
4. When Craig is ready for step 3, `pbcopy < ~/.mcu-secrets/railway_token`.

## Step 3 — the cloud environment's settings (Craig, about five minutes)

In any cloud session on this repo: the environment menu in the session's title bar → **Edit**:

- **Environment variables:** `NEON_READONLY_URL` = the read-only URL (step 1's clipboard), and
  `RAILWAY_TOKEN` = the token (step 2's clipboard). If step 2 needed an account token:
  `RAILWAY_API_TOKEN` and `RAILWAY_PROJECT_ID` instead.
- **Network access:** nothing today. If a new session reports a blocked host, add the one it
  names. Before V9, allow `blu-ray.com` and `avforums.com` (`OWNER-ACTIONS.md`).

A **new** cloud session picks the variables up; its startup hook says which it found.

## Step 4 — hand back

Tell Craig to start a new cloud session with: **"Check the cloud setup (`OWNER-ACTIONS.md`
27) and record it."** That session runs a read-only count and an `EXPLAIN` through
`src.scripts.live_sql`, a `railway config plan`, and records the result in `STATUS.md` and
`OWNER-ACTIONS.md`. It also runs V5's open check: the Highlights query plans on production's
own rows.
