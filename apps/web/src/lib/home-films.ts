import type { CalendarEntry, Highlights, OnThisDayMemory, RewatchSuggestion } from './api'
import { cinemaSections, type CinemaFilms, type CinemaLine } from './cinemas'
import { stars } from './highlights'
import { isPhysical } from './releases'
import { formatShortDate } from './utils'

/**
 * AC2: no film twice on Home in one load.
 *
 * Home's modules ask for their films separately, and the same favourite turns up in several
 * of them: on 4 Nov Double Indemnity was in Most rewatched, Best discs and Mark's Worth a
 * rewatch at once. Each module takes its films in page order from one shared ledger of what
 * is already showing, so a film appears where it comes first and nowhere after.
 */
export class HomeFilms {
  private readonly shown = new Set<string>()

  /** The first `count` of `items` not already on the page, which then count as shown. */
  take<T>(items: readonly T[], keyOf: (item: T) => string | null, count = Infinity): T[] {
    const out: T[] = []
    for (const item of items) {
      if (out.length >= count) break
      const key = keyOf(item)
      if (key !== null && this.shown.has(key)) continue
      if (key !== null) this.shown.add(key)
      out.push(item)
    }
    return out
  }

  /** Like `take`, but leaves the ledger alone: for alternatives only one of which shows,
   *  such as Highlights' tabs, which must each avoid what came before them. */
  peek<T>(items: readonly T[], keyOf: (item: T) => string | null, count = Infinity): T[] {
    return items.filter((item) => { const key = keyOf(item); return key === null || !this.shown.has(key) }).slice(0, count)
  }

  /** Mark films as shown without taking them, after `peek`. */
  claim(keys: Iterable<string | null>): void {
    for (const key of keys) if (key !== null) this.shown.add(key)
  }
}


/** The film Home leads with, from what it has already read. */
export interface FeaturedPick {
  movieId: string
  title: string
  posterPath: string | null
  /** Why this film: "Worth a rewatch", "Most rewatched". */
  eyebrow: string
  detail: string
}

/** What Home shows below the ledger, each film in the first place it belongs and no other. */
export interface HomeLineup {
  featured: FeaturedPick | null
  discs: CalendarEntry[]
  highlights: Pick<Highlights, 'mostRewatched' | 'mostValuable' | 'bestReviewed' | 'recentlyAdded'> | null
  forYou: { movieId: string; title: string; posterPath: string | null; detail: string }[]
}

const ROW = 12

function lastSeen(iso: string): string {
  return `Last seen ${formatShortDate(iso).replace(/^\d+ /, '')}`
}

/**
 * A film coming on 4K and Blu-ray is one card, not two: "4K UHD + Blu-ray". Most upcoming
 * releases are films the collection does not hold, so they are matched by title and date.
 */
function oneCardPerFilm(entries: CalendarEntry[]): CalendarEntry[] {
  const cards = new Map<string, CalendarEntry>()
  for (const entry of entries) {
    const key = entry.movieId ?? `${entry.title.trim().toLowerCase()}:${entry.releaseDate}`
    const card = cards.get(key)
    if (!card) cards.set(key, entry)
    else if (!card.typeLabel.split(' + ').includes(entry.typeLabel)) cards.set(key, { ...card, typeLabel: `${card.typeLabel} + ${entry.typeLabel}` })
  }
  return [...cards.values()]
}

/**
 * Home's line-up in page order — AC2 (#337): the featured film, Coming to disc, Highlights'
 * tabs, then For you. A module whose read failed or has not come back passes nothing.
 */
export function homeLineup(input: {
  rewatch?: RewatchSuggestion[]
  highlights?: Highlights
  calendar?: CalendarEntry[]
  onThisDay?: OnThisDayMemory[]
}): HomeLineup {
  const films = new HomeFilms()
  const rewatch = input.rewatch ?? []
  const rewatched = input.highlights?.mostRewatched ?? []
  let featured: FeaturedPick | null = null
  const [first] = films.take(rewatch, (film) => film.movieId, 1)
  if (first) {
    featured = {
      movieId: first.movieId,
      title: first.movieTitle,
      posterPath: first.posterPath,
      eyebrow: 'Worth a rewatch',
      detail: `You gave it ★ ${stars(first.personalRating)} and last saw it on ${formatShortDate(first.lastWatchedAt)}.`,
    }
  } else {
    const [most] = films.take(rewatched, (film) => film.movieId, 1)
    if (most) {
      featured = {
        movieId: most.movieId,
        title: most.title,
        posterPath: most.posterPath,
        eyebrow: 'Most rewatched',
        detail: `${String(most.viewings)} viewings across both diaries.`,
      }
    }
  }
  const discs = films.take(oneCardPerFilm((input.calendar ?? []).filter(isPhysical)), (entry) => entry.movieId, ROW)
  let highlights: HomeLineup['highlights'] = null
  if (input.highlights) {
    highlights = {
      mostRewatched: films.peek(input.highlights.mostRewatched, (film) => film.movieId, ROW),
      mostValuable: films.peek(input.highlights.mostValuable, (disc) => disc.movieId, ROW),
      bestReviewed: films.peek(input.highlights.bestReviewed, (film) => film.movieId, ROW),
      // AE2: Recently added, a tab like the others, avoids what came before Highlights.
      recentlyAdded: films.peek(input.highlights.recentlyAdded, (film) => film.movieId, ROW),
    }
    films.claim(
      [...highlights.recentlyAdded, ...highlights.mostRewatched, ...highlights.mostValuable, ...highlights.bestReviewed].map((film) => film.movieId),
    )
  }
  const forYou = [
    ...films.take(input.onThisDay ?? [], (memory) => memory.movieId, ROW).map((memory) => ({
      movieId: memory.movieId,
      title: memory.movieTitle,
      posterPath: memory.posterPath,
      detail: memory.yearsAgo === 1 ? 'A year ago today' : `${String(memory.yearsAgo)} years ago today`,
    })),
    ...films.take(rewatch, (film) => film.movieId, ROW).map((film) => ({
      movieId: film.movieId,
      title: film.movieTitle,
      posterPath: film.posterPath,
      detail: lastSeen(film.lastWatchedAt),
    })),
  ].slice(0, ROW)
  return { featured, discs, highlights, forYou }
}

function sameTitle(title: string): string {
  return title.normalize('NFKD').toLowerCase().replace(/&/g, 'and').replace(/[^a-z0-9]/g, '')
}

/**
 * AC4's strip: this week's films at the cinema, each with a poster, in At the cinema's own order.
 *
 * **It comes last on Home, so it takes what the rows above have left** (AC2's rule, #338): a film
 * already on Home is left out of the strip, matched by its catalogue film or, for a film the
 * collection does not hold, by its title, since Coming to disc may name it with no catalogue film.
 * It is still in At the cinema. Listings not matched to a film yet, and events, are left to the
 * view: a strip is posters.
 */
export function cinemaStrip(lineup: HomeLineup, films: CinemaFilms | undefined, now: number): CinemaLine[] {
  if (!films) return []
  const movies = new Set<string>()
  const titles = new Set<string>()
  const shown = [
    ...(lineup.featured ? [lineup.featured] : []),
    ...lineup.discs,
    ...(lineup.highlights
      ? [...lineup.highlights.recentlyAdded, ...lineup.highlights.mostRewatched, ...lineup.highlights.mostValuable, ...lineup.highlights.bestReviewed]
      : []),
    ...lineup.forYou,
  ]
  for (const film of shown) {
    if (film.movieId) movies.add(film.movieId)
    titles.add(sameTitle(film.title))
  }
  return cinemaSections(films, { run: 'all', day: null, venueIds: null }, now).thisWeek
    .filter(({ card }) => card.posterPath && !(card.movieId && movies.has(card.movieId)) && !titles.has(sameTitle(card.title)))
    .slice(0, ROW)
}
