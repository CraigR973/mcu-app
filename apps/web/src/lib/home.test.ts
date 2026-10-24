import { describe, expect, it } from 'vitest'
import type { CompletionSet } from '@mcu/shared'

import { closestToComplete, yearsAgo } from './home'

function set(name: string, owned: number, total: number): CompletionSet {
  return {
    id: `id-${name}`,
    setType: 'director',
    setKey: name,
    setName: name,
    ownedCount: owned,
    totalCount: total,
    missingCount: total - owned,
    percentComplete: Math.floor((owned / total) * 100),
    lastRefreshed: null,
    personProfilePath: null,
  }
}

describe('closestToComplete — Batch W2', () => {
  it('leads with the fewest films missing, whatever the share', () => {
    const order = closestToComplete([set('Many', 18, 353), set('Two short', 3, 5), set('One short', 10, 11)])
    expect(order.map((s) => s.setName)).toEqual(['One short', 'Two short', 'Many'])
  })

  it('puts a finished set after the unfinished ones', () => {
    const order = closestToComplete([set('Done', 6, 6), set('Nearly', 5, 6)])
    expect(order.map((s) => s.setName)).toEqual(['Nearly', 'Done'])
  })

  it('breaks a tie on the share, then the name', () => {
    const order = closestToComplete([set('B', 8, 10), set('A', 8, 10), set('Higher', 18, 20)])
    expect(order.map((s) => s.setName)).toEqual(['Higher', 'A', 'B'])
  })

  it('leaves the list it was given alone', () => {
    const given = [set('B', 1, 2), set('A', 1, 3)]
    closestToComplete(given)
    expect(given.map((s) => s.setName)).toEqual(['B', 'A'])
  })
})

describe('yearsAgo', () => {
  it('says "a year" for one, and counts the rest', () => {
    expect(yearsAgo(1)).toBe('A year ago')
    expect(yearsAgo(4)).toBe('4 years ago')
  })
})
