import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Poster } from '@/components/movies/Poster'
import { StatePanel } from '@/components/ui/state-panel'
import { fetchHighlights, formatLabel, type Highlights as HighlightsData } from '@/lib/api'
import { stars, whoseRatings } from '@/lib/highlights'
import { queryErrorMessage } from '@/lib/query-state'
import { formatShortDate } from '@/lib/utils'

function money(price: string, currency: string): string {
  return currency === 'GBP' ? `£${price}` : `${price} ${currency}`
}

interface Card {
  movieId: string
  title: string
  posterPath: string | null
  detail: ReactNode
}

/** One short row of posters, scrolling sideways on a phone; each film opens its page. */
function PosterRow({ id, title, caption, cards }: { id: string; title: string; caption: string; cards: Card[] }) {
  return (
    <section aria-labelledby={id} className="space-y-2">
      <div>
        <h3 id={id} className="text-sm font-semibold text-foreground">{title}</h3>
        <p className="text-xs text-muted-foreground">{caption}</p>
      </div>
      <ul className="-mx-1 flex snap-x gap-3 overflow-x-auto px-1 pb-2">
        {cards.map((card) => (
          <li key={card.movieId} className="w-24 shrink-0 snap-start sm:w-28">
            <Link to={`/movies/${card.movieId}`} className="group block rounded-md">
              <Poster
                path={card.posterPath}
                title={card.title}
                size="w154"
                decorative
                className="aspect-[2/3] w-full rounded-md border border-border object-cover"
              />
              <span className="mt-1.5 block line-clamp-2 text-xs font-semibold leading-4 text-foreground group-hover:text-primary">
                {card.title}
              </span>
              <span className="mt-0.5 block text-xs leading-4 text-muted-foreground">{card.detail}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}

function rows(data: HighlightsData): ReactNode[] {
  const built: ReactNode[] = []
  const top = data.topRated
  if (top.items.length > 0) {
    built.push(
      <PosterRow
        key="top-rated"
        id="highlights-top-rated"
        title="Top rated"
        caption={whoseRatings(top.ratedBy, top.notRatedBy)}
        cards={top.items.map((film) => ({
          movieId: film.movieId,
          title: film.title,
          posterPath: film.posterPath,
          detail: film.ratings.map((entry) => `★ ${stars(entry.rating)} ${entry.personName}`).join(' · '),
        }))}
      />,
    )
  }
  if (data.mostRewatched.length > 0) {
    built.push(
      <PosterRow
        key="most-rewatched"
        id="highlights-most-rewatched"
        title="Most rewatched"
        caption="Watched two or more times, across both diaries."
        cards={data.mostRewatched.map((film) => ({
          movieId: film.movieId,
          title: film.title,
          posterPath: film.posterPath,
          detail: (
            <>
              {film.viewings} viewings
              <span className="block">
                {film.byPerson.map((person) => `${person.personName} ${String(person.viewings)}`).join(' · ')}
              </span>
            </>
          ),
        }))}
      />,
    )
  }
  if (data.mostValuable.length > 0) {
    const first = data.mostValuable[0]
    built.push(
      <PosterRow
        key="most-valuable"
        id="highlights-most-valuable"
        title="Most valuable discs"
        caption={`At their stored value: eBay ${first.basis}, checked ${formatShortDate(first.checkedAt)}.`}
        cards={data.mostValuable.map((disc) => ({
          movieId: disc.movieId,
          title: disc.title,
          posterPath: disc.posterPath,
          detail: (
            <>
              {money(disc.price, disc.currency)} · {formatLabel(disc.formatCode)}
              <span className="block">
                {disc.sampleSize} listings{disc.copies > 1 ? ` · ${String(disc.copies)} copies` : ''}
              </span>
            </>
          ),
        }))}
      />,
    )
  }
  if (data.bestReviewed.length > 0) {
    built.push(
      <PosterRow
        key="best-reviewed"
        id="highlights-best-reviewed"
        title="Best reviewed"
        caption="Blu-ray.com's overall score for the disc, on a format on the shelf."
        cards={data.bestReviewed.map((film) => ({
          movieId: film.movieId,
          title: film.title,
          posterPath: film.posterPath,
          detail: (
            <>
              {film.overall.toFixed(1)}/{film.outOf}
              {film.formatCode ? ` · ${formatLabel(film.formatCode)}` : ''}
            </>
          ),
        }))}
      />,
    )
  }
  return built
}

/**
 * Highlights on Home — Batch V5, snag 9 (`DECISIONS.md` #228: "a mix of all").
 *
 * Short poster rows, each film opening its page: top rated (with whose rating it is), most
 * rewatched across both diaries, the most valuable discs at their stored value, and since
 * V9 the best reviewed, by Blu-ray.com's overall score. **A row with nothing in it is not
 * shown**, and nor is the panel when every row is empty, as Home's other sections do. One
 * request for the whole panel.
 */
export function Highlights() {
  const query = useQuery({ queryKey: ['highlights'], queryFn: fetchHighlights })

  if (query.isError) {
    return (
      <StatePanel
        compact
        tone="error"
        title="Highlights are unavailable"
        description={queryErrorMessage(query.error, 'Could not load the highlights.')}
      />
    )
  }
  if (!query.data) return null
  const built = rows(query.data)
  if (built.length === 0) return null

  return (
    <section className="space-y-5" aria-labelledby="highlights-heading">
      <h2 id="highlights-heading" className="section-heading flex items-center gap-2">
        <Sparkles className="h-5 w-5 text-primary" aria-hidden />
        Highlights
      </h2>
      {built}
    </section>
  )
}
