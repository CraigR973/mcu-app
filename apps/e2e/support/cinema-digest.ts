import { expect } from '@playwright/test'
import type { Api } from './api.ts'
import { runJob } from './cli.ts'
import { pushesTo, registerDevice } from './push.ts'
import { world } from './world.ts'

type DB = { sql(statement: string): void; scalar(statement: string): string }

/** The actual morning command, against real disposable tables and fake source/TMDB/push. */
export async function exerciseCinemaDigest(craig: Api, mark: Api, db: DB) {
  const venue = db.scalar("SELECT id FROM cinema_venues WHERE slug='odeon-braehead'")
  const oldRuns = new Set((db.scalar("SELECT coalesce(string_agg(id::text,','),'') FROM cinema_refresh_runs") || '').split(','))
  const prefs = [await craig.get<Record<string, unknown>>('/notifications/preferences'), await mark.get<Record<string, unknown>>('/notifications/preferences')]
  const phones = [await registerDevice(craig, 'ac6-craig'), await registerDevice(mark, 'ac6-mark')]
  const later = new Date(Date.now() + 86400000)
  const day = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' }).format(later)
  const cleanup = async () => {
    db.sql(`DELETE FROM cinema_digest_deliveries;
      DELETE FROM notifications WHERE category='cinemas';
      DELETE FROM cinema_digest_days;
      DELETE FROM cinema_digest_appearances;
      DELETE FROM cinema_digest_listings;
      DELETE FROM cinema_digest_films;
      DELETE FROM cinema_films WHERE source='cinematimes' AND source_key='/uk/glasgow/movies/ac6-e2e/';
      UPDATE cinema_venues SET collection_enabled=false WHERE id='${venue}'`)
    const current = (db.scalar("SELECT coalesce(string_agg(id::text,','),'') FROM cinema_refresh_runs") || '').split(',')
    for (const id of current.filter(id => id && !oldRuns.has(id))) db.sql(`DELETE FROM cinema_refresh_runs WHERE id='${id}'`)
    // Reset the fixture through SQL: the synchronous jobs can outlive the HTTP client's
    // idle connection. No API assertion depends on this post-test cleanup transport.
    for (const [i, name] of ['Craig', 'Mark'].entries()) {
      const saved = "'" + JSON.stringify(prefs[i]).replaceAll("'", "''") + "'::jsonb"
      db.sql(`UPDATE notification_preferences n SET
        cinemas_enabled=(${saved}->>'cinemasEnabled')::boolean,
        cinemas_older_only=(${saved}->>'cinemasOlderOnly')::boolean,
        digest_mode=(${saved}->>'digestMode')::boolean,
        quiet_hours_start=(${saved}->>'quietHoursStart')::time,
        quiet_hours_end=(${saved}->>'quietHoursEnd')::time
        FROM profiles p WHERE n.user_id=p.id AND p.display_name='${name}'`)
    }
  }
  try {
    await craig.put('/notifications/preferences', { cinemasEnabled: true, cinemasOlderOnly: false, digestMode: false, clearQuietHours: true })
    await mark.put('/notifications/preferences', { cinemasEnabled: true, cinemasOlderOnly: true, digestMode: false, clearQuietHours: true })
    world.setScenario({ cinemas: { slug: 'odeon-braehead', title: 'Ember Coast', day } })
    db.sql(`UPDATE cinema_venues SET collection_enabled=true WHERE id='${venue}'`)
    const first = runJob('src.scripts.run_reminders')
    expect(first.status, first.output).toBe(0)
    expect(first.output).toMatch(/cinema programme:\s+partial/)
    const second = runJob('src.scripts.run_reminders')
    expect(second.status, second.output).toBe(0)
    for (const phone of phones) {
      const messages = pushesTo(phone).filter(message => message.category === 'cinemas')
      expect(messages).toHaveLength(1)
      expect(messages[0].body).toContain('Ember Coast — Rerun')
      expect(messages[0].url).toContain('/movie-night/cinema?view=new-this-week')
    }
    expect(pushesTo(phones[1]).find(message => message.category === 'cinemas')?.url).toContain('&run=olderFilm')
    expect(db.scalar('SELECT count(*) FROM cinema_digest_appearances')).toBe('1')
    expect(db.scalar('SELECT count(*) FROM cinema_digest_deliveries')).toBe('2')
    return { cleanup, url: String(pushesTo(phones[0]).find(message => message.category === 'cinemas')?.url) }
  } catch (error) {
    await cleanup()
    throw error
  }
}
