import { renderToStaticMarkup } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom/server'
import { describe, expect, it } from 'vitest'

import { MovieCard } from './MovieCard'

describe('MovieCard', () => {
  it('makes unidentified films visible and links by UUID', () => {
    const markup = renderToStaticMarkup(
      <StaticRouter location="/movies">
        <MovieCard movie={{
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
          copyCount: 2,
          locations: [{ section: 'Front', shelf: '2nd', label: 'Front 2nd' }],
          watched: true,
          lastWatchedAt: '2025-03-12',
          editions: ['Masters of Cinema', 'SteelBook'],
        }} />
      </StaticRouter>,
    )

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
})
