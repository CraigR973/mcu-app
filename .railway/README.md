# Railway infrastructure

Batch 2 defines the production API service in `.railway/railway.ts` using Railway's
project-level Infrastructure as Code format. The legacy `railway.toml` format cannot be
enabled for new services.

For the first production close-out, create the project and an empty service, then add the
two owner-supplied variables without triggering a deploy. This lets the IaC apply attach
the Git source only after the service can boot successfully:

```bash
railway init --name mcu-app
railway add --service api
railway variable set DATABASE_URL --stdin --service api --skip-deploys
railway variable set FRONTEND_ORIGIN=https://YOUR-VERCEL-DOMAIN --service api --skip-deploys
railway config plan
railway config apply
railway domain --service api
```

On later machines, use `railway link` instead of `railway init`.

`plan` is read-only. Do not run `apply` outside the explicit phase-closeout workflow.
`DATABASE_URL` and `FRONTEND_ORIGIN` are preserved from Railway and must be supplied as
service variables; they are never stored in this repository. The two JWT secrets are
generated independently and sealed by Railway.
