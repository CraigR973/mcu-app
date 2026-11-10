import { describe, expect, it } from 'vitest'

import { cinemaFilmLinks, imdbUrl, letterboxdUrl } from './external-links'

describe('letterboxdUrl', () => {
  it('resolves to the film page when an IMDb id is present', () => {
    // `letterboxd.com/imdb/<id>` redirects to the film's own page. This is the branch
    // snag 9 asked for, and before Batch S2 it did not exist at all.
    expect(letterboxdUrl({ title: 'The Red Shoes', imdbId: 'tt0040725' })).toBe(
      'https://letterboxd.com/imdb/tt0040725/',
    )
  })

  it('falls back to a search only when the IMDb id is null', () => {
    // 763 of 1,854 films are unidentified and have no id. A search is the honest answer
    // for them — but it must be the *fallback*, not the only branch that ever runs.
    expect(letterboxdUrl({ title: 'The Red Shoes', imdbId: null })).toBe(
      'https://letterboxd.com/search/The%20Red%20Shoes/',
    )
  })

  it('escapes a title that would otherwise change the path', () => {
    // Real rows in this collection carry slashes and question marks — `Test 15.04.26` is
    // the junk row, and `Collector, The` the shape of the messy ones.
    expect(letterboxdUrl({ title: 'Face/Off', imdbId: null })).toBe(
      'https://letterboxd.com/search/Face%2FOff/',
    )
  })

  it('never emits a search URL for a film it can name', () => {
    // The regression this batch exists to prevent: an id present and a search link out.
    const url = letterboxdUrl({ title: 'Heat', imdbId: 'tt0113277' })
    expect(url).not.toContain('/search/')
  })
})

describe('imdbUrl', () => {
  it('links to the title page when there is an id', () => {
    expect(imdbUrl({ imdbId: 'tt0113277' })).toBe('https://www.imdb.com/title/tt0113277/')
  })

  it('is null without one, because IMDb has no useful search fallback', () => {
    expect(imdbUrl({ imdbId: null })).toBeNull()
  })
})

describe('cinemaFilmLinks (AE6, #355 point 5)', () => {
  it('opens a matched film on Letterboxd by its TMDB id, and on IMDb when its id is known', () => {
    expect(cinemaFilmLinks({ kind: 'film', title: 'Rocky', tmdbId: 1366, imdbId: 'tt0075148' })).toEqual({
      letterboxd: 'https://letterboxd.com/tmdb/1366/', imdb: 'https://www.imdb.com/title/tt0075148/', search: false,
    })
    expect(cinemaFilmLinks({ kind: 'film', title: 'Rocky', tmdbId: 1366, imdbId: null })).toEqual({
      letterboxd: 'https://letterboxd.com/tmdb/1366/', imdb: null, search: false,
    })
  })

  it('gives a listing not matched yet a Letterboxd search only, and an event nothing', () => {
    expect(cinemaFilmLinks({ kind: 'listing', title: 'Face/Off (Preview)', tmdbId: null, imdbId: null })).toEqual({
      letterboxd: 'https://letterboxd.com/search/Face%2FOff%20(Preview)/', imdb: null, search: true,
    })
    expect(cinemaFilmLinks({ kind: 'event', title: 'NT Live: Hamlet', tmdbId: null, imdbId: null })).toEqual({ letterboxd: null, imdb: null, search: false })
  })

  it('names a catalogue film without a TMDB id by its IMDb id, else searches', () => {
    expect(cinemaFilmLinks({ kind: 'film', title: 'Old Film', tmdbId: null, imdbId: 'tt0012345' }).letterboxd).toBe('https://letterboxd.com/imdb/tt0012345/')
    expect(cinemaFilmLinks({ kind: 'film', title: 'Old Film', tmdbId: null, imdbId: null })).toMatchObject({ letterboxd: 'https://letterboxd.com/search/Old%20Film/', search: true })
  })
})

