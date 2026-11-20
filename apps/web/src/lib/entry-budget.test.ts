import { describe, expect, it } from 'vitest'
import { ENTRY_BUDGET, entryBudgetBreach } from './entry-budget'

const entry = (raw: number, gzip: number) => ({ fileName: 'assets/index-a.js', isEntry: true, raw, gzip })

describe('the entry chunk budget (AG10)', () => {
  it('is about the size measured on 20 Nov, with little room', () => {
    expect(ENTRY_BUDGET.raw).toBeGreaterThanOrEqual(756_905)
    expect(ENTRY_BUDGET.raw).toBeLessThanOrEqual(800_000)
    expect(ENTRY_BUDGET.gzip).toBeGreaterThanOrEqual(230_768)
    expect(ENTRY_BUDGET.gzip).toBeLessThanOrEqual(245_000)
  })

  it('passes an entry chunk inside it', () => {
    expect(entryBudgetBreach([entry(756_905, 230_768)])).toBeNull()
    expect(entryBudgetBreach([entry(ENTRY_BUDGET.raw, ENTRY_BUDGET.gzip)])).toBeNull()
  })

  it('fails an entry chunk over it, raw or gzipped, and says what to do', () => {
    const raw = entryBudgetBreach([entry(ENTRY_BUDGET.raw + 1, 200_000)])
    expect(raw).toContain('assets/index-a.js')
    expect(raw).toContain('780,001 bytes')
    expect(raw).toContain('raise the budget as a decision')
    expect(entryBudgetBreach([entry(700_000, ENTRY_BUDGET.gzip + 1)])).toContain('240,001 gzipped')
  })

  it('ignores a large chunk loaded later, such as the scanner', () => {
    const scanner = { fileName: 'assets/index-zxing.js', isEntry: false, raw: 2_000_000, gzip: 600_000 }
    expect(entryBudgetBreach([entry(700_000, 200_000), scanner])).toBeNull()
  })

  it('fails a build with no entry chunk rather than passing it', () => {
    expect(entryBudgetBreach([])).toContain('no entry chunk')
  })
})
