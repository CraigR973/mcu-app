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
      // Batch T8b, "Connect eBay" (`DECISIONS.md` #227, #245). Set in the console by Craig
      // on 3 Oct (`OWNER-ACTIONS.md` 18): the RuName eBay generated for the sign-in page,
      // and the 32 bytes the sealing key for each person's eBay token is derived from.
      // Until this declared them, `config plan` read "2 to destroy": these two.
      EBAY_RUNAME: preserve(),
      EBAY_TOKEN_KEY: preserve(),
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
   * The scheduled jobs — `DECISIONS.md` #60 and #119.
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

  /**
   * Batch T8a — eBay price alerts and the deal scan (`DECISIONS.md` #203, #216).
   *
   * Every two hours: the price targets people have set, then the newest UK Blu-ray and 4K
   * listings, within 500 of eBay's 5,000 calls a day (10%, beside the valuation's 750). It
   * takes the eBay keyset from `api` by reference, as `cron-specs` takes the Brave key, and
   * the push keys from `cronDefaults`. It signs nobody in and holds no personal token.
   * `NEVER` restarts, like the others: a pass eBay refused waits for the next one.
   */
  const ebay = service('cron-ebay', {
    ...cronDefaults,
    env: {
      ...cronDefaults.env,
      EBAY_CLIENT_ID: api.env.EBAY_CLIENT_ID,
      EBAY_CLIENT_SECRET: api.env.EBAY_CLIENT_SECRET,
    },
    deploy: {
      // Twenty past every second hour, clear of the other jobs, which start on the hour.
      cronSchedule: '20 */2 * * *',
      startCommand: 'python -m src.scripts.ebay_watch',
      restartPolicyType: 'NEVER',
    },
  })

  /**
   * Batch U4 — the collection re-priced on its own (`DECISIONS.md` #222, #223).
   *
   * A price falls due 30 days after it was taken. This prices whatever is due within the
   * valuation's 750 of eBay's 5,000 calls a day, the Home button's own run, and spends
   * nothing when nothing is due. **Every fortnight, not every night: Craig's choice.** Two
   * mornings each time, because the whole collection was priced within three days, so it
   * falls due together, and a day's share prices about half of it. It takes the eBay keyset
   * from `api` by reference, as `cron-ebay` does. `NEVER` restarts, like the others: a run
   * eBay refused carries on at the next one.
   */
  const values = service('cron-values', {
    ...cronDefaults,
    env: {
      ...cronDefaults.env,
      EBAY_CLIENT_ID: api.env.EBAY_CLIENT_ID,
      EBAY_CLIENT_SECRET: api.env.EBAY_CLIENT_SECRET,
    },
    deploy: {
      // 04:00 UTC on the 1st, 2nd, 15th and 16th: after the specs (02:00) and the shops
      // (03:00), and clear of the eBay pass at twenty past.
      cronSchedule: '0 4 1,2,15,16 * *',
      startCommand: 'python -m src.scripts.value_collection',
      restartPolicyType: 'NEVER',
    },
  })

  return project('mcu-app', {
    environments: ['production'],
    resources: [api, scrape, reminders, specs, ebay, values],
  })
})
