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
  mediaType: null,
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

  it('flags a title for identifying exactly when "Still to identify" would list it', () => {
    // Mark, 15 Oct: Broadchurch, set aside as a TV series, carried the Identify badge but was
    // never listed. Since Batch Y3 it is listed, to be identified as a series, so it is
    // flagged; only a title set aside as not a film is neither.
    const setAside = markupOf({ ...unidentified, title: 'Broadchurch', setAsideAs: 'tv', mediaType: 'tv' })
    expect(setAside).toContain('Identify')

    const notAFilm = markupOf({ ...unidentified, title: 'A concert', setAsideAs: 'not_film' })
    expect(notAFilm).not.toContain('Identify')
    expect(notAFilm).not.toContain('TV series')

    const matched = markupOf({ ...unidentified, identified: true, mediaType: 'film' })
    expect(matched).not.toContain('Identify')
    expect(matched).not.toContain('TV series')
  })

  it('says "TV series" on a title identified as one (Batch Y3)', () => {
    const series = markupOf({ ...unidentified, title: 'Band of Brothers', identified: true, mediaType: 'tv' })
    expect(series).toContain('TV series')
    expect(series).not.toContain('Identify')
  })

  it('says "In doubt" on an identified film with an open doubt, and nowhere else (Batch Y4)', () => {
    const doubted = markupOf({ ...unidentified, title: 'Good Fellas', identified: true, mediaType: 'film', inDoubt: true })
    expect(doubted).toContain('In doubt')
    expect(doubted).not.toContain('Identify')

    // A list cached before Y4 has no flag; a title not yet identified says "Identify".
    expect(markupOf({ ...unidentified, identified: true, mediaType: 'film' })).not.toContain('In doubt')
    const waiting = markupOf({ ...unidentified, inDoubt: true })
    expect(waiting).toContain('Identify')
    expect(waiting).not.toContain('In doubt')
  })
})
