import { useQuery } from '@tanstack/react-query'
import { Activity, CalendarHeart, Pin, RotateCcw } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ActivityFeed } from '@/components/ActivityFeed'
import { COLLECTION_ICONS } from '@/components/collections/icons'
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
    <div className="mx-auto max-w-4xl space-y-6 p-4 md:p-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Recent activity and your pinned collections.
        </p>
      </div>

      <section className="space-y-3" aria-labelledby="on-this-day-heading">
        <h2 id="on-this-day-heading" className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <CalendarHeart className="h-4 w-4" />
          On this day
        </h2>
        {memoriesQuery.isPending ? (
          <p className="text-sm text-muted-foreground">Looking through your watch history…</p>
        ) : memoriesQuery.isError ? (
          <p className="text-sm text-destructive">
            {queryErrorMessage(memoriesQuery.error, 'Could not load your watch memories.')}
          </p>
        ) : memories.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No watch memories for this date yet. They will appear here as your history grows.
          </p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2">
            {memories.map((memory) => (
              <li key={memory.id} className="rounded-lg border border-border bg-card p-3">
                <Link to={`/movies/${memory.movieId}`} className="font-medium text-foreground hover:underline">
                  {memory.movieTitle}
                </Link>
                <p className="mt-1 text-sm text-muted-foreground">
                  You watched this {memory.yearsAgo === 1 ? 'one year ago' : `${memory.yearsAgo} years ago`}.
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3" aria-labelledby="rewatch-heading">
        <h2 id="rewatch-heading" className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <RotateCcw className="h-4 w-4" />
          Worth a rewatch
        </h2>
        {rewatchQuery.isPending ? (
          <p className="text-sm text-muted-foreground">Finding films you loved…</p>
        ) : rewatchQuery.isError ? (
          <p className="text-sm text-destructive">
            {queryErrorMessage(rewatchQuery.error, 'Could not load rewatch suggestions.')}
          </p>
        ) : rewatchSuggestions.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Log a rating after watching to receive rewatch suggestions here.
          </p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {rewatchSuggestions.map((suggestion) => (
              <li key={suggestion.movieId} className="rounded-lg border border-border bg-card p-3">
                <Link to={`/movies/${suggestion.movieId}`} className="font-medium text-foreground hover:underline">
                  {suggestion.movieTitle}
                </Link>
                <p className="mt-1 text-sm text-muted-foreground">
                  Your rating: {suggestion.personalRating}/5 · Last watched {suggestion.lastWatchedAt}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Activity className="h-4 w-4" />
          Recent activity
        </h2>
        {/* §13.2's feed. Batch 15 adds loans to it and Batch 20 adds price drops; both
            land in the same endpoint, so this component does not change. */}
        <ActivityFeed limit={20} />
      </section>

      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Pin className="h-4 w-4" />
          Pinned collections
        </h2>

        {state === 'loading' ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : state === 'offline' ? (
          <p className="text-sm text-muted-foreground">
            Waiting for the network — your pinned collections could not be loaded yet.
          </p>
        ) : state === 'error' ? (
          <p className="text-sm text-destructive">
            {queryErrorMessage(pinnedQuery.error, 'Could not load your pinned collections.')}
          </p>
        ) : state === 'empty' ? (
          <p className="text-sm text-muted-foreground">
            Nothing pinned yet.{' '}
            <Link to="/collections" className="text-primary hover:underline">
              Pin a smart collection
            </Link>{' '}
            to see it here.
          </p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {pinned.map((collection) => {
              const Icon = COLLECTION_ICONS[collection.icon]
              return (
                <li key={collection.id} className="rounded-lg border border-border bg-card p-3">
                  <Link
                    to={`/collections/${collection.id}`}
                    className="flex items-center gap-2 font-medium text-foreground hover:underline"
                  >
                    <Icon className="h-4 w-4 shrink-0 text-primary" />
                    <span className="truncate">{collection.name}</span>
                  </Link>
                  <p className="mt-1 truncate text-xs text-muted-foreground">
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
