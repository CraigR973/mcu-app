import { runJob } from '../support/cli.ts'
import { pushesTo, registerDevice } from '../support/push.ts'
import { expect, test } from '../support/test.ts'
import { world } from '../support/world.ts'

/**
 * CR43-07: the five jobs Railway runs on a schedule, run the way Railway runs them
 * (`python -m src.scripts.<job>`), on the throwaway Postgres, with every outside service
 * faked. Until now the eBay, spec-and-review and valuation jobs' `main()` had never run in a
 * test, and the other two ran with their working part swapped out. Each case checks the exit
 * code (the only thing a scheduler reads), the job's heartbeat, and something the job did.
 */
test.describe('the cron jobs, run as Railway runs them', () => {
  test('the shop check reads the shops, saves a price and sends the alert', async ({ api, db }) => {
    const craig = await api('Craig')
    await craig.post('/wanted', { tmdbId: 1401, preferredFormat: 'blu_ray', maxPrice: '10.00' })
    world.setScenario({
      shops: { 'www.zavvi.com': [{ match: 'ember coast', title: 'Ember Coast Blu-ray', price: '8.99' }] },
    })
    const phone = await registerDevice(craig, 'craig-phone')

    const run = runJob('src.scripts.daily_scrape')
    expect(run.status, run.output).toBe(0)
    expect(run.output).toContain('daily scrape complete')
    expect(Number(db.scalar('SELECT count(*) FROM price_checks'))).toBeGreaterThan(0)
    expect(pushesTo(phone).map((p) => p.title)).toContain('Ember Coast is £8.99')
    expect(db.scalar("SELECT outcome FROM job_heartbeats WHERE job = 'cron-scrape'")).not.toBe('')
  })

  test('the reminders pass runs the daily check and records that it ran', async ({ db }) => {
    const run = runJob('src.scripts.run_reminders')
    expect(run.status, run.output).toBe(0)
    expect(run.output).toContain('reminder pass complete')
    expect(run.output).toMatch(/daily check:\s+\d+ checks/)
    expect(Number(db.scalar('SELECT count(*) FROM health_checks'))).toBeGreaterThan(0)
    expect(db.scalar("SELECT count(*) FROM job_heartbeats WHERE job = 'cron-reminders'")).toBe('1')
  })

  test('the disc spec and review job searches for pages with Brave and finishes its batch', async ({ db }) => {
    const run = runJob('src.scripts.spec_backfill')
    expect(run.status, run.output).toBe(0)
    expect(run.output).toContain('spec batch finished')
    expect(run.output).toContain('review batch finished')
    expect(run.output).toContain('IMDb ratings:')
    expect(world.calls('datasets.imdbws.com').length).toBe(1)
    expect(db.scalar('SELECT imdb_rating::text FROM movies WHERE tmdb_id = 1001')).toBe('8.2')
    expect(world.calls('api.search.brave.com').length).toBeGreaterThan(0)
    expect(db.scalar("SELECT count(*) FROM job_heartbeats WHERE job = 'cron-specs'")).toBe('1')
  })

  test('the eBay pass checks a person\'s alert against new listings and tells them', async ({ api, db }) => {
    const mark = await api('Mark')
    const phone = await registerDevice(mark, 'mark-phone')
    const films = await mark.get<{ items: { id: string; title: string }[] }>('/movies?perPage=2000')
    const film = films.items.find((f) => f.title === 'Harbour Lights')
    if (!film) throw new Error('the seed has no Harbour Lights')
    await mark.post('/ebay/targets/search', { movieId: film.id, formatCode: 'blu_ray', targetPrice: '9.00' })
    world.setScenario({
      ebay: { searches: [{ contains: 'harbour lights', listings: [{ title: 'Harbour Lights Blu-ray (1958)', price: '6.00', legacyItemId: '830001' }] }] },
    })

    const run = runJob('src.scripts.ebay_watch')
    expect(run.status, run.output).toBe(0)
    expect(run.output).toMatch(/targets checked: [1-9]\d*, met [1-9]/)
    expect(pushesTo(phone).map((p) => p.title).join('|')).toContain('Harbour Lights')
    expect(db.scalar("SELECT count(*) FROM job_heartbeats WHERE job = 'cron-ebay'")).toBe('1')
  })

  test('the valuation job prices discs from eBay listings and stores the values', async ({ db }) => {
    const run = runJob('src.scripts.value_collection')
    expect(run.status, run.output).toBe(0)
    expect(run.output).toContain('valuation run finished')
    expect(Number(db.scalar("SELECT count(*) FROM disc_valuations WHERE status = 'priced'"))).toBeGreaterThan(0)
    expect(db.scalar("SELECT count(*) FROM job_heartbeats WHERE job = 'cron-values'")).toBe('1')
  })
})


test('a refused IMDb file fails the nightly command without wiping its stored scores', async ({ db }) => {
  db.sql("UPDATE movies SET imdb_ratings_id = imdb_id, imdb_rating = 6.2, imdb_vote_count = 99, imdb_ratings_checked_utc = '2026-10-24 02:00:00' WHERE tmdb_id = 1001")
  world.setScenario({ imdb: { status: 503 } })
  const run = runJob('src.scripts.spec_backfill')
  expect(run.status, run.output).toBe(1)
  expect(run.output).toContain('IMDb ratings failed:')
  expect(db.scalar('SELECT imdb_rating::text FROM movies WHERE tmdb_id = 1001')).toBe('6.2')
  expect(db.scalar("SELECT detail->>'imdbError' FROM job_heartbeats WHERE job = 'cron-specs'")).toContain('503')
})
