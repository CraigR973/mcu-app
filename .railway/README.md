# Railway infrastructure

Batch 2 defines the production API service in `.railway/railway.ts` using Railway's
project-level Infrastructure as Code format. The legacy `railway.toml` format cannot be
enabled for new services.

**Live since 2026-09-07.** Project `mcu-app`, environment `production`, service `api`,
region `ams`, deploying `main` from `CraigR973/mcu-app` via the root `Dockerfile`.
Public URL: `https://api-production-a8fe.up.railway.app`.

## Two things that will bite

1. **Run the Railway CLI on Node 22+.** Its IaC engine invokes Node's type-stripping
   flag, which Node 20 does not support, and `railway config plan` fails before touching
   any infrastructure. The app's own build stays on Node 20:
   `PATH="$HOME/.nvm/versions/node/v22.23.2/bin:$PATH" railway config plan`

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

`plan` is read-only. Do not run `apply` outside the explicit phase-closeout workflow.
`DATABASE_URL` and `FRONTEND_ORIGIN` are preserved from Railway and must be supplied as
service variables; they are never stored in this repository. The two JWT secrets are
generated independently and sealed by Railway — Batch 3 consumes them.
