# MCU App — Claude Project Instructions

## Project
Mark's Cinematic Universe (The Real MCU). Monorepo at `~/mcu_app`.
Stack: Python 3.12 + FastAPI + React 18 + Supabase PostgreSQL + Tailwind CSS + shadcn/ui.

## Phase close-out protocol
At the end of every phase, always run ALL of these steps without being asked:

1. **Commit** all phase work with a descriptive message
2. **Push** to `origin main` (remote is SSH: `git@github.com:CraigR973/mcu-app.git`)
3. **Poll CI** via GitHub API until the run completes:
   ```bash
   curl -s -H "Authorization: token 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" \
     "https://api.github.com/repos/CraigR973/mcu-app/actions/runs?per_page=1"
   ```
4. **Fix any CI failures** — fetch job logs, fix, commit, push, re-poll until both `API` and `Web` jobs are green
5. **Append session notes** to `/Users/craigrobinson/mcu_app/session-log.md.txt`
6. **Update the phase status line** in `/Users/craigrobinson/mcu_app/MCU_Architecture_v2.1_FINAL.md`:
   - Use grep to find the line (never read the full file — it's 2,600+ lines)
   - Append ` ✅ YYYY-MM-DD` to the matching `**Phase X.Y: ...**` line
7. **Give the copy-paste prompt** for the next phase (pull content from `MCU_Architecture_v2.1_FINAL.md` via grep)

## CI polling helper
```bash
# Wait for a run to complete
RUN_ID=<id>
curl -s -H "Authorization: token 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" \
  "https://api.github.com/repos/CraigR973/mcu-app/actions/runs/$RUN_ID"

# Get job step results
curl -s -H "Authorization: token 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" \
  "https://api.github.com/repos/CraigR973/mcu-app/actions/runs/$RUN_ID/jobs"

# Get logs for a failing job
curl -sL -H "Authorization: token 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" \
  "https://api.github.com/repos/CraigR973/mcu-app/actions/jobs/<job_id>/logs"
```

## Key environment facts
- **autoenv** is installed — never `cd` into `apps/api` or `apps/web`; use absolute paths instead
- **Node**: system is v14; use `~/.nvm/versions/node/v20.20.2/bin/` for pnpm/node commands
- **Python**: use `apps/api/.venv/bin/python3.12` — system Python is 3.7
- **Alembic**: `PYTHONPATH=apps/api apps/api/.venv/bin/alembic --config apps/api/alembic.ini <cmd>`
- **pnpm**: `PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm <cmd>`
- **DATABASE_URL**: in `apps/api/.env.local` (gitignored) — live Supabase connection

## Repo structure
```
apps/api/        FastAPI backend (Python 3.12)
apps/web/        React 18 frontend (Vite + Tailwind + shadcn)
packages/shared/ Shared TypeScript types
migrations/      Raw SQL migrations (Supabase profiles etc.)
apps/api/migrations/  Alembic migrations (movies, movie_credits, ...)
session-log.md.txt    Append session notes here after each phase
MCU_Architecture_v2.1_FINAL.md  Master plan — update phase status lines here
```
