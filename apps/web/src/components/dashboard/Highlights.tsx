import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Award, Gem, Repeat, type LucideIcon } from 'lucide-react'

import { valueBehind } from '@/components/collection/value-words'
import { PosterCard, Shelf } from '@/components/dashboard/Shelf'
import { StatePanel } from '@/components/ui/state-panel'
import { fetchHighlights, formatLabel, type Highlights as HighlightsData } from '@/lib/api'
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
  after?: ReactNode
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
          after={card.after}
        />
      ))}
    </Shelf>
  )
}

function rows(data: HighlightsData): ReactNode[] {
  const built: ReactNode[] = []
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
        title="Best discs"
        caption="Blu-ray.com scores the disc's picture, sound and extras, not the film."
        cards={data.bestReviewed.map((film) => {
          // The response schema supplies these from a fresh API response; older offline Home
          // entries predate AA2, so retain their existing card instead of crashing it.
          const scores = film.scores ?? []
          return {
            movieId: film.movieId,
            title: film.title,
            posterPath: film.posterPath,
            detail: (
              <>
                Strongest for {film.strength ?? 'the disc'}
                <span className="block">
                  {film.overall.toFixed(1)}/{film.outOf}
                  {film.formatCode ? ` · ${formatLabel(film.formatCode)}` : ''}
                </span>
              </>
            ),
            after: scores.length > 0 ? (
              <details className="mt-1 text-xs leading-4 text-muted-foreground">
                <summary className="cursor-pointer text-primary underline-offset-2 hover:underline">Scores</summary>
                <span className="mt-0.5 block">
                  {scores.map((score) => `${score.heading} ${score.score.toFixed(1)}`).join(' · ')}
                </span>
              </details>
            ) : undefined,
          }
        })}
      />,
    )
  }
  return built
}

/**
 * Highlights on Home — Batch V5, snag 9 (`DECISIONS.md` #228: "a mix of all").
 *
 * Short poster rows, each film opening its page: most rewatched across both diaries,
 * the most valuable discs at their stored value, and the best discs by Blu-ray.com's
 * overall score. AA1 removed Top rated from Home. **A row with nothing in it is not
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
