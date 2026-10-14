import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Award, Gem, Repeat, Star, type LucideIcon } from 'lucide-react'

import { valueBehind } from '@/components/collection/value-words'
import { PosterCard, Shelf } from '@/components/dashboard/Shelf'
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

/** One row of posters; each film opens its page. A peer of Home's other rows since W2. */
function PosterRow({
  id,
  title,
  icon,
  caption,
  cards,
}: {
  id: string
  title: string
  icon: LucideIcon
  caption: string
  cards: Card[]
}) {
  return (
    <Shelf id={id} title={title} icon={icon} caption={caption}>
      {cards.map((card) => (
        <PosterCard
          key={card.movieId}
          to={`/movies/${card.movieId}`}
          title={card.title}
          posterPath={card.posterPath}
          detail={card.detail}
        />
      ))}
    </Shelf>
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
        icon={Star}
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
        icon={Repeat}
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
        icon={Gem}
        title="Most valuable discs"
        caption={`At their stored value${first.valuedAs ? ` ${first.valuedAs}` : ''}: eBay ${first.basis}, checked ${formatShortDate(first.checkedAt)}.`}
        cards={data.mostValuable.map((disc) => ({
          movieId: disc.movieId,
          title: disc.title,
          posterPath: disc.posterPath,
          detail: (
            <>
              {money(disc.price, disc.currency)} · {formatLabel(disc.formatCode)}
              <span className="block">
                {disc.valueBasis && disc.low && disc.high
                  ? valueBehind(
                      { ...disc, valueBasis: disc.valueBasis, low: disc.low, high: disc.high },
                      { short: true },
                    )
                  : `${String(disc.sampleSize)} listings`}
                {disc.copies > 1 ? ` · ${String(disc.copies)} copies` : ''}
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
        icon={Award}
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
 * shown**, and nothing at all when every row is empty, as Home's other sections do. One
 * request for all four.
 *
 * **Since W2 the rows are peers of Home's other rows** (#249: "make all the sections look
 * like highlights"), so the "Highlights" heading over them has gone: each row is a section
 * of its own, with its own heading.
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
  return <>{built}</>
}
