# Railway infrastructure

Batch 2 defines the production API service in `.railway/railway.ts` using Railway's
project-level Infrastructure as Code format. The legacy `railway.toml` format cannot be
enabled for new services.

**Live since 2026-09-07.** Project `mcu-app`, environment `production`, service `api`,
region `ams`, deploying `main` from `CraigR973/mcu-app` via the root `Dockerfile`.
Public URL: `https://api-production-a8fe.up.railway.app`.

## The scheduled jobs

Four cron services share the API's image and run a different entry point (`DECISIONS.md`
#60, #119). They are separate services because a Railway cron runs the service's own start
command and expects it to **exit** — `api` runs uvicorn, which never does, so a schedule on
`api` would restart the API on a timer instead of scraping anything.

| Service | Command | Schedule (UTC) |
|---|---|---|
| `cron-scrape` | `python -m src.scripts.daily_scrape` | `0 3 * * *` |
| `cron-reminders` | `python -m src.scripts.run_reminders` | `0 8 * * *` |
| `cron-specs` | `python -m src.scripts.spec_backfill` | `0 2 * * *` |
| `cron-ebay` | `python -m src.scripts.ebay_watch` | `20 */2 * * *` |

All four take `DATABASE_URL` and the three VAPID variables **by reference** from `api`, so
there is one copy of each secret. `restartPolicyType` is `NEVER`: these make live requests
to real shops, and retrying a failed night automatically would turn one bad night into
three. Railway skips a scheduled run whose previous run is still going, and the minimum
interval it accepts is five minutes. `cron-specs` also takes `BRAVE_SEARCH_API_KEY` from
`api` the same way (Batch T7), and `cron-ebay` takes `EBAY_CLIENT_ID` and
`EBAY_CLIENT_SECRET` (Batch T8a).

## Two things that will bite

1. **Run the Railway CLI on Node 22+, and call it by its full path.** Two separate
   traps that look like one.

   Its IaC engine invokes Node's type-stripping flag, which Node 20 does not support, so
   `plan` fails before touching any infrastructure. But **the CLI itself is installed under
   Node 20's nvm bin** (`nvm alias default` is 20) and is an `#!/usr/bin/env node` script —
   so putting Node 22 first on `PATH` makes `node` correct and makes `railway` *disappear*,
   because it was never in Node 22's bin. The result is `bash: railway: command not found`,
   which reads like a missing install rather than a `PATH` order problem.

   Both at once — Node 22 for the engine, absolute path for the binary:

   ```
   PATH="$HOME/.nvm/versions/node/v22.23.2/bin:$PATH" \
     "$HOME/.nvm/versions/node/v20.20.2/bin/railway" config plan
   ```

   This works from a shell with no nvm loaded at all, which the bare-`railway` form does
   not. The app's own build stays on Node 20.

2. **The domain must target Railway's injected `PORT` (8080), not the Dockerfile's
   `EXPOSE 8000`** — see `DECISIONS.md` #20. Getting this wrong returns a public 502 while
   the container is perfectly healthy. After creating a domain, check that
   `railway domain list` agrees with the `Uvicorn running on` line in `railway logs -d`.

## First-time setup on a new machine

```bash
railway link                       # NOT railway init — the project already exists
railway status                     # confirm project/environment/service
```

## Re-provisioning from scratch

```bash
railway init --name mcu-app
railway add --service api
railway variable set DATABASE_URL --stdin --service api --skip-deploys
railway variable set FRONTEND_ORIGIN=https://YOUR-VERCEL-DOMAIN --service api --skip-deploys
railway config plan                # read-only
railway config apply
railway domain --service api --port 8080
```

## Read the destroy count before every apply

`plan` is read-only. Do not run `apply` outside the explicit phase-closeout workflow — and
**read the `N to destroy` line before you do**, because the dangerous change here is not one
you authored. On 2026-09-10 a plan read `2 to destroy`, and the two were
`ANTHROPIC_API_KEY` and `TMDB_READ_TOKEN`: set in the console, never declared in
`railway.ts`, and therefore drift for IaC to remove. Applying would have recreated the TMDB
outage of 2026-09-09 exactly. `DECISIONS.md` #124.

**The rule:** anything that exists in Railway is declared in `railway.ts`, and anything
already set is declared `preserve()` — which names the variable without putting its value in
this repository. A healthy plan for a variable change reads `0 to destroy`.

**One line that stays after an apply (seen 26 Sep):** `~ Update api deploy.restartPolicyType
(null → "ON_FAILURE")`. The file declares Railway's default explicitly and Railway appears to
store its default as unset, so every plan lists it. It changes nothing; read past it.

Sealed variables cannot be read back to compare, so declaring one as a generated value makes
every plan report it as changing. The two JWT secrets are `preserve()` for that reason:
applying a regenerated secret would sign both people out.

Every variable is preserved from Railway and supplied as a service variable; none is stored
in this repository. That now includes the two JWT secrets, which Batch 3 consumes and which
were generated once when the service was created.
