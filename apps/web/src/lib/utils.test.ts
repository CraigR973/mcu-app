import { describe, it, expect } from 'vitest'
import { cn, formatShortDate } from './utils'

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

describe('formatShortDate', () => {
  it('writes a watch date the way it is said in the UK', () => {
    expect(formatShortDate('2025-03-12')).toBe('12 Mar 2025')
  })

  it('keeps the calendar day, whatever the time zone', () => {
    // A UTC-midnight parse would show 31 Dec 2024 anywhere west of Greenwich.
    expect(formatShortDate('2025-01-01')).toBe('1 Jan 2025')
  })

  it('gives back anything that is not a date unchanged', () => {
    expect(formatShortDate('someday')).toBe('someday')
  })
})
