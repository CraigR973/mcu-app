import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { AttentionList } from './AttentionRow'

describe('AttentionList — Batch X2 (DS44-01, UX48-02)', () => {
  it('names each problem in words, with when it began', () => {
    const html = renderToStaticMarkup(
      <AttentionList
        attention={{
          checkedAt: '2026-10-13T08:00:00Z',
          items: [
            {
              key: 'ebay:listings',
              message: 'No eBay listings read in the last 6 scans (since 9 Oct).',
              since: '2026-10-13T08:00:00Z',
            },
            {
              key: 'person:1:notifications',
              message: 'Mark has no phone getting notifications.',
              since: '2026-10-13T08:00:00Z',
            },
            { key: 'check:stale', message: "The daily check hasn't run since 11 Oct.", since: null },
          ],
        }}
      />,
    )
    expect(html).toContain('Needs attention')
    expect(html).toContain('No eBay listings read in the last 6 scans (since 9 Oct).')
    expect(html).toContain('Mark has no phone getting notifications.<span class="text-muted-foreground"> · since 13 Oct')
    // Not twice for a message that already says since when.
    expect(html).toContain('(since 9 Oct).</li>')
    expect(html).toContain('The daily check hasn&#x27;t run since 11 Oct.')
  })

  it('is not there at all when nothing is wrong', () => {
    expect(renderToStaticMarkup(<AttentionList attention={{ checkedAt: null, items: [] }} />)).toBe(
      '',
    )
  })
})
