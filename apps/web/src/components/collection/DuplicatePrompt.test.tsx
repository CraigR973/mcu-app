import { renderToStaticMarkup } from 'react-dom/server'
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
}

function markup(duplicate: DuplicateCheck) {
  return renderToStaticMarkup(
    <DuplicatePrompt duplicate={duplicate} onConfirm={() => {}} onCancel={() => {}} />,
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
})
