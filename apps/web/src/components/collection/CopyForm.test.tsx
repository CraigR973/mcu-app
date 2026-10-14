// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'

import CopyForm, { EMPTY_COPY } from './CopyForm'
import type { CollectionFacets, CollectionItemFields } from '@/lib/api'

function markup(value: CollectionItemFields, facets?: CollectionFacets) {
  // A fresh client per render so one test's cache cannot decide another's output.
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  if (facets) client.setQueryData(['facets'], facets)
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
    // Batch U2: the copy's edition, and the spreadsheet's grouping under its own name. The
    // grouping was labelled "Collector edition" until editions had a field of their own.
    expect(html).toContain('Edition')
    expect(html).toContain('Sub-category')
    expect(html).not.toContain('Collector edition')
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

  it('holds the edition it is given, and caps it at the column’s 100 characters — Batch U2', () => {
    const html = markup({ ...EMPTY_COPY, edition: 'Zavvi Exclusive SteelBook' })

    expect(html).toContain('value="Zavvi Exclusive SteelBook"')
    expect(html).toContain('maxLength="100"')
    expect(EMPTY_COPY.edition).toBeNull()
  })

  it('will not offer a purchase date in the future', () => {
    const today = new Date().toISOString().slice(0, 10)
    expect(markup(EMPTY_COPY)).toContain(`max="${today}"`)
  })

  it('offers every section, including one with no disc yet — Batch V4', () => {
    // Craig's house held nothing when it was added; a picker built from the places that
    // hold a disc could never offer it.
    const html = markup(EMPTY_COPY, {
      sections: [{ section: 'Front', movieCount: 1, itemCount: 1, shelves: [] }],
      unsectionedItemCount: 0,
      decades: [],
      undatedMovieCount: 0,
      discsWithSpecs: 0,
      allSections: ['Front', 'Back', "Craig's house"],
    })

    expect(html).toContain('<option value="Craig&#x27;s house">Craig&#x27;s house</option>')
    expect(html).toContain('<option value="Back">Back</option>')
  })

  it('offers the places that hold a disc when an older cached answer has no vocabulary', () => {
    const html = markup(EMPTY_COPY, {
      sections: [{ section: 'Front', movieCount: 1, itemCount: 1, shelves: [] }],
      unsectionedItemCount: 0,
      decades: [],
      undatedMovieCount: 0,
      discsWithSpecs: 0,
      allSections: [],
    })

    expect(html).toContain('<option value="Front">Front</option>')
    expect(html).not.toContain('Craig')
  })

  it('shows a disc already in Craig\u2019s house as chosen, with no shelf picker', () => {
    const html = markup(
      { ...EMPTY_COPY, section: "Craig's house", location: "Craig's house" },
      {
        sections: [{ section: "Craig's house", movieCount: 1, itemCount: 1, shelves: [] }],
        unsectionedItemCount: 0,
        decades: [],
        undatedMovieCount: 0,
        discsWithSpecs: 0,
        allSections: ['Front', "Craig's house"],
      },
    )

    expect(html).toMatch(/<option value="Craig&#x27;s house" selected="">/)
    expect(html).not.toContain('No particular shelf')
  })

  it('drops the old text when the shelf changes, as it does for a new section', () => {
    // Mark's 12 Angry Men, 13 Oct: the shelf went from 3rd to 4th and "Front 3rd shelf"
    // stayed, so the film page showed both places.
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    client.setQueryData(['facets'], {
      sections: [{ section: 'Front', movieCount: 2, itemCount: 2, shelves: [
        { shelf: '3rd', movieCount: 1, itemCount: 1 },
        { shelf: '4th', movieCount: 1, itemCount: 1 },
      ] }],
      unsectionedItemCount: 0,
      decades: [],
      undatedMovieCount: 0,
      discsWithSpecs: 0,
      allSections: ['Front'],
    })
    const onChange = vi.fn()
    render(
      <QueryClientProvider client={client}>
        <CopyForm
          value={{ ...EMPTY_COPY, formats: ['blu_ray'], section: 'Front', shelf: '3rd', location: 'Front 3rd shelf' }}
          onChange={onChange}
        />
      </QueryClientProvider>,
    )

    fireEvent.change(screen.getByDisplayValue('3rd shelf'), { target: { value: '4th' } })

    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ section: 'Front', shelf: '4th', location: null }))
  })

  const LOUNGE_FACETS: CollectionFacets = {
    sections: [
      {
        section: 'Lounge',
        movieCount: 96,
        itemCount: 96,
        shelfNoun: 'side',
        shelves: [
          { shelf: 'Left', label: 'Left hand side', movieCount: 0, itemCount: 0 },
          { shelf: 'Right', label: 'Right hand side', movieCount: 96, itemCount: 96 },
        ],
      },
    ],
    unsectionedItemCount: 0,
    decades: [],
    undatedMovieCount: 0,
    discsWithSpecs: 0,
    allSections: ['Front', 'Lounge', 'Garage'],
  }

  it('offers the Lounge’s two sides as a picker, not a box to type in — Mark, 14 Oct', () => {
    const html = markup({ ...EMPTY_COPY, section: 'Lounge' }, LOUNGE_FACETS)

    expect(html).toContain('Side')
    expect(html).toContain('No particular side')
    expect(html).toContain('<option value="Left">Left hand side</option>')
    expect(html).toContain('<option value="Right">Right hand side</option>')
    expect(html).not.toContain('shelf</option>')
  })

  it('picking a side drops the old text, so the API writes the side’s own', () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    client.setQueryData(['facets'], LOUNGE_FACETS)
    const onChange = vi.fn()
    render(
      <QueryClientProvider client={client}>
        <CopyForm
          value={{ ...EMPTY_COPY, formats: ['4k_uhd'], section: 'Lounge', shelf: null, location: 'Lounge' }}
          onChange={onChange}
        />
      </QueryClientProvider>,
    )

    fireEvent.change(screen.getByDisplayValue('No particular side'), { target: { value: 'Right' } })

    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ section: 'Lounge', shelf: 'Right', location: null }))
  })

  it('asks for detail, not a whole place, once a section without shelves is chosen', () => {
    const html = markup({ ...EMPTY_COPY, section: 'Garage' }, LOUNGE_FACETS)

    expect(html).toContain('Anything more, e.g. top row')
    expect(html).not.toContain('placeholder="Front 2nd shelf"')
  })

  it('names shelves as before when an older cached answer has no labels', () => {
    const html = markup(
      { ...EMPTY_COPY, section: 'Front' },
      {
        ...LOUNGE_FACETS,
        sections: [
          { section: 'Front', movieCount: 1, itemCount: 1, shelves: [{ shelf: '2nd', movieCount: 1, itemCount: 1 }] },
        ],
      },
    )

    expect(html).toContain('<option value="2nd">2nd shelf</option>')
    expect(html).toContain('No particular shelf')
  })
})

afterEach(() => cleanup())
