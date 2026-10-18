import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

/**
 * Batch X12b (UX48-06): nothing is set below 12px. The review found 10-11px labels, badges and
 * card details on 32 of 34 screens. A size under 12px is written in this codebase as an
 * arbitrary Tailwind value (`text-[11px]`, `text-[0.6875rem]`) or an inline `fontSize`, so this
 * fails when one comes back. Use `text-xs` (12px), the smallest the app sets.
 */
const BELOW_FLOOR =
  /text-\[(?:1[01]|\d)(?:\.\d+)?px\]|text-\[0\.(?:[0-6]\d*|7[0-4]\d*)rem\]|fontSize:\s*['"]?(?:1[01]|\d)(?:\.\d+)?(?:px|['"]|\b)/

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return sources(path)
    return /\.(ts|tsx|css)$/.test(name) && !/\.test\./.test(name) ? [path] : []
  })
}

describe('no text below 12px', () => {
  it('has no arbitrary type size under 12px in a screen or stylesheet', () => {
    const offenders = sources(join(__dirname, '..')).filter((path) =>
      BELOW_FLOOR.test(readFileSync(path, 'utf8')),
    )
    expect(offenders).toEqual([])
  })
})
