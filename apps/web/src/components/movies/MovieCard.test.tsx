import { renderToStaticMarkup } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom/server'
import { describe, expect, it } from 'vitest'

import type { MovieListItem } from '@/lib/api'
import { MovieCard } from './MovieCard'

const unidentified: MovieListItem = {
  id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
  title: 'Shelf title only',
  originalTitle: null,
  year: null,
  posterPath: null,
  backdropPath: null,
  tmdbRating: null,
  runtimeMinutes: null,
  bestFormatOwned: 'blu_ray',
  bestHdrOwned: null,
  bestAudioOwned: null,
  identified: false,
  setAsideAs: null,
  copyCount: 2,
  locations: [{ section: 'Front', shelf: '2nd', label: 'Front 2nd' }],
  watched: true,
  lastWatchedAt: '2025-03-12',
  editions: ['Masters of Cinema', 'SteelBook'],
}

function markupOf(movie: MovieListItem): string {
  return renderToStaticMarkup(
    <StaticRouter location="/movies">
      <MovieCard movie={movie} />
    </StaticRouter>,
  )
}

describe('MovieCard', () => {
  it('makes unidentified films visible and links by UUID', () => {
    const markup = markupOf(unidentified)

    expect(markup).toContain('/movies/3f2504e0-4f89-11d3-9a0c-0305e82c3301')
    expect(markup).toContain('Identify')
    expect(markup).toContain('2 copies')
    expect(markup).toContain('Blu-ray')
    // Batch 6: where it is, and that it has been seen.
    expect(markup).toContain('Front 2nd')
    expect(markup).toContain('Watched')
    // Batch U2: which editions are on the shelf.
    expect(markup).toContain('Masters of Cinema · SteelBook')
  })

  it('flags a film for identifying only when "Still to identify" would list it', () => {
    // Mark, 15 Oct: Broadchurch, set aside as a TV series, carried the Identify badge but was
    // never under "Still to identify".
    const series = markupOf({ ...unidentified, title: 'Broadchurch', setAsideAs: 'tv' })
    expect(series).not.toContain('Identify')
    expect(series).toContain('TV series')

    const notAFilm = markupOf({ ...unidentified, title: 'A concert', setAsideAs: 'not_film' })
    expect(notAFilm).not.toContain('Identify')
    expect(notAFilm).not.toContain('TV series')

    const matched = markupOf({ ...unidentified, identified: true })
    expect(matched).not.toContain('Identify')
  })
})
