import { describe, expect, it } from 'vitest'
import type { ScrapeRunRecord } from '@mcu/shared'

import { scrapeRunVerdict } from './api'

/**
 * §5.5's acceptance criterion, as the page renders it.
 *
 * `DECISIONS.md` #112 corrected the criterion after a live run disproved it: as written it
 * wanted rows ≈ (wants × retailers), which assumes every shop stocks every film. On
 * 2026-09-09 that predicted 35 rows from 7 wants × 5 shops and the correct answer was 6,
 * with all 29 gaps right. The corrected form compares against the pairs that were
 * genuinely answerable, and the intent worth keeping is catching a **silent mass failure**.
 */
function run(overrides: Partial<ScrapeRunRecord> = {}): ScrapeRunRecord {
  return {
    id: '00000000-0000-4000-8000-000000000000',
    startedAt: '2026-09-10T03:00:00Z',
    finishedAt: '2026-09-10T03:04:00Z',
    trigger: 'cron',
    dryRun: false,
    attempted: 10,
    notStocked: 0,
    noResults: 0,
    skipped: 0,
    succeeded: 10,
    failed: 0,
    written: 10,
    alertsQueued: 0,
    failures: [],
    disabledRetailers: [],
    error: null,
    ...overrides,
  }
}

describe('scrapeRunVerdict', () => {
  it('passes when every answerable pair was priced', () => {
    expect(scrapeRunVerdict(run())).toMatchObject({ answerable: 10, ok: true })
  })

  it('does not count a shop that has not got the film against the run', () => {
    // #107: three correct refusals once read as three failures and took three working
    // scrapers offline. They are neither a gap nor a failure — and the API already leaves
    // them out of `attempted`, which is why this asserts 4 attempted rather than 10.
    const verdict = scrapeRunVerdict(run({ attempted: 4, notStocked: 6, written: 4 }))

    expect(verdict.answerable).toBe(4)
    expect(verdict.ok).toBe(true)
  })

  it('does not subtract notStocked a second time', () => {
    // The bug this file encoded. `attempted` already excludes `notStocked` (#107), so
    // subtracting it here counted it twice, and any run where the shops honestly had more
    // films than they carried collapsed to "Nothing to price". #125.
    const verdict = scrapeRunVerdict(run({ attempted: 17, notStocked: 23, written: 6 }))

    expect(verdict.answerable).toBe(17)
    expect(verdict.label).not.toContain('Nothing to price')
  })

  it('tolerates the criterion\'s 10% failure margin', () => {
    expect(scrapeRunVerdict(run({ attempted: 10, written: 9 })).ok).toBe(true)
  })

  it('fails when writes collapse while the shops were still answering', () => {
    // The silent mass failure the criterion exists to catch: the scrapers broke, so
    // attempted-minus-not-stocked stays high while written drops.
    const verdict = scrapeRunVerdict(run({ attempted: 10, written: 2, failed: 8 }))

    expect(verdict.ok).toBe(false)
    expect(verdict.label).toContain('check the failures')
  })

  it('calls a run with nothing to do exactly that', () => {
    // Every want was one no shop carries. Zero of zero is not a failure, and reporting it
    // as one would train the reader to ignore the line.
    const verdict = scrapeRunVerdict(run({ attempted: 0, notStocked: 5, written: 0 }))

    expect(verdict.ok).toBe(true)
    expect(verdict.label).toContain('Nothing to price')
  })

  it('reports a run that blew up as failed regardless of its counts', () => {
    expect(scrapeRunVerdict(run({ error: 'connection reset' })).ok).toBe(false)
  })

  it('does not count a shop that answered with nothing against the run', () => {
    // #125: an empty results page is neither a failure nor a claim, and it is certainly
    // not a pair anybody could have priced. Counting it in the denominator would make a
    // healthy night read as a collapse.
    const verdict = scrapeRunVerdict(run({ attempted: 10, noResults: 6, written: 4 }))

    expect(verdict.answerable).toBe(4)
    expect(verdict.ok).toBe(true)
  })

  it('reads the real run of 2026-09-10 correctly', () => {
    // 40 pairs: 23 shops answered "not that one", 8 answered with nothing at all, 3 broke
    // and 6 priced. Nine were genuinely answerable, and six of them were priced.
    const verdict = scrapeRunVerdict(
      run({ attempted: 17, notStocked: 23, noResults: 8, failed: 3, written: 6 }),
    )

    expect(verdict.answerable).toBe(9)
    expect(verdict.ok).toBe(false)
    expect(verdict.label).toContain('6 of 9')
  })
})
