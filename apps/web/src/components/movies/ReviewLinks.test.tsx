// @vitest-environment happy-dom
import { cleanup, render, screen, within } from '@testing-library/react'
import type { FilmReview } from '@mcu/shared'
import { afterEach, describe, expect, it } from 'vitest'

import { ReviewLinks } from './ReviewLinks'

/** Blu-ray.com's review of Dog Soldiers 4K, as read from the captured page (3 Oct). */
const BLURAY_COM: FilmReview = {
  site: 'bluray_com',
  siteName: 'Blu-ray.com',
  url: 'https://www.blu-ray.com/movies/Dog-Soldiers-4K-Blu-ray/314666/',
  formatCode: '4k_uhd',
  title: 'Dog Soldiers 4K Blu-ray (4K Ultra HD + Blu-ray)',
  description: 'Dog Soldiers 4K Blu-ray Release Date August 23, 2022.',
  scores: [
    { heading: 'Movie', score: 3.5 },
    { heading: 'Video 4K', score: 4 },
    { heading: 'Video 2K', score: 4.5 },
    { heading: 'Audio', score: 3.5 },
    { heading: 'Extras', score: 5 },
    { heading: 'Overall', score: 4 },
  ],
  overall: 4,
  outOf: 5,
  scoresReadAt: '2026-10-03T02:20:00Z',
  note: null,
}

const AVFORUMS: FilmReview = {
  site: 'avforums',
  siteName: 'AVForums',
  url: 'https://www.avforums.com/reviews/dog-soldiers-4k-blu-ray-review-dolby-vision.20024/',
  formatCode: '4k_uhd',
  title: 'Dog Soldiers 4K Blu-ray Review | AVForums',
  description: 'The 4K image, with Dolby Vision, is stunning.',
  scores: [],
  overall: null,
  outOf: null,
  scoresReadAt: null,
  note: 'AVForums does not allow apps to read its pages, so its scores are not shown.',
}

afterEach(cleanup)

describe('ReviewLinks — Batch V9', () => {
  it('reads "Reviews: Blu-ray.com · AVForums", each a link to the review', () => {
    render(<ReviewLinks reviews={[BLURAY_COM, AVFORUMS]} />)

    const links = screen.getAllByRole('link')
    expect(links.map((link) => link.textContent)).toEqual(['Blu-ray.com (4K UHD)', 'AVForums (4K UHD)'])
    expect(links.map((link) => link.getAttribute('href'))).toEqual([BLURAY_COM.url, AVFORUMS.url])
    for (const link of links) {
      expect(link.getAttribute('target')).toBe('_blank')
      expect(link.getAttribute('rel')).toBe('noreferrer')
    }
    expect(screen.getByText('Reviews:')).not.toBeNull()
  })

  it("shows Blu-ray.com's scores under its own headings, out of 5", () => {
    render(<ReviewLinks reviews={[BLURAY_COM]} />)
    const line = within(screen.getByRole('listitem'))

    expect(line.getByText('4.0/5')).not.toBeNull()
    expect(line.getByText('Movie 3.5 · Video 4K 4.0 · Video 2K 4.5 · Audio 3.5 · Extras 5.0')).not.toBeNull()
    expect(line.getByText(BLURAY_COM.description ?? '')).not.toBeNull()
  })

  it('says why AVForums has no scores, and shows its Brave line', () => {
    render(<ReviewLinks reviews={[AVFORUMS]} />)
    const line = within(screen.getByRole('listitem'))

    expect(line.queryByText(/\/5|\/10/)).toBeNull()
    expect(line.getByText(AVFORUMS.note ?? '')).not.toBeNull()
    expect(line.getByText('The 4K image, with Dolby Vision, is stunning.')).not.toBeNull()
  })

  it('says a Blu-ray.com review is waiting to be read', () => {
    const waiting: FilmReview = {
      ...BLURAY_COM,
      scores: [],
      overall: null,
      outOf: null,
      scoresReadAt: null,
      note: 'Its scores are read overnight.',
    }
    render(<ReviewLinks reviews={[waiting]} />)

    expect(screen.getByText('Its scores are read overnight.')).not.toBeNull()
    expect(screen.queryByText(/overall/)).toBeNull()
  })

  it('renders nothing when no review was found', () => {
    const { container } = render(<ReviewLinks reviews={[]} />)
    expect(container.innerHTML).toBe('')
  })
})
