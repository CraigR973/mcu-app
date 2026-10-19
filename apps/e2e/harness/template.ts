import path from 'node:path'
import { Api } from '../support/api.ts'
import { API_DIR, E2E_DIR, RUN_DIR } from './env.ts'
import { ApiProcess, dbtool, resetWorld, runPython } from './stack.ts'

const FILLER_FIRST = 900001
const FILLER_COUNT = 62

function must(label: string, result: { status: number; output: string }): void {
  if (result.status !== 0) throw new Error(`${label} failed (${result.status}):\n${result.output.slice(-3000)}`)
}

/**
 * The seeded database every run starts from: migrated, both people given a PIN, a small
 * sheet imported by the real import CLI, and enough more films added through the app's own
 * endpoint to make the Archive longer than its first screen. Built once and cloned, so a run
 * does not pay for it again.
 */
export async function buildTemplate(name: string): Promise<void> {
  dbtool('fresh', name)
  resetWorld()

  must(
    'alembic upgrade head',
    runPython(['-m', 'alembic', '--config', path.join(API_DIR, 'alembic.ini'), 'upgrade', 'head'], name),
  )
  must('people', runPython([path.join(E2E_DIR, 'seed', 'seed_people.py')], name))

  const sheet = path.join(RUN_DIR, 'collection.xlsx')
  must('sheet', runPython([path.join(E2E_DIR, 'seed', 'make_sheet.py'), sheet], name))
  must(
    'import',
    runPython(
      ['-m', 'src.scripts.import_collection', '--xlsx', sheet, '--review-out', path.join(RUN_DIR, 'review.csv')],
      name,
      {},
      'import_collection',
    ),
  )

  const api = new ApiProcess(name)
  await api.start()
  try {
    const craig = await Api.as('Craig')
    for (let n = 0; n < FILLER_COUNT; n += 1) {
      await craig.post('/collection', {
        tmdbId: FILLER_FIRST + n,
        formats: ['blu_ray'],
        section: 'Back',
        shelf: `${(n % 4) + 1}${['st', 'nd', 'rd', 'th'][n % 4]} shelf`,
        hasPlaybackIssues: false,
      })
    }
    await craig.post('/retailers/seed')
    await craig.post('/scrapers/apply-built-ins')
  } finally {
    await api.stop()
  }
  // Logging in to seed counted against the five-per-fifteen-minutes limit.
  dbtool('sql', name, 'TRUNCATE rate_limit_counters')
  resetWorld()
}
