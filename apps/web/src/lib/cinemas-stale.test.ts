import { describe, expect, it } from 'vitest'

import { coverageAged, coverageStale, staleCinemasLine, staleVenues, timeStale, type ProgrammeVenue } from './cinemas'

// AG3 (CT52-01, UX54-01): one stale test for every cinema reader, and a guard that keeps it one.
const sources = import.meta.glob('../**/*.{ts,tsx}', { query: '?raw', import: 'default', eager: true }) as Record<string, string>

describe('the one stale test', () => {
  const files = Object.entries(sources).filter(([path]) => !/\.test\.tsx?$/.test(path) && path !== './cinemas.ts')

  it('keeps the 30 and 36 hour limits in lib/cinemas.ts alone', () => {
    const limit = /\b(?:30|36)\s*\*\s*(?:3600000|60\s*\*\s*60\s*\*\s*1000)/
    const copies = files.filter(([, source]) => limit.test(source)).map(([path]) => path)
    expect(copies).toEqual([])
  })

  it('has every cinema card reader ask it', () => {
    const readers = ['components/cinemas/AtTheCinema.tsx', 'components/cinemas/StaleCinemasLine.tsx', 'components/dashboard/CinemaStrip.tsx', 'components/cinemas/ProgrammeCoverage.tsx', 'pages/CinemaFilmPage.tsx']
    for (const reader of readers) {
      const source = files.find(([path]) => path.endsWith(reader))?.[1]
      expect(source, reader).toBeDefined()
      expect(source, reader).toMatch(/coverageAged|staleCoverage|staleCinemasLine|timeStale|coverageStale/)
    }
  })
})

const NOW = Date.parse('2026-11-17T09:00:00Z')
const hours = (count: number) => new Date(NOW - count * 3600000).toISOString()

function venue(name: string, status: 'healthy' | 'failed', lastSuccessUtc: string | null, localDate = '2026-11-17'): ProgrammeVenue {
  return {
    id: name, name, slug: name.toLowerCase(), collectionEnabled: true,
    coverage: [{ localDate, status, observed: status === 'healthy', lastSuccessUtc, lastAttemptUtc: lastSuccessUtc, upstreamUtc: null, upstreamAge: 'unknown', sourceUpdateLabel: null, error: null }],
  } as unknown as ProgrammeVenue
}

describe('"N cinemas not read since <date>"', () => {
  const fresh = venue('Fresh', 'healthy', hours(2))
  const failed = venue('Braehead', 'failed', hours(24 * 6))
  const aged = venue('Quay', 'healthy', hours(31))

  it('says nothing while every cinema is current', () => {
    expect(staleCinemasLine([fresh], NOW)).toBeNull()
  })
  it('counts the stale cinemas and dates the oldest last good read', () => {
    expect(staleVenues([fresh, failed, aged], NOW).map((item) => item.name)).toEqual(['Braehead', 'Quay'])
    expect(staleCinemasLine([fresh, failed, aged], NOW)).toBe('2 cinemas not read since Wed 11 Nov')
  })
  it('says one cinema in the singular and "yet" when it was never read', () => {
    expect(staleCinemasLine([fresh, aged], NOW)).toBe('1 cinema not read since Mon 16 Nov')
    expect(staleCinemasLine([venue('New', 'failed', null)], NOW)).toBe('1 cinema not read yet')
  })
  it('judges a coverage day by status or age, and a time chip by its own day', () => {
    expect(coverageAged({ lastSuccessUtc: hours(29), upstreamUtc: null }, NOW)).toBe(false)
    expect(coverageAged({ lastSuccessUtc: hours(30), upstreamUtc: null }, NOW)).toBe(true)
    expect(coverageAged({ lastSuccessUtc: hours(1), upstreamUtc: hours(36) }, NOW)).toBe(true)
    expect(coverageStale(failed.coverage[0], NOW)).toBe(true)
    expect(timeStale({ at: '2026-11-17T19:30:00Z' }, failed, NOW)).toBe(true)
    expect(timeStale({ at: '2026-11-17T19:30:00Z' }, fresh, NOW)).toBe(false)
  })
})
