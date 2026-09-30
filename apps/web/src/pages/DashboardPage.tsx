import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, BarChart3, CalendarHeart, Pin, Plus, RotateCcw, Target } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ActivityFeed } from '@/components/ActivityFeed'
import { COLLECTION_ICONS } from '@/components/collections/icons'
import { ArchiveStats } from '@/components/dashboard/ArchiveStats'
import { CollectionValue } from '@/components/dashboard/CollectionValue'
import { Button } from '@/components/ui/button'
import { CompletionSets } from '@/components/dashboard/CompletionSets'
import { Highlights } from '@/components/dashboard/Highlights'
import { PageHeader } from '@/components/ui/page-header'
import { ComingToDisc } from '@/components/releases/ComingToDisc'
import { StatePanel } from '@/components/ui/state-panel'
import {
  describeFilters,
  fetchOnThisDayMemories,
  fetchRewatchSuggestions,
  fetchSmartCollections,
} from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

/**
 * Home — Batch S3's merge of the old Home, Stats and Insights (snag 5,
 * `DECISIONS.md` #154).
 *
 * **The capture argued the merge from organisation; the database argued something
 * stronger.** Measured 2026-09-14: `watch_log` 0 rows and `smart_collections` 0, so three
 * of old-Home's four sections — On this day, Worth a rewatch, pinned collections — were
 * *all* empty; Stats had four real charts and two empty ones; Insights had 40 genuine
 * completion sets. Three pages, one page of actual content.
 *
 * **So every section hides when it has nothing in it**, rather than rendering an empty
 * frame. That is the difference between a merge and a longer scroll: three empty panels
 * stacked on top of two more would have produced exactly the page Craig complained about,
 * only taller. What is left is short today and grows on its own — S8's watch-history
 * import is what fills the first two sections.
 *
 * `/stats` and `/insights` redirect here rather than 404: both are in browser history, in
 * the command palette's index, and in whatever links exist outside the app.
 */
export default function DashboardPage() {
  // A completion set opens into a full-screen panel of its own. While it is open the rest
  // of the page is hidden, because the panel *is* the page at that point — otherwise the
  // reader loses their place in a long scroll on the way back.
  const [setOpen, setSetOpen] = useState(false)

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

  if (setOpen) {
    return (
      <div className="page-shell-narrow">
        <CompletionSets onOpenChange={setSetOpen} />
      </div>
    )
  }

  return (
    <div className="page-shell-narrow space-y-10">
      <PageHeader
        eyebrow="Your archive"
        title="Home"
        description="The shape of the collection, what you have been watching, and how close each set is to complete."
        actions={(
          /* Batch S4, snag 7. **Visible below 640px**, unlike the header's own "Add a
             disc" which is `hidden sm:inline-flex`. Not role-gated: `DECISIONS.md` #155
             makes adding a viewer's to do, and every endpoint behind the page moved in
             the same commit. Home is where `/` lands since S3, so this is the first thing
             on the first screen. */
          <Button asChild>
            <Link to="/collection/add">
              <Plus className="h-4 w-4" aria-hidden />
              Add a disc
            </Link>
          </Button>
        )}
      />

      {/* Batch T5, and #201's Home: the next disc releases lead, so buying is one tap from
          the opening screen. Hidden when there are none. */}
      <ComingToDisc limit={5} />

      {/* On this day — hidden entirely until there is a watch history to look back
          through. Empty for both people today: `watch_log` holds 0 rows. */}
      {memoriesQuery.isError ? (
        <StatePanel
          compact
          tone="error"
          title="Watch memories are unavailable"
          description={queryErrorMessage(memoriesQuery.error, 'Could not load your watch memories.')}
        />
      ) : memories.length > 0 ? (
        <section className="space-y-4" aria-labelledby="on-this-day-heading">
          <div>
            <h2 id="on-this-day-heading" className="section-heading flex items-center gap-2">
              <CalendarHeart className="h-5 w-5 text-primary" aria-hidden />
              On this day
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">A look back through your own watch history.</p>
          </div>
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
        </section>
      ) : null}

      {/* Worth a rewatch — same rule, same reason. It needs ratings as well as watches. */}
      {rewatchQuery.isError ? (
        <StatePanel
          compact
          tone="error"
          title="Rewatch suggestions are unavailable"
          description={queryErrorMessage(rewatchQuery.error, 'Could not load rewatch suggestions.')}
        />
      ) : rewatchSuggestions.length > 0 ? (
        <section className="space-y-4" aria-labelledby="rewatch-heading">
          <div>
            <h2 id="rewatch-heading" className="section-heading flex items-center gap-2">
              <RotateCcw className="h-5 w-5 text-primary" aria-hidden />
              Worth a rewatch
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">Films you rated highly and have not seen for a while.</p>
          </div>
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
        </section>
      ) : null}

      {/* Batch V5, snag 9: top rated, most rewatched and most valuable, one request. Each
          row hides while it has nothing in it, and the panel with them. */}
      <Highlights />

      {/* Batch T6, snag 7: the collection at current eBay asking prices. Hidden from a
          viewer until there is a total; an admin sees it earlier, to start the first run. */}
      <CollectionValue />

      {/* The old Stats page. Never empty — 1,857 discs make four of its six charts real —
          so it has no hidden state of its own; the two charts that have no data are
          handled inside it. */}
      <section className="space-y-4" aria-labelledby="stats-heading">
        <h2 id="stats-heading" className="section-heading flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-primary" aria-hidden />
          The collection
        </h2>
        <ArchiveStats />
      </section>

      {/* The old Insights page. 40 real sets, which is why the merge does not produce a
          page of empty headings. */}
      <section className="space-y-4" aria-labelledby="completion-heading">
        <h2 id="completion-heading" className="section-heading flex items-center gap-2">
          <Target className="h-5 w-5 text-primary" aria-hidden />
          Completion
        </h2>
        <p className="-mt-2 text-sm text-muted-foreground">
          How much of each director&rsquo;s and actor&rsquo;s work is on the shelf.
        </p>
        <CompletionSets onOpenChange={setSetOpen} />
      </section>

      {/* Recent activity is the one section that has never been empty — 41 admin actions
          on the day this was measured — so it is always here. */}
      <section className="space-y-4" aria-labelledby="activity-heading">
        <h2 id="activity-heading" className="section-heading flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" aria-hidden />
          Recent activity
        </h2>
        <div className="archive-panel px-4 py-2 sm:px-5">
          <ActivityFeed limit={20} />
        </div>
      </section>

      {/* Pinned collections — hidden until something is pinned. `smart_collections` holds
          0 rows, so this is invisible today; the Collections destination hides itself from
          the menu on the same count. */}
      {pinnedQuery.isError ? (
        <StatePanel
          compact
          tone="error"
          title="Pinned collections are unavailable"
          description={queryErrorMessage(pinnedQuery.error, 'Could not load your pinned collections.')}
        />
      ) : pinned.length > 0 ? (
        <section className="space-y-4" aria-labelledby="pinned-heading">
          <h2 id="pinned-heading" className="section-heading flex items-center gap-2">
            <Pin className="h-5 w-5 text-primary" aria-hidden />
            Pinned collections
          </h2>
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
        </section>
      ) : null}
    </div>
  )
}
