/**
 * Links out to the film databases — IMDb and Letterboxd.
 *
 * **Every Letterboxd link in this app used to be a search link**, and not as an edge case:
 * `letterboxd_slug` is `NULL` for all 1,854 films, TMDB does not supply it and no import
 * populates it, so the search fallback was the only branch that ever ran (snag 9 of the
 * 2026-09-14 owner triage). The film's own page was one redirect away the whole time —
 * Letterboxd resolves `letterboxd.com/imdb/<imdbId>` to it — and `MovieDetailResponse`
 * already carries `imdbId`, so the fix needed no schema change and no new request.
 *
 * **The ceiling is real and worth stating.** 1,091 of 1,854 films have an IMDb id, so this
 * takes roughly **59%** of the collection from a search page to the right page. The rest are
 * the unidentified rows the April import never resolved; they improve when they are
 * identified, not before, and a search link stays the only honest answer for them.
 */

/** The film's Letterboxd page when we can name the film, a search when we cannot.
 *
 *  `letterboxd_slug` is deliberately **not** consulted. It is null for every row in the
 *  database and nothing writes it, so a branch reading it would be dead code that looks
 *  like a feature — and `imdb/<id>` lands on exactly the same page the slug would. */
export function letterboxdUrl(movie: { title: string; imdbId: string | null }): string {
  if (movie.imdbId) return `https://letterboxd.com/imdb/${encodeURIComponent(movie.imdbId)}/`
  return `https://letterboxd.com/search/${encodeURIComponent(movie.title)}/`
}

/** IMDb, which has no search fallback: without an id there is nothing to link to. */
export function imdbUrl(movie: { imdbId: string | null }): string | null {
  return movie.imdbId ? `https://www.imdb.com/title/${encodeURIComponent(movie.imdbId)}/` : null
}
