import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

/**
 * Batch S2, snag 3 — the criterion that is a *refusal* rather than a change.
 *
 * Two of the three zoom behaviours Craig reported are fixed by CSS: form controls are
 * 16px at touch widths so focusing one no longer zooms, and `touch-action: manipulation`
 * at the root kills double-tap zoom. **Pinch-zoom is the third and is deliberately left
 * alone** — blocking it would stop anyone enlarging small text, which is a real
 * accessibility cost for a fix nobody asked for.
 *
 * The tempting shortcut is `user-scalable=no` or a `maximum-scale`, because either
 * suppresses all three at once and looks like it worked. This test is here so that
 * shortcut fails loudly instead of shipping. It reads the real `index.html` that Vite
 * serves, not a copy.
 */

const html = readFileSync(
  fileURLToPath(new URL('../../index.html', import.meta.url)),
  'utf8',
)

function viewportContent(): string {
  const match = /<meta\s+name="viewport"\s+content="([^"]*)"/i.exec(html)
  expect(match, 'index.html has no viewport meta tag at all').not.toBeNull()
  return match![1]
}

describe('the viewport meta tag', () => {
  it('exists and sets the width and initial scale', () => {
    const content = viewportContent()
    expect(content).toContain('width=device-width')
    expect(content).toContain('initial-scale=1')
  })

  it('never disables user scaling', () => {
    // `user-scalable=no` is the one-line way to stop every kind of zoom, including the
    // kind somebody uses to read a disc's small print.
    expect(viewportContent()).not.toMatch(/user-scalable\s*=\s*(no|0)/i)
  })

  it('sets no maximum-scale, which is the same ban wearing a different name', () => {
    // iOS treats `maximum-scale=1` as "no pinch zoom" just as firmly as `user-scalable=no`.
    expect(viewportContent()).not.toMatch(/maximum-scale/i)
  })

  it('keeps text-size-adjust from being pinned, so the OS text size still applies', () => {
    // A `-webkit-text-size-adjust: none` would undo the 16px floor on a phone that has
    // been told to use larger text.
    expect(html).not.toMatch(/text-size-adjust:\s*none/i)
  })
})
