import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import DuplicatePrompt from './DuplicatePrompt'
import type { DuplicateCheck } from '@/lib/api'

const owningBluRay: DuplicateCheck = {
  movieId: '3f2504e0-4f89-11d3-9a0c-0305e82c3302',
  movieTitle: 'Heat',
  isDuplicate: true,
  existingCopies: [
    {
      id: '3f2504e0-4f89-11d3-9a0c-0305e82c3303',
      formats: ['blu_ray'],
      locationLabel: 'Back 6th',
      condition: 'good',
    },
  ],
  isUpgrade: true,
  bestFormatOwned: 'blu_ray',
  barcodeCopy: null,
  maybeOwned: null,
}

function markup(duplicate: DuplicateCheck) {
  return renderToStaticMarkup(
    <MemoryRouter>
      <DuplicatePrompt duplicate={duplicate} onConfirm={() => {}} onCancel={() => {}} />
    </MemoryRouter>,
  )
}

describe('DuplicatePrompt', () => {
  it('offers the upgrade choice when the new disc beats what is owned', () => {
    // §3.5's acceptance criterion, as the person adding the disc actually sees it:
    // "Adding a 4K when Blu-ray exists triggers the upgrade prompt".
    const html = markup(owningBluRay)

    expect(html).toContain('This is an upgrade')
    expect(html).toContain('Add another copy')
    expect(html).toContain('You already own this on Blu-ray')
    // §3.5 also asks for the existing formats *and locations*.
    expect(html).toContain('Back 6th')
  })

  it('offers only "another copy" when the format is not an upgrade', () => {
    const html = markup({ ...owningBluRay, isUpgrade: false, bestFormatOwned: '4k_uhd' })

    expect(html).not.toContain('This is an upgrade')
    expect(html).toContain('Add another copy')
    expect(html).toContain('already in the collection')
  })

  it('counts the copies already on a shelf', () => {
    const html = markup({
      ...owningBluRay,
      existingCopies: [
        ...owningBluRay.existingCopies,
        {
          id: '3f2504e0-4f89-11d3-9a0c-0305e82c3304',
          formats: ['dvd', 'download'],
          locationLabel: 'Digital',
          condition: null,
        },
      ],
    })

    expect(html).toContain('2 copies are already on a shelf')
    // A combo pack is one row holding several formats, and reads as one.
    expect(html).toContain('DVD + Digital')
  })

  it('names the copy a scanned barcode is already on, and says a box is one copy (X10)', () => {
    const html = markup({
      ...owningBluRay,
      isUpgrade: false,
      bestFormatOwned: '4k_uhd',
      existingCopies: [],
      barcodeCopy: {
        id: '3f2504e0-4f89-11d3-9a0c-0305e82c3305',
        movieId: '3f2504e0-4f89-11d3-9a0c-0305e82c3306',
        movieTitle: '12 Angry Men',
        formats: ['4k_uhd'],
        locationLabel: 'Front 4th',
      },
    })

    expect(html).toContain('This barcode is already in the collection')
    expect(html).not.toContain('copies are already on a shelf')
    expect(html).toContain('12 Angry Men')
    expect(html).toContain('Front 4th')
    expect(html).toContain('A box holding two formats is one copy')
    expect(html).toContain('href="/movies/3f2504e0-4f89-11d3-9a0c-0305e82c3306"')
  })
})
