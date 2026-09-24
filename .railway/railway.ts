import { defineRailway, github, preserve, project, service } from 'railway/iac'

export default defineRailway(() => {
  const api = service('api', {
    source: github('CraigR973/mcu-app', { branch: 'main' }),
    build: {
      builder: 'DOCKERFILE',
      dockerfilePath: 'Dockerfile',
    },
    deploy: {
      healthcheckPath: '/api/v1/health/ready',
      healthcheckTimeout: 300,
      restartPolicyType: 'ON_FAILURE',
      restartPolicyMaxRetries: 3,
    },
    env: {
      DATABASE_URL: preserve(),
      ENVIRONMENT: 'production',
      FRONTEND_ORIGIN: preserve(),
      // **`preserve()`, not `randomString()`.** These are sealed, so Railway cannot read
      // them back to compare — `config plan` therefore reported them as changing on every
      // run, and applying that would have minted new secrets and signed both people out,
      // invalidating every refresh token with them. They were generated once when the
      // service was created (Batch 2) and there is no reason to generate them again.
      JWT_ACCESS_SECRET: preserve(),
      JWT_REFRESH_SECRET: preserve(),
      // **Everything below is declared only so that `apply` does not delete it.**
      // `ANTHROPIC_API_KEY` and `TMDB_READ_TOKEN` were set in the console and never added
      // here, so IaC read them as drift and planned to remove them — which would have
      // recreated the TMDB outage of 2026-09-09 exactly. `DECISIONS.md` #124.
      //
      // `preserve()` keeps whatever Railway already holds, so no secret enters this
      // repository (`AGENTS.md`: never put a token in a tracked file).
      ANTHROPIC_API_KEY: preserve(),
      TMDB_READ_TOKEN: preserve(),
      VAPID_PUBLIC_KEY: preserve(),
      VAPID_PRIVATE_KEY: preserve(),
      VAPID_SUBJECT: preserve(),
      EBAY_VERIFICATION_TOKEN: preserve(),
      // Batch 28's Browse keyset, set in the console on 2026-09-12 and never declared, so
      // `apply` would have removed it (`OWNER-ACTIONS.md` 1b). Batch T7 declares it
      // because its own change needs an `apply`.
      EBAY_CLIENT_ID: preserve(),
      EBAY_CLIENT_SECRET: preserve(),
      // Batch T7 (`DECISIONS.md` #202). Brave's web search key, set in the console by
      // Craig; the nightly spec batch takes it from here by reference.
      BRAVE_SEARCH_API_KEY: preserve(),
      // **A literal, not `preserve()` — the one env var here that is not a secret.**
      // eBay hashes the URL *it* has on file into every validation challenge, so ours
      // must match byte for byte or validation fails with no diagnosable error. Pinning
      // it here makes IaC enforce that identity instead of trusting a console field
      // nobody re-reads. It is already public in `.railway/README.md`, and
      // `routers/ebay.py` reads it rather than reconstructing it from the request,
      // because behind this proxy the app sees a different host and scheme.
      EBAY_ACCOUNT_DELETION_ENDPOINT:
        'https://api-production-a8fe.up.railway.app/api/v1/ebay/account-deletion',
    },
  })

  /**
   * The two scheduled jobs — `DECISIONS.md` #60 and #119.
   *
   * **Separate services, not a schedule on `api`.** A Railway cron runs the service's own
   * start command and expects the process to exit; `api` runs uvicorn, which never does.
   * Putting a schedule on it would restart the API on a timer instead of scraping anything.
   *
   * They share the API's image because they *are* the API — same code, same models, same
   * database — invoked at a different entry point. Nothing here runs a migration: `api`
   * does that on deploy, and two containers racing `alembic upgrade head` is a way to lose
   * a database rather than a way to schedule a job.
   *
   * **`restartPolicyType: 'NEVER'`.** A failed scrape must not be retried automatically:
   * these make live requests to real shops, and `ON_FAILURE` would turn one bad night into
   * three. The job exits non-zero, Railway shows it red, and the next run is tomorrow's.
   */
  const cronDefaults = {
    source: github('CraigR973/mcu-app', { branch: 'main' }),
    build: {
      builder: 'DOCKERFILE' as const,
      dockerfilePath: 'Dockerfile',
    },
    env: {
      DATABASE_URL: api.env.DATABASE_URL,
      ENVIRONMENT: 'production',
      // Without these the job scrapes, queues, and silently sends nothing.
      VAPID_PUBLIC_KEY: api.env.VAPID_PUBLIC_KEY,
      VAPID_PRIVATE_KEY: api.env.VAPID_PRIVATE_KEY,
      VAPID_SUBJECT: api.env.VAPID_SUBJECT,
    },
  }

  const scrape = service('cron-scrape', {
    ...cronDefaults,
    deploy: {
      // 03:00 UTC — outside UK shopping hours, and well clear of the reminder pass.
      cronSchedule: '0 3 * * *',
      startCommand: 'python -m src.scripts.daily_scrape',
      restartPolicyType: 'NEVER',
    },
  })

  const reminders = service('cron-reminders', {
    ...cronDefaults,
    deploy: {
      // 08:00 UTC — a reminder about tonight's release is worth having in the morning.
      cronSchedule: '0 8 * * *',
      startCommand: 'python -m src.scripts.run_reminders',
      restartPolicyType: 'NEVER',
    },
  })

  /**
   * Batch T7 — the Blu-ray.com backfill (`DECISIONS.md` #202, within #110).
   *
   * Up to 150 Brave searches, then up to 150 page fetches five seconds apart, and a
   * `403` or `429` from Blu-ray.com halts it for good. `NEVER` restarts, like the others:
   * a batch that failed should not be retried into the site that refused it.
   */
  const specs = service('cron-specs', {
    ...cronDefaults,
    env: {
      ...cronDefaults.env,
      BRAVE_SEARCH_API_KEY: api.env.BRAVE_SEARCH_API_KEY,
    },
    deploy: {
      // 02:00 UTC — overnight, and clear of the shop check at 03:00.
      cronSchedule: '0 2 * * *',
      startCommand: 'python -m src.scripts.spec_backfill',
      restartPolicyType: 'NEVER',
    },
  })

  return project('mcu-app', {
    environments: ['production'],
    resources: [api, scrape, reminders, specs],
  })
})
