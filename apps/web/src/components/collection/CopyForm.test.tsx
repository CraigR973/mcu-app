import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import CopyForm, { EMPTY_COPY } from './CopyForm'
import type { CollectionItemFields } from '@/lib/api'

function markup(value: CollectionItemFields) {
  // A fresh client per render so one test's cache cannot decide another's output.
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <CopyForm value={value} onChange={() => {}} />
    </QueryClientProvider>,
  )
}

describe('CopyForm', () => {
  it('offers §3.2’s editable fields — location, format, notes, condition and price', () => {
    const html = markup(EMPTY_COPY)

    expect(html).toContain('Formats')
    expect(html).toContain('4K UHD')
    expect(html).toContain('Blu-ray')
    expect(html).toContain('Section')
    expect(html).toContain('Condition')
    expect(html).toContain('Collector edition')
    expect(html).toContain('Price paid')
    expect(html).toContain('Notes')
  })

  it('falls back to a free-text location when no section is chosen', () => {
    // The facets query has not resolved here, so the section picker is empty — the
    // form must still be usable, because "somewhere the vocabulary does not cover" is
    // a real answer for two of the 1,857 rows.
    const html = markup(EMPTY_COPY)

    expect(html).toContain('Somewhere else')
    expect(html).toContain('Front 2nd shelf')
  })

  it('reveals the playback note only once an issue is flagged (§3.11)', () => {
    expect(markup(EMPTY_COPY)).not.toContain('Freezes about an hour in')
    expect(markup({ ...EMPTY_COPY, hasPlaybackIssues: true })).toContain(
      'Freezes about an hour in',
    )
  })

  it('marks the chosen formats as pressed so a combo pack reads correctly', () => {
    const html = markup({ ...EMPTY_COPY, formats: ['4k_uhd', 'download'] })
    // Three of the four are unpressed; the two chosen are not.
    expect(html.match(/aria-pressed="true"/g)).toHaveLength(2)
  })

  it('will not offer a purchase date in the future', () => {
    const today = new Date().toISOString().slice(0, 10)
    expect(markup(EMPTY_COPY)).toContain(`max="${today}"`)
  })
})
