import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

/**
 * Batch X12a (UX48-05): dates read one way. The review found four forms on one phone, two of
 * them from `toLocaleDateString`, which writes "11/10/2026" or "22 Sept" by browser and
 * locale. Every date now goes through `formatDate`, `formatDateTime`, `formatShortDate` or
 * `formatDayMonth` in `lib/utils.ts`; this fails when a screen formats one by hand again.
 * (`toLocaleString()` on a number is fine: it is the thousands separator.)
 */
const HAND_FORMATTED = /\.toLocale(?:Date|Time)String\(|new Date\([^)]*\)\.toLocaleString\(|Intl\.DateTimeFormat/

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return sources(path)
    return /\.(ts|tsx)$/.test(name) && !/\.test\./.test(name) ? [path] : []
  })
}

// `ReleasesPage` and `ComingToDisc` write a month heading ("December 2026") rather than a
// date, and `PriceAlertsPage` writes UK clock time with its own zone; they are named here so
// the exception is visible, not silent.
const MONTH_OR_ZONED = ['ReleasesPage.tsx', 'ComingToDisc.tsx', 'PriceAlertsPage.tsx']

describe('dates are formatted by lib/utils only', () => {
  it('has no hand-formatted date in a screen', () => {
    const offenders = sources(join(__dirname, '..'))
      .filter((path) => !path.endsWith('lib/utils.ts'))
      .filter((path) => !MONTH_OR_ZONED.some((name) => path.endsWith(name)))
      .filter((path) => HAND_FORMATTED.test(readFileSync(path, 'utf8')))
    expect(offenders).toEqual([])
  })
})
