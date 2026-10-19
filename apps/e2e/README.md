# @mcu/e2e — the end-to-end suite (Batch 38, Phase 13.10)

The built web bundle, in Chromium, Firefox and WebKit, against the real API on a real Postgres,
with **every outside service faked**; plus the five cron jobs run the way Railway runs them.
`DECISIONS.md` #285 records why it is shaped like this.

```
 Playwright (chromium · firefox · webkit · jobs; one worker, no retries)
    │ browser ─► vite preview  http://localhost:4173   the production build, VITE_API_URL=http://127.0.0.1:8000
    │                          (two origins, as Vercel and Railway are; never the dev proxy)
    ▼
 API  http://127.0.0.1:8000    uvicorn, cwd = apps/e2e/.run (no .env there to read)
    │ every outbound call ─►  sitecustomize ─► apps/api/tests/outside_world (the fake world)
    ▼
 a throwaway Postgres          CI: the service container · Mac: pgserver (below)
```

## Run it

You need a **throwaway** Postgres server and nothing else outside the repo. Never Neon, Railway
or production: the harness refuses a URL that looks hosted, and the fake world refuses to arm
against one.

```bash
# once per sitting: a local server (pgserver is in the API venv); keep the path short
apps/api/.venv/bin/python3.12 -c "import pgserver,pathlib; s=pgserver.get_server(pathlib.Path('scratchpad/e2e-pgdata'), cleanup_mode=None); print(s.get_uri('postgres'))"

export E2E_DATABASE_URL='<that URL>'          # CI: postgresql://postgres:postgres@localhost:5432/postgres
export PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH"
pnpm --filter @mcu/e2e e2e                    # all four projects, one after the other
pnpm --filter @mcu/e2e e2e chromium           # one browser
pnpm --filter @mcu/e2e e2e jobs               # the cron jobs only
pnpm --filter @mcu/e2e exec playwright test --project=chromium specs/scan.spec.ts   # one file
```

Browsers come from Playwright 1.60.0 (`pnpm --filter @mcu/e2e exec playwright install chromium
firefox webkit`, once). `E2E_SKIP_BUILD=1` reuses the last bundle; `E2E_RESEED=1` rebuilds the
seeded database; `E2E_VERBOSE=1` prints every Python job's output; `E2E_PROBE_DIR=<dir>` makes a
`probe(page, name)` call in a case save what the page says (a no-op otherwise).

Each project starts from a fresh copy of one seeded database, so the order of cases is free.
The seed is rebuilt whenever the migrations, the seed scripts or the fake world change.

## What runs where

| Project | Cases |
|---|---|
| `chromium`, `firefox`, `webkit` | login · import (the CLI, then the screens) · search · add via barcode · shop price alert and eBay alert · chat · movie night · offline replay and cross-origin worker · version drift and a missing chunk · box sets, smart collections, photos, eBay accounts · Tell Craig and the Archive's first screen |
| `jobs` | `daily_scrape`, `run_reminders`, `spec_backfill`, `ebay_watch`, `value_collection`, each as `python -m src.scripts.<job>` |

## The fake outside world

`apps/api/tests/outside_world/` answers TMDB, eBay (Browse, OAuth, Trading), Brave, Blu-ray.com,
the shops, the model (the real streaming format, through the real SDK) and the push services
(it decrypts what the app sent, with the subscription's private key). It is armed by
`apps/e2e/fakes/sitecustomize.py` in every Python process the harness starts, and it **fails
closed**: a host it does not know fails the call and is logged; a name lookup or a socket to
another machine is refused; a failure to arm ends the process. Both HTTP libraries in the
process are covered (`httpx`, and the `httpx2` the `anthropic` SDK brings: patching only the
first once let one request reach api.anthropic.com).
`apps/api/tests/test_outside_world.py` pins all of this.

A case tells the fake what to say with `world.setScenario({...})` (cleared before every case)
and reads what the app asked with `world.calls(host)` and `pushesTo(device)`. Any call to an
unfaked host, or to a path on a faked host nobody wrote, fails the case that caused it.

## Rules for adding a case

- Roles and labels, not test ids. Seed through the app's own paths (the import CLI, its
  endpoints), never a shared live fixture and never a direct insert except what a case must
  reset.
- **No retries, no loosened assertions to reach green.** A flaky case is a defect.
- A skip must say why, in the report: `test.skip(condition, 'reason')`. Firefox has no Web
  Speech API, so dictation is skipped there on purpose and visibly. Under Playwright's WebKit two
  cases are skipped for reasons recorded in `DECISIONS.md` #285 (the replayed write's lost answer,
  and the live match on an open page). Any other skip is a defect.
- Wait for the state you need (`expect.poll`, a visible element), never for a time. Let a screen
  finish loading before leaving it.
- Cases that are not about the service worker run without one (`signedIn(person)`); ask for it
  with `signedIn(person, { worker: true })` and wait for it to take control.

## What this suite cannot prove

Reading a barcode from a real camera, the tap on a real push notification, speech recognition
(no microphone), and a real phone's behaviour. Those stay on `OWNER-ACTIONS.md`.
