import { randomUUID } from 'node:crypto'
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
    // AB6: the installed child phase stays idle until the separate owner enable.
    expect(run.output).toMatch(/cinema programme:\s+disabled/)
    expect(db.scalar('SELECT count(*) FROM cinema_venues')).toBe('9')
    expect(db.scalar('SELECT count(*) FROM cinema_venues WHERE collection_enabled')).toBe('0')
    expect(db.scalar('SELECT count(*) FROM cinema_refresh_runs')).toBe('0')
    for (const host of ['cinematimes.com', 'www.myvue.com', 'www.everymancinema.com',
      'www.cineworld.co.uk', 'www.glasgowfilm.org', 'www.glasgowsciencecentre.org',
      'www.tickettailor.com', 'cms-assets.webediamovies.pro']) {
      expect(world.calls(host)).toHaveLength(0)
    }
  })

  test('the reminders pass reminds a cinema trip on its morning, once however often it runs', async ({ api, db }) => {
    // AC5 (#345, decision 2): the proposer and everyone going are reminded on the showing's own
    // day, in the cinema's zone, which the trip keeps as a snapshot. A fixed-offset zone whose day
    // still has hours left keeps this case independent of the hour it runs.
    const people = { Craig: await api('Craig'), Mark: await api('Mark') }
    const quote = (value: string) => `'${value.replaceAll("'", "''")}'`
    const snapshot = (name: string) => db.scalar(`SELECT json_build_object(
      'movie_night_enabled',n.movie_night_enabled,'digest_mode',n.digest_mode,
      'quiet_hours_start',n.quiet_hours_start,'quiet_hours_end',n.quiet_hours_end)::text
      FROM notification_preferences n JOIN profiles p ON p.id=n.user_id WHERE p.display_name=${quote(name)}`)
    const kept: Record<string, string> = {}
    for (const [name, who] of Object.entries(people)) {
      await who.get('/notifications/preferences')
      kept[name] = snapshot(name)
      await who.put('/notifications/preferences', { movieNightEnabled: true, digestMode: false, clearQuietHours: true })
    }
    await registerDevice(people.Craig, 'craig-trip-reminder')
    const markPhone = await registerDevice(people.Mark, 'mark-trip-reminder')
    const now = Date.now()
    const offsets = [0, ...Array.from({ length: 14 }, (_, i) => [i + 1, -(i + 1)]).flat()].filter((h) => h >= -12 && h <= 14)
    const offset = offsets.find((h) => new Date(now + h * 3600000).getUTCHours() <= 21) ?? 0
    const zone = offset === 0 ? 'Etc/UTC' : `Etc/GMT${offset > 0 ? '-' : '+'}${Math.abs(offset)}`
    const starts = new Date(Math.ceil((now + 3600000) / 60000) * 60000)
    const startsUtc = starts.toISOString().slice(0, 19)
    const clock = new Date(starts.getTime() + offset * 3600000).toISOString().slice(11, 16)
    const [film, showing, trip] = [randomUUID(), randomUUID(), randomUUID()]
    const venue = db.scalar("SELECT id FROM cinema_venues WHERE slug='odeon-glasgow-quay'")
    db.sql(`INSERT INTO cinema_films (id,source,source_key,title,identity_status,evidence)
        VALUES ('${film}','cinematimes','ac5-reminder:${film}','AC5 Reminder Film','verified','{"tmdbId":9300009}'::jsonb);
      INSERT INTO cinema_screenings (id,venue_id,film_id,source_key,identity_strength,local_date,source_local_start,starts_utc,formats,release_category,category_evidence,confirmation)
        VALUES ('${showing}','${venue}','${film}','ac5-reminder:${showing}','opaque','${startsUtc.slice(0, 10)}','${startsUtc}','${startsUtc}','[]'::jsonb,'newRelease','{}'::jsonb,'confirmed');
      INSERT INTO cinema_trips (id,client_request_id,proposer_id,film_key,film_title,showing_id,venue_id,venue_name,venue_timezone,starts_utc)
        VALUES ('${trip}',gen_random_uuid(),(SELECT id FROM profiles WHERE display_name='Craig'),'tmdb-9300009','AC5 Reminder Film','${showing}','${venue}','ODEON Glasgow Quay','${zone}','${startsUtc}');
      INSERT INTO cinema_trip_invitees (id,trip_id,profile_id,reply,reply_revision,replied_at_utc)
        VALUES (gen_random_uuid(),'${trip}',(SELECT id FROM profiles WHERE display_name='Mark'),'going',1,now() AT TIME ZONE 'utc')`)
    try {
      const first = runJob('src.scripts.run_reminders')
      expect(first.status, first.output).toBe(0)
      expect(first.output).toMatch(/cinema trips:\s+1/)
      const second = runJob('src.scripts.run_reminders')
      expect(second.status, second.output).toBe(0)
      // One reminder each, sent; the second pass wrote nothing (the dedupe key carries the trip's
      // revision and the person).
      expect(db.scalar(`SELECT string_agg(p.display_name || '|' || n.status || '|' || n.body, ';' ORDER BY p.display_name)
        FROM notifications n JOIN profiles p ON p.id = n.user_id WHERE n.dedupe_key LIKE 'cinema-trip-reminder:${trip}:%'`))
        .toBe(`Craig|sent|${clock} at ODEON Glasgow Quay, with Mark.;Mark|sent|${clock} at ODEON Glasgow Quay, with Craig.`)
      const reminders = pushesTo(markPhone).filter((p) => p.title === 'Cinema today: AC5 Reminder Film')
      expect(reminders.map((p) => [p.body, p.url])).toEqual([[`${clock} at ODEON Glasgow Quay, with Craig.`, `/movie-night/trips/${trip}`]])
    } finally {
      db.sql(`DELETE FROM cinema_trips WHERE id='${trip}'; DELETE FROM cinema_films WHERE id='${film}'`)
      // runJob blocks Node while the real command runs. Its previously idle HTTP socket
      // may have closed meanwhile; fixture cleanup must not depend on reusing that socket.
      // Restore only the fields this test changed, in the harness's disposable database.
      for (const [name, saved] of Object.entries(kept)) {
        db.sql(`UPDATE notification_preferences n SET
          movie_night_enabled=old.movie_night_enabled,digest_mode=old.digest_mode,
          quiet_hours_start=old.quiet_hours_start,quiet_hours_end=old.quiet_hours_end
          FROM json_populate_record(NULL::notification_preferences,${quote(saved)}::json) old,
            profiles p WHERE p.id=n.user_id AND p.display_name=${quote(name)}`)
      }
    }
    for (const [name, saved] of Object.entries(kept)) expect(snapshot(name)).toBe(saved)
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

// AC6 exercises the same scheduled entry point without a browser as well.
test('the cinema digest names a verified film once across two scheduled runs', async ({ api, db }) => {
  const { exerciseCinemaDigest } = await import('../support/cinema-digest.ts')
  const fixture = await exerciseCinemaDigest(await api('Craig'), await api('Mark'), db)
  await fixture.cleanup()
})

// AE4 (#355): the step owed the morning after AE4 deploys, rehearsed in the fake world. A morning
// run reads the Omniplex's page beside an ODEON on CinemaTimes and shows it to nobody; with the
// other nine then on, as production is, the existing command switches on exactly one cinema,
// audited, and only then is it seen. (Only Braehead is on for the read: the other sources'
// hosts are not faked here.)
test('the Omniplex is read on a morning run while off, then the existing command enables it alone', async ({ api, db }) => {
  const omniplex = db.scalar("SELECT id FROM cinema_venues WHERE slug='omniplex-glasgow-renfrew-street'")
  const craigId = db.scalar("SELECT id FROM profiles WHERE display_name='Craig'")
  const runsBefore = new Set((db.scalar("SELECT coalesce(string_agg(id::text,','),'') FROM cinema_refresh_runs") || '').split(','))
  const day = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(Date.now() + 86400000))
  const slugs = async () => (await (await api('Craig')).get<{ venues: { slug: string }[]; films: { title: string }[] }>('/cinemas/films'))
  try {
    db.sql("UPDATE cinema_venues SET collection_enabled = (slug = 'odeon-braehead')")
    world.setScenario({ cinemas: { slug: 'omniplex-glasgow-renfrew-street', title: 'Renfrew Morning', day } })
    const morning = runJob('src.scripts.run_reminders')
    expect(morning.status, morning.output).toBe(0)
    expect(Number(db.scalar(`SELECT count(*) FROM cinema_coverage WHERE venue_id='${omniplex}' AND observed`))).toBeGreaterThan(0)
    // Read, but shown to nobody, and not in any digest.
    const before = await slugs()
    expect(before.venues.map((venue) => venue.slug)).not.toContain('omniplex-glasgow-renfrew-street')
    expect(before.films.map((film) => film.title)).not.toContain('Renfrew Morning')
    expect(db.scalar("SELECT count(*) FROM cinema_digest_appearances")).toBe('0')

    // Production's state for the enable step: the nine on, the Omniplex off.
    db.sql(`UPDATE cinema_venues SET collection_enabled = (id <> '${omniplex}')`)
    // The existing command, guarded by its count: any other number writes nothing.
    const wrong = runJob('src.scripts.refresh_cinemas', ['--enable', '--confirm-count', '2', '--actor-profile-id', craigId])
    expect(wrong.status).not.toBe(0)
    expect(db.scalar(`SELECT collection_enabled::text FROM cinema_venues WHERE id='${omniplex}'`)).toBe('false')
    const enable = runJob('src.scripts.refresh_cinemas', ['--enable', '--confirm-count', '1', '--actor-profile-id', craigId])
    expect(enable.status, enable.output).toBe(0)
    expect(db.scalar(`SELECT collection_enabled::text FROM cinema_venues WHERE id='${omniplex}'`)).toBe('true')
    expect(db.scalar(`SELECT count(*) FROM admin_actions WHERE target_table='cinema_venues' AND target_id='${omniplex}'`)).toBe('1')
    const after = await slugs()
    expect(after.venues.map((venue) => venue.slug)).toContain('omniplex-glasgow-renfrew-street')
    expect(after.films.map((film) => film.title)).toContain('Renfrew Morning')
  } finally {
    db.sql(`UPDATE cinema_venues SET collection_enabled=false;
      DELETE FROM admin_actions WHERE target_table='cinema_venues' AND target_id='${omniplex}';
      DELETE FROM cinema_films WHERE source='cinematimes' AND source_key='/uk/glasgow/movies/ac6-e2e/'`)
    const runs = (db.scalar("SELECT coalesce(string_agg(id::text,','),'') FROM cinema_refresh_runs") || '').split(',')
    for (const id of runs.filter((id) => id && !runsBefore.has(id))) db.sql(`DELETE FROM cinema_refresh_runs WHERE id='${id}'`)
  }
})

