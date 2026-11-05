import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CalendarHeart, Pin } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useAuth } from '@/context/auth'

import { HomeBanner } from '@/components/brand/HomeBanner'
import { AttentionRow } from '@/components/dashboard/AttentionRow'
import { CinemaStrip } from '@/components/dashboard/CinemaStrip'
import { CollectionLedger } from '@/components/dashboard/CollectionLedger'
import { CompletionShelf } from '@/components/dashboard/CompletionShelf'
import { FeaturedFilm } from '@/components/dashboard/FeaturedFilm'
import { HighlightsRow } from '@/components/dashboard/Highlights'
import { NeedsYouRow } from '@/components/dashboard/NeedsYouRow'
import { PosterCard, Shelf, ShelfHeading } from '@/components/dashboard/Shelf'
import { COLLECTION_ICONS } from '@/components/collections/icons'
import { CompletionSetPanel } from '@/components/insights/CompletionSetPanel'
import { PageHeader } from '@/components/ui/page-header'
import { ComingToDisc } from '@/components/releases/ComingToDisc'
import { StatePanel } from '@/components/ui/state-panel'
import {
  describeFilters,
  fetchAttention,
  fetchCalendar,
  fetchCollectionValue,
  fetchHighlights,
  fetchNeedsYou,
  fetchStats,
  fetchOnThisDayMemories,
  fetchRewatchSuggestions,
  fetchSmartCollections,
} from '@/lib/api'
import { homeLineup } from '@/lib/home-films'
import { queryErrorMessage } from '@/lib/query-state'
import { DISC_WINDOW_DAYS } from '@/lib/releases'

/**
 * Home — AC2's one ledger and varied modules, Craig's pick A (#337).
 *
 * In page order: the banner (T1, the photo letters with live type); what needs the person and
 * their next screening (AC1); Craig's "Needs attention"; the collection as one ledger; one
 * featured film with Feeling lucky inside it; then three poster rows (Coming to disc,
 * Highlights' tabs, For you), the sets closest to complete as a short list, and the cinemas.
 * At most four sideways rows, with AC4's cinema strip; one short caption each.
 *
 * **No film twice in one load** (`home-films.ts`): the featured film and the rows take their
 * films in page order, each where it comes first. Every module still hides when it has nothing
 * in it (#154), and a failed read still says so. The featured film and the rows read what Home
 * already read, and the banner comes from the device after its first load; AC4's cinema strip
 * adds one read, shared with At the cinema.
 *
 * `/stats` still redirects here; `/insights` is the full Completion view.
 */
export default function DashboardPage() {
  const { profile } = useAuth()
  // Observe the existing cache keys: the children share these requests. Home targets
  // must not accept a tap while the first archive/attention layout is still arriving (AB7).
  const homeStats = useQuery({ queryKey: ['stats', profile?.id], queryFn: fetchStats })
  const homeValue = useQuery({ queryKey: ['collection-value'], queryFn: fetchCollectionValue })
  const homeAttention = useQuery({ queryKey: ['attention'], queryFn: fetchAttention, enabled: profile?.role === 'admin' })
  // AC1: "Needs you" arrives above everything, so it is part of the first layout too.
  const homeNeedsYou = useQuery({ queryKey: ['needs-you', profile?.id], queryFn: fetchNeedsYou, enabled: Boolean(profile) })
  const homeLayoutPending = homeStats.isLoading || homeValue.isLoading || homeAttention.isLoading || homeNeedsYou.isLoading
  // AC2: the two rows above the ledger arrive before anything under them is drawn, so nothing
  // is pushed down when they do. On 4 Nov, Craig's "Needs attention" moved the ledger 142 px.
  const topSettled = !homeNeedsYou.isLoading && !homeAttention.isLoading
  // A completion set opens in place of Home, because the panel *is* the page while it is
  // open; otherwise the reader loses their place in a long page on the way back (W2).
  const [openSetId, setOpenSetId] = useState<string | null>(null)

  const memoriesQuery = useQuery({ queryKey: ['memories', 'on-this-day'], queryFn: fetchOnThisDayMemories })
  const rewatchQuery = useQuery({ queryKey: ['memories', 'rewatch-suggestions'], queryFn: fetchRewatchSuggestions })
  const highlightsQuery = useQuery({ queryKey: ['highlights'], queryFn: fetchHighlights })
  // The same key and freshness as the Releases page, so the two share one request.
  const calendarQuery = useQuery({
    queryKey: ['calendar', DISC_WINDOW_DAYS],
    queryFn: () => fetchCalendar(DISC_WINDOW_DAYS),
    staleTime: 10 * 60 * 1000,
  })
  const pinnedQuery = useQuery({ queryKey: ['smart-collections', 'pinned'], queryFn: () => fetchSmartCollections(true) })

  // The line-up waits for every read it draws on, so a film never jumps from one module to
  // another as the answers arrive. A failed read passes nothing and its module says so.
  const lineupSettled = !memoriesQuery.isPending && !rewatchQuery.isPending && !highlightsQuery.isPending && !calendarQuery.isPending
  const lineup = useMemo(
    () => homeLineup({
      rewatch: rewatchQuery.data,
      highlights: highlightsQuery.data,
      calendar: calendarQuery.data?.items,
      onThisDay: memoriesQuery.data,
    }),
    [rewatchQuery.data, highlightsQuery.data, calendarQuery.data, memoriesQuery.data],
  )
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
        description="What needs you, the collection at a glance, a film for tonight, and what is coming."
      />

      <HomeBanner className="mb-9" />

      {!topSettled ? <div aria-hidden className="h-[32rem] animate-pulse rounded-lg bg-muted/40" /> : null}
      <div className={topSettled ? 'space-y-9' : 'hidden'}>
        {/* AC1 (#335): what the person signed in can act on now, and since AC2 their next
            screening. Hidden when there is nothing. */}
        <NeedsYouRow />

        {/* Batch X2: what has stopped, for Craig. Hidden when all is well and for Mark. */}
        <AttentionRow />

        <CollectionLedger />

        {lineupSettled ? (
          <FeaturedFilm pick={lineup.featured} homeLayoutPending={homeLayoutPending} />
        ) : (
          // The featured card's own height while its films arrive.
          <div aria-hidden className="h-52 animate-pulse rounded-lg bg-muted/50" />
        )}

        {lineupSettled ? <ComingToDisc limit={12} entries={lineup.discs} /> : null}

        {highlightsQuery.isError ? (
          <StatePanel
            compact
            tone="error"
            title="Highlights are unavailable"
            description={queryErrorMessage(highlightsQuery.error, 'Could not load the highlights.')}
          />
        ) : lineupSettled && lineup.highlights ? (
          <HighlightsRow data={lineup.highlights} />
        ) : null}

        {memoriesQuery.isError ? (
          <StatePanel
            compact
            tone="error"
            title="Watch memories are unavailable"
            description={queryErrorMessage(memoriesQuery.error, 'Could not load your watch memories.')}
          />
        ) : null}
        {rewatchQuery.isError ? (
          <StatePanel
            compact
            tone="error"
            title="Rewatch suggestions are unavailable"
            description={queryErrorMessage(rewatchQuery.error, 'Could not load rewatch suggestions.')}
          />
        ) : null}
        {lineupSettled && lineup.forYou.length > 0 ? (
          <Shelf
            id="home-for-you"
            title="For you"
            icon={CalendarHeart}
            caption="On this day, and favourites you have not seen for a while."
          >
            {lineup.forYou.map((film) => (
              <PosterCard key={film.movieId} to={`/movies/${film.movieId}`} title={film.title} posterPath={film.posterPath} detail={film.detail} />
            ))}
          </Shelf>
        ) : null}

        <CompletionShelf onOpen={setOpenSetId} />

        {/* AC4: this week's films at the cinema, after everything above has taken its own. */}
        <CinemaStrip lineup={lineup} settled={lineupSettled} homeLayoutPending={homeLayoutPending} />

        {/* Pinned collections: hidden until something is pinned; links, not a sideways row. */}
        {pinnedQuery.isError ? (
          <StatePanel
            compact
            tone="error"
            title="Pinned collections are unavailable"
            description={queryErrorMessage(pinnedQuery.error, 'Could not load your pinned collections.')}
          />
        ) : pinned.length > 0 ? (
          <section aria-labelledby="home-pinned" className="space-y-3">
            <ShelfHeading id="home-pinned" title="Pinned collections" icon={Pin} />
            <ul className="flex flex-wrap gap-2">
              {pinned.map((collection) => {
                const Icon = COLLECTION_ICONS[collection.icon]
                return (
                  <li key={collection.id}>
                    <Link
                      to={`/collections/${collection.id}`}
                      title={describeFilters(collection.filters)}
                      className="touch-target inline-flex min-h-11 items-center gap-2 rounded-full border border-border bg-card px-3 text-sm font-semibold text-foreground hover:border-primary/40"
                    >
                      <Icon className="h-4 w-4 text-primary" aria-hidden />
                      {collection.name}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </section>
        ) : null}
      </div>
    </div>
  )
}
