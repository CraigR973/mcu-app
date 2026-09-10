import { useQuery } from '@tanstack/react-query'
import { Activity, CalendarHeart, Pin, RotateCcw } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ActivityFeed } from '@/components/ActivityFeed'
import { COLLECTION_ICONS } from '@/components/collections/icons'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import {
  describeFilters,
  fetchOnThisDayMemories,
  fetchRewatchSuggestions,
  fetchSmartCollections,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

/**
 * §6.31's "pinned to the home dashboard".
 *
 * Batch 12 put the pinned section here, because §11.5 lists "pin to dashboard" as one of
 * its three bullets and a pin toggle with nowhere to appear is a control that does nothing
 * — the exact defect `STATUS.md` gotcha 5 catalogues four instances of in the onboarding
 * wizard. Batch 14 adds §13.2's activity feed above it; the charts live on `/stats`,
 * because §6's own page table gives them their own route.
 *
 * Only the pinned ones are fetched. Loading the whole sidebar to render three tiles
 * would ship every collection the person owns to display the few they chose.
 */
export default function DashboardPage() {
  const memoriesQuery = useQuery({
    queryKey: ['memories', 'on-this-day'],
    queryFn: fetchOnThisDayMemories,
  })
  const rewatchQuery = useQuery({
    queryKey: ['memories', 'rewatch-suggestions'],
    queryFn: fetchRewatchSuggestions,
  })
  const pinnedQuery = useQuery({
    queryKey: ['smart-collections', 'pinned'],
    queryFn: () => fetchSmartCollections(true),
  })
  const pinned = pinnedQuery.data?.items ?? []
  const state = listState(pinnedQuery, pinned.length === 0)
  const memories = memoriesQuery.data ?? []
  const rewatchSuggestions = rewatchQuery.data ?? []

  return (
    <div className="page-shell-narrow space-y-10">
      <PageHeader
        eyebrow="Your archive"
        title="Dashboard"
        description="Watch memories, rewatch ideas and the parts of the collection you return to most."
      />

      <section className="space-y-4" aria-labelledby="on-this-day-heading">
        <div>
          <h2 id="on-this-day-heading" className="section-heading flex items-center gap-2">
            <CalendarHeart className="h-5 w-5 text-primary" aria-hidden />
            On this day
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">A look back through your own watch history.</p>
        </div>
        {memoriesQuery.isPending ? (
          <StatePanel compact tone="loading" title="Looking through your watch history" />
        ) : memoriesQuery.isError ? (
          <StatePanel
            compact
            tone="error"
            title="Watch memories are unavailable"
            description={queryErrorMessage(memoriesQuery.error, 'Could not load your watch memories.')}
          />
        ) : memories.length === 0 ? (
          <StatePanel
            compact
            tone="empty"
            title="No memories for today—yet"
            description="They will appear here as your watch history grows."
          />
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2">
            {memories.map((memory) => (
              <li key={memory.id} className="archive-panel border-l-2 border-l-accent p-4">
                <Link to={`/movies/${memory.movieId}`} className="font-display text-lg font-semibold text-foreground hover:text-primary">
                  {memory.movieTitle}
                </Link>
                <p className="mt-2 text-sm leading-5 text-muted-foreground">
                  You watched this {memory.yearsAgo === 1 ? 'one year ago' : `${memory.yearsAgo} years ago`}.
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-4" aria-labelledby="rewatch-heading">
        <div>
          <h2 id="rewatch-heading" className="section-heading flex items-center gap-2">
            <RotateCcw className="h-5 w-5 text-primary" aria-hidden />
            Worth a rewatch
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">Films you rated highly and have not seen for a while.</p>
        </div>
        {rewatchQuery.isPending ? (
          <StatePanel compact tone="loading" title="Finding films you loved" />
        ) : rewatchQuery.isError ? (
          <StatePanel
            compact
            tone="error"
            title="Rewatch suggestions are unavailable"
            description={queryErrorMessage(rewatchQuery.error, 'Could not load rewatch suggestions.')}
          />
        ) : rewatchSuggestions.length === 0 ? (
          <StatePanel
            compact
            tone="empty"
            title="No rewatch suggestions yet"
            description="Log a rating after watching to receive suggestions here."
          />
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {rewatchSuggestions.map((suggestion) => (
              <li key={suggestion.movieId} className="archive-panel p-4">
                <Link to={`/movies/${suggestion.movieId}`} className="font-semibold text-foreground hover:text-primary">
                  {suggestion.movieTitle}
                </Link>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  <span className="text-foreground">{suggestion.personalRating}/5</span> from you · Last watched {suggestion.lastWatchedAt}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="section-heading flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" aria-hidden />
          Recent activity
        </h2>
        {/* §13.2's feed. Batch 15 adds loans to it and Batch 20 adds price drops; both
            land in the same endpoint, so this component does not change. */}
        <div className="archive-panel px-4 py-2 sm:px-5">
          <ActivityFeed limit={20} />
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="section-heading flex items-center gap-2">
          <Pin className="h-5 w-5 text-primary" aria-hidden />
          Pinned collections
        </h2>

        {state === 'loading' ? (
          <StatePanel compact tone="loading" title="Loading pinned collections" />
        ) : state === 'offline' ? (
          <StatePanel
            compact
            tone="offline"
            title="Pinned collections are not cached here"
            description="Reconnect to load them on this device."
          />
        ) : state === 'error' ? (
          <StatePanel
            compact
            tone="error"
            title="Pinned collections are unavailable"
            description={queryErrorMessage(pinnedQuery.error, 'Could not load your pinned collections.')}
          />
        ) : state === 'empty' ? (
          <StatePanel
            compact
            tone="empty"
            title="Nothing pinned yet"
            description="Pin a smart collection to keep it close at hand."
            action={
              <Link to="/collections" className="inline-flex min-h-11 items-center text-sm font-semibold text-primary hover:underline">
                Browse collections
              </Link>
            }
          />
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {pinned.map((collection) => {
              const Icon = COLLECTION_ICONS[collection.icon]
              return (
                <li key={collection.id} className="archive-panel p-4">
                  <Link
                    to={`/collections/${collection.id}`}
                    className="flex min-h-11 items-center gap-3 font-semibold text-foreground hover:text-primary"
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <Icon className="h-4 w-4" aria-hidden />
                    </span>
                    <span className="min-w-0 truncate">{collection.name}</span>
                  </Link>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">
                    {describeFilters(collection.filters)}
                  </p>
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </div>
  )
}
