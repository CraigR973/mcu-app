import { describe, it, expect } from 'vitest'
import { cn, formatDate, formatDateTime, formatDayMonth, formatMonth, formatShortDate } from './utils'

describe('cn', () => {
  it('joins class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar')
  })

  it('resolves conflicting tailwind classes (last wins)', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4')
  })

  it('filters falsy values', () => {
    expect(cn('foo', false, null, undefined, 'bar')).toBe('foo bar')
  })

  it('handles conditional classes', () => {
    const active = true
    expect(cn('base', active && 'active')).toBe('base active')
  })
})

describe('formatDayMonth', () => {
  it('writes a recent date as day and month, read off the string', () => {
    expect(formatDayMonth('2026-09-30T19:14:57Z')).toBe('30 Sep')
    expect(formatDayMonth('not a date')).toBe('not a date')
  })
})

describe('formatShortDate', () => {
  it('writes a watch date the way it is said in the UK', () => {
    expect(formatShortDate('2025-03-12')).toBe('12 Mar 2025')
  })

  it('keeps the calendar day, whatever the time zone', () => {
    // A UTC-midnight parse would show 31 Dec 2024 anywhere west of Greenwich.
    expect(formatShortDate('2025-01-01')).toBe('1 Jan 2025')
  })

  it('writes September as "Sep", whatever the browser prefers', () => {
    expect(formatShortDate('2026-09-23')).toBe('23 Sep 2026')
    expect(formatShortDate('2026-09-23T18:00:00Z')).toBe('23 Sep 2026')
  })

  it('gives back anything that is not a date unchanged', () => {
    expect(formatShortDate('someday')).toBe('someday')
  })
})

describe('formatDate — Batch X12a (UX48-05)', () => {
  const now = new Date(2026, 9, 18)

  it('drops the year in the current year and keeps it in any other', () => {
    expect(formatDate('2026-10-11', now)).toBe('11 Oct')
    expect(formatDate('2025-10-11', now)).toBe('11 Oct 2025')
  })

  it('writes September as Sep, never "Sept"', () => {
    expect(formatDate('2026-09-22', now)).toBe('22 Sep')
  })

  it('reads a bare date off the string, whatever the time zone', () => {
    expect(formatDate('2026-03-01', now)).toBe('1 Mar')
  })

  it('reads a timestamp in the viewer\'s own day, and a moment with its time', () => {
    const moment = new Date(2026, 9, 11, 14, 5)
    expect(formatDate(moment, now)).toBe('11 Oct')
    expect(formatDateTime(moment, now)).toBe('11 Oct, 14:05')
  })

  it('passes an unreadable value through rather than printing "Invalid Date"', () => {
    expect(formatDate('soon', now)).toBe('soon')
  })
})

describe('formatMonth', () => {
  it('reads the spend chart month as words', () => {
    expect(formatMonth('2026-09')).toBe('Sep 2026')
    expect(formatMonth('nonsense')).toBe('nonsense')
  })
})
