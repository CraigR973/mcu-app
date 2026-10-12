import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, CalendarHeart, Pin, RotateCcw } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ActivityFeed } from '@/components/ActivityFeed'
import { AttentionRow } from '@/components/dashboard/AttentionRow'
import { COLLECTION_ICONS } from '@/components/collections/icons'
import { CollectionShelf } from '@/components/dashboard/CollectionShelf'
import { CompletionShelf } from '@/components/dashboard/CompletionShelf'
import { Highlights } from '@/components/dashboard/Highlights'
import { PosterCard, Shelf } from '@/components/dashboard/Shelf'
import { CompletionSetPanel } from '@/components/insights/CompletionSetPanel'
import { PageHeader } from '@/components/ui/page-header'
import { ComingToDisc } from '@/components/releases/ComingToDisc'
import { StatePanel } from '@/components/ui/state-panel'
import {
  describeFilters,
  fetchOnThisDayMemories,
  fetchRewatchSuggestions,
  fetchSmartCollections,
} from '@/lib/api'
import { stars } from '@/lib/highlights'
import { yearsAgo } from '@/lib/home'
import { queryErrorMessage } from '@/lib/query-state'
import { formatShortDate } from '@/lib/utils'

/**
 * Home — Batch S3's merge of the old Home, Stats and Insights (snag 5, `DECISIONS.md` #154),
 * made a page of rows by Batch W2 (#249).
 *
 * **Every section but Recent activity is a row that scrolls sideways**, as V5's Highlights
 * rows did: Craig's "make all the sections look like highlights so it is a carousel". **The
 * collection comes first** ("maybe also have the collection section at the top"), which
 * replaces T5's "Home opens with the next few disc releases"; they come second.
 *
 * **Every row still hides when it has nothing in it** (#154), and a failed request still
 * shows its own panel. What W2 took away: Home's "Add a disc" (the bottom bar has Add below
 * 1,024 px and the top bar its button above it), Most watched (8 of its 10 films repeated
 * Most rewatched on 5 Oct), and the bid trial with "Update values", which are Admin's
 * "Collection value" now, so Home only reads.
 *
 * `/stats` still redirects here; `/insights` is the full Completion view again.
 */
export default function DashboardPage() {
  // A completion set opens in place of Home, because the panel *is* the page while it is
  // open; otherwise the reader loses their place in a long page on the way back. Home owns
  // which set is open (W2): when the list owned it, Home's swap to a second copy of the list
  // lost it, and the first tap showed every set instead of the one tapped.
  const [openSetId, setOpenSetId] = useState<string | null>(null)

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

  const memories = memoriesQuery.data ?? []
  const rewatchSuggestions = rewatchQuery.data ?? []
  const pinned = pinnedQuery.data?.items ?? []

  if (openSetId !== null) {
    return (
      <div className="page-shell-narrow">
        <CompletionSetPanel setId={openSetId} onBack={() => setOpenSetId(null)} backLabel="Home" />
      </div>
    )
  }

  return (
    <div className="page-shell-narrow">
      {/* Outside the rows' spacing: on a phone the header is hidden (its title is in the top
          bar), and a hidden first child would still leave the gap above the first row. */}
      <PageHeader
        eyebrow="Your archive"
        title="Home"
        description="The collection at a glance, what is coming to disc, the highlights, and how close each set is to complete."
      />

      <div className="space-y-9">
        {/* Batch X2: what has stopped, for Craig, above everything else. Hidden when all is
            well and for Mark. */}
        <AttentionRow />

        <CollectionShelf />

        {/* Batch T5's disc releases, second since W2. Hidden when there are none. */}
        <ComingToDisc limit={12} />

        {/* Batch V5 and V9's rows: top rated, most rewatched, most valuable, best reviewed. */}
        <Highlights />

        {/* On this day: the caller's own viewings from this date in earlier years. */}
        {memoriesQuery.isError ? (
          <StatePanel
            compact
            tone="error"
            title="Watch memories are unavailable"
            description={queryErrorMessage(memoriesQuery.error, 'Could not load your watch memories.')}
          />
        ) : memories.length > 0 ? (
          <Shelf
            id="home-on-this-day"
            title="On this day"
            icon={CalendarHeart}
            caption="Films you watched on this date in earlier years."
          >
            {memories.map((memory) => (
              <PosterCard
                key={memory.id}
                to={`/movies/${memory.movieId}`}
                title={memory.movieTitle}
                posterPath={memory.posterPath}
                detail={yearsAgo(memory.yearsAgo)}
              />
            ))}
          </Shelf>
        ) : null}

        {/* Worth a rewatch: rated highly and not seen for six months. */}
        {rewatchQuery.isError ? (
          <StatePanel
            compact
            tone="error"
            title="Rewatch suggestions are unavailable"
            description={queryErrorMessage(rewatchQuery.error, 'Could not load rewatch suggestions.')}
          />
        ) : rewatchSuggestions.length > 0 ? (
          <Shelf
            id="home-rewatch"
            title="Worth a rewatch"
            icon={RotateCcw}
            caption="Films you rated highly and have not seen for a while."
          >
            {rewatchSuggestions.map((suggestion) => (
              <PosterCard
                key={suggestion.movieId}
                to={`/movies/${suggestion.movieId}`}
                title={suggestion.movieTitle}
                posterPath={suggestion.posterPath}
                detail={
                  <>
                    ★ {stars(suggestion.personalRating)}
                    <span className="block">Last seen {formatShortDate(suggestion.lastWatchedAt)}</span>
                  </>
                }
              />
            ))}
          </Shelf>
        ) : null}

        <CompletionShelf onOpen={setOpenSetId} />

        {/* Pinned collections: hidden until something is pinned. */}
        {pinnedQuery.isError ? (
          <StatePanel
            compact
            tone="error"
            title="Pinned collections are unavailable"
            description={queryErrorMessage(pinnedQuery.error, 'Could not load your pinned collections.')}
          />
        ) : pinned.length > 0 ? (
          <Shelf id="home-pinned" title="Pinned collections" icon={Pin}>
            {pinned.map((collection) => {
              const Icon = COLLECTION_ICONS[collection.icon]
              return (
                <li key={collection.id} className="w-56 shrink-0 snap-start">
                  <Link
                    to={`/collections/${collection.id}`}
                    className="flex h-full flex-col gap-2 rounded-lg border border-border bg-card p-3 hover:border-primary/40"
                  >
                    <span className="flex items-center gap-2 font-semibold text-foreground">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                        <Icon className="h-4 w-4" aria-hidden />
                      </span>
                      <span className="min-w-0 truncate">{collection.name}</span>
                    </span>
                    <span className="line-clamp-2 text-xs leading-5 text-muted-foreground">
                      {describeFilters(collection.filters)}
                    </span>
                  </Link>
                </li>
              )
            })}
          </Shelf>
        ) : null}

        {/* Recent activity stays a list at the foot: a feed reads down, not across. */}
        <section className="space-y-3" aria-labelledby="activity-heading">
          <h2 id="activity-heading" className="section-heading flex items-center gap-2 text-lg">
            <Activity className="h-5 w-5 text-primary" aria-hidden />
            Recent activity
          </h2>
          <div className="archive-panel px-4 py-2 sm:px-5">
            <ActivityFeed limit={10} />
          </div>
        </section>
      </div>
    </div>
  )
}
