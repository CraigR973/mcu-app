import { useId, useState, type KeyboardEvent, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Sparkles } from 'lucide-react'

import { valueBehind } from '@/components/collection/value-words'
import { PosterCard, ShelfHeading, ShelfRow } from '@/components/dashboard/Shelf'
import { StatePanel } from '@/components/ui/state-panel'
import { useAuth } from '@/context/auth'
import { fetchHighlights, formatLabel, type Highlights as HighlightsData } from '@/lib/api'
import { addedLine } from '@/lib/highlights'
import { personPath } from '@/lib/people'
import { queryErrorMessage } from '@/lib/query-state'
import { cn, formatShortDate } from '@/lib/utils'

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
interface Tab {
  key: string
  label: string
  caption: string
  cards: Card[]
}

type HighlightsRowData = Pick<HighlightsData, 'mostRewatched' | 'mostValuable' | 'bestReviewed' | 'recentlyAdded'>

function rewatchedTab(data: HighlightsRowData, reader: string | undefined): Tab | null {
  if (data.mostRewatched.length === 0) return null
  return {
    key: 'most-rewatched',
    label: 'Most rewatched',
    caption: 'Watched two or more times, across both diaries.',
    cards: data.mostRewatched.map((film) => ({
      movieId: film.movieId,
      title: film.title,
      posterPath: film.posterPath,
      detail: <>{film.viewings} viewings</>,
      // AE9 (#355): each name opens that person's page (your own opens You), outside the
      // card's own link to the film.
      after: (
        <span className="block text-xs leading-4 text-muted-foreground">
          {film.byPerson.map((person, index) => (
            <span key={person.personId ?? person.personName}>
              {index > 0 ? ' · ' : null}
              {person.personId ? (
                <Link to={personPath(person.personId, reader)} className="hover:text-primary hover:underline">{person.personName} {String(person.viewings)}</Link>
              ) : `${person.personName} ${String(person.viewings)}`}
            </span>
          ))}
        </span>
      ),
    })),
  }
}

/**
 * The rows as tabs, each only when it has a film in it. Top rated stays off Home (AA1).
 *
 * AE2 (#355): Recently added comes first and is where the row opens every visit; then Most
 * valuable, Most rewatched and Best discs. A tab with nothing in it is not offered, so with
 * nothing added in the app the row opens on the next one.
 */
function highlightTabs(data: HighlightsRowData, reader?: string): Tab[] {
  const tabs: Tab[] = []
  if (data.recentlyAdded.length > 0) {
    tabs.push({
      key: 'recently-added',
      label: 'Recently added',
      caption: 'Copies added in the app, newest first, and who added them.',
      cards: data.recentlyAdded.map((film) => ({
        movieId: film.movieId,
        title: film.title,
        posterPath: film.posterPath,
        detail: addedLine(film),
      })),
    })
  }
  if (data.mostValuable.length > 0) {
    const first = data.mostValuable[0]
    tabs.push({
      key: 'most-valuable',
      label: 'Most valuable',
      caption: `At their stored value${first.valuedAs ? ` ${first.valuedAs}` : ''}: eBay ${first.basis}, checked ${formatShortDate(first.checkedAt)}.`,
      cards: data.mostValuable.map((disc) => ({
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
      })),
    })
  }
  const rewatched = rewatchedTab(data, reader)
  if (rewatched) tabs.push(rewatched)
  if (data.bestReviewed.length > 0) {
    tabs.push({
      key: 'best-reviewed',
      label: 'Best discs',
      caption: "Blu-ray.com scores the disc's picture, sound and extras, not the film.",
      cards: data.bestReviewed.map((film) => {
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
      }),
    })
  }
  return tabs
}

/**
 * Highlights as one row with tabs — AC2 (#337).
 *
 * Before AC2 these were three rows of their own, so Home ran seven sideways rows; Craig asked
 * for repetition to go and the redesign keeps at most four. The films come in already free of
 * any shown higher up Home (`home-films.ts`). Arrow keys move between the tabs.
 */
export function HighlightsRow({ data }: { data: HighlightsRowData }) {
  const reader = useAuth().profile?.id
  const tabs = highlightTabs(data, reader)
  const [picked, setPicked] = useState<string | null>(null)
  const id = useId()
  if (tabs.length === 0) return null
  const current = tabs.find((tab) => tab.key === picked) ?? tabs[0]
  const move = (event: KeyboardEvent<HTMLButtonElement>) => {
    const index = tabs.indexOf(current)
    const next = event.key === 'ArrowRight' ? index + 1 : event.key === 'ArrowLeft' ? index - 1 : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : null
    if (next === null) return
    event.preventDefault()
    const tab = tabs[(next + tabs.length) % tabs.length]
    setPicked(tab.key)
    document.getElementById(`${id}-${tab.key}`)?.focus()
  }
  return (
    <section aria-labelledby={`${id}-heading`} className="space-y-3">
      <ShelfHeading id={`${id}-heading`} title="Highlights" icon={Sparkles} caption={current.caption} />
      <div role="tablist" aria-label="Highlights" className="flex gap-1.5 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            id={`${id}-${tab.key}`}
            type="button"
            role="tab"
            aria-selected={tab === current}
            aria-controls={`${id}-panel`}
            tabIndex={tab === current ? 0 : -1}
            onClick={() => setPicked(tab.key)}
            onKeyDown={move}
            className={cn(
              'touch-target min-h-9 shrink-0 rounded-full border px-3 text-xs font-semibold transition-colors',
              tab === current
                ? 'border-transparent bg-primary text-primary-foreground'
                : 'border-border text-muted-foreground hover:text-foreground',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-${current.key}`}>
        <ShelfRow label={current.label}>
          {current.cards.map((card) => (
            <PosterCard
              key={card.movieId}
              to={`/movies/${card.movieId}`}
              title={card.title}
              posterPath={card.posterPath}
              detail={card.detail}
              after={card.after}
            />
          ))}
        </ShelfRow>
      </div>
    </section>
  )
}

/**
 * Highlights on Home — Batch V5, snag 9 (`DECISIONS.md` #228: "a mix of all"), one row since
 * AC2: since AE2 the copies most recently added in the app first, then the most valuable discs
 * at their stored value, the most rewatched across both diaries, and the best discs by
 * Blu-ray.com's overall score. AA1 removed Top rated from Home. A tab with
 * nothing in it is not offered, and the row is not shown when every tab is empty. One request.
 *
 * Home itself reads the same query and passes `HighlightsRow` its films, so none repeats one
 * shown higher up the page; this wrapper is the row on its own.
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
  return <HighlightsRow data={query.data} />
}
