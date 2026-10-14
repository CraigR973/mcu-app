import { useEffect, useState, type KeyboardEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Clock,
  Disc3,
  ExternalLink,
  Loader2,
  MapPin,
  Pencil,
  Plus,
  RefreshCcw,
  ShieldAlert,
  Star,
} from 'lucide-react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import CopyEditor, { fieldsFrom } from '@/components/collection/CopyEditor'
import { LendButton } from '@/components/collection/LendButton'
import { PhotoGallery } from '@/components/collection/PhotoGallery'
import { SpecBadges } from '@/components/collection/SpecBadges'
import { SalePanel } from '@/components/collection/SalePanel'
import { StoredValue } from '@/components/collection/StoredValue'
import { UpgradePrompt } from '@/components/collection/UpgradePrompt'
import { ValuePanel } from '@/components/collection/ValuePanel'
import { RecommendationsPanel } from '@/components/movies/RecommendationsPanel'
import { StreamingPanel } from '@/components/movies/StreamingPanel'
import { FormatBadge } from '@/components/movies/FormatBadge'
import { ReviewLinks } from '@/components/movies/ReviewLinks'
import { Poster } from '@/components/movies/Poster'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { StatePanel } from '@/components/ui/state-panel'
import ItemHistory from '@/components/collection/ItemHistory'
import IdentifyPanel from '@/components/movies/IdentifyPanel'
import PriceAlertPanel from '@/components/movies/PriceAlertPanel'
import WatchPanel from '@/components/movies/WatchPanel'
import { useAuth } from '@/context/auth'
import { imdbUrl, letterboxdUrl } from '@/lib/external-links'
import { useGoBack } from '@/hooks/useGoBack'
import { useRecentItems } from '@/hooks/useRecentItems'
import {
  backdropUrl,
  bestFormat,
  conditionLabel,
  LISTING_STATUS_LABELS,
  fetchCopies,
  fetchMovie,
  updateCollectionItem,
  type CollectionCopy,
  type ListingStatus,
  type MovieDetail,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

type Tab = 'overview' | 'crew' | 'copies' | 'watch'

function CopyCard({
  item,
  movieId,
  filmTitle,
  year,
  isSeries,
  canEdit,
  isAdmin,
  onEdit,
}: {
  item: CollectionCopy
  movieId: string
  /** The film's title and year, for §4.1's price lookup and §4.3's listing link. Passed
   *  down rather than re-fetched: the copy row carries neither, and the page above has
   *  both. */
  filmTitle: string
  year: number | null
  /** A TV title (`mediaType` tv): its own box sets are what the price check looks for. */
  isSeries: boolean
  /** Either person: edit, move, mark damaged, move to trash (`DECISIONS.md` #264). */
  canEdit: boolean
  /** Craig only: the live eBay check, the sale panel and photo uploads. */
  isAdmin: boolean
  onEdit: (copy: CollectionCopy) => void
}) {
  const queryClient = useQueryClient()

  // §3.11's "mark as damaged" quick action. It is the ordinary update with one field
  // changed — the client already holds the whole copy — so there is only one path that
  // has to remember to stamp `conditionUpdatedAt` and write the audit row.
  const markDamaged = useMutation({
    mutationFn: () =>
      updateCollectionItem(item.id, {
        ...fieldsFrom(item),
        condition: 'damaged',
        hasPlaybackIssues: true,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['movie-copies', movieId] })
      void queryClient.invalidateQueries({ queryKey: ['item-history', movieId] })
    },
  })

  return (
    <article className="archive-panel flex h-full flex-col gap-4 p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-wrap gap-1.5" aria-label="Formats in this copy">
          {item.formats.map((format) => <FormatBadge key={format} format={format} />)}
        </div>
        {item.condition && (
          <Badge tone={item.condition === 'damaged' ? 'danger' : 'neutral'}>
            {conditionLabel(item.condition)} condition
          </Badge>
        )}
      </div>

      {(item.edition || item.subCategory || item.releaseLabel) && (
        <div className="rounded-md border border-accent/35 bg-accent/10 px-3 py-2.5">
          {/* Batch U2: the edition is what makes one copy of a film unlike another. */}
          {item.edition ? (
            <div>
              <p className="metadata-label">Edition</p>
              <p className="mt-0.5 font-display text-lg font-semibold text-foreground">
                {item.edition}
              </p>
            </div>
          ) : null}
          {item.subCategory ? (
            <div className={item.edition ? 'mt-2 border-t border-accent/25 pt-2' : ''}>
              <p className="metadata-label">Sub-category</p>
              <p className="metadata-value mt-0.5">{item.subCategory}</p>
            </div>
          ) : null}
          {item.releaseLabel ? (
            <div
              className={
                item.edition || item.subCategory ? 'mt-2 border-t border-accent/25 pt-2' : ''
              }
            >
              <p className="metadata-label">Release label</p>
              <p className="metadata-value mt-0.5">{item.releaseLabel}</p>
            </div>
          ) : null}
        </div>
      )}

      <div className="flex items-start gap-2 rounded-md bg-primary/10 px-3 py-2.5 text-sm">
        <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
        <div>
          {item.location ? (
            <p className="font-semibold text-foreground">{item.location}</p>
          ) : (
            <p className="text-muted-foreground">Location not recorded</p>
          )}
          {item.section && (
            <p className="mt-0.5 text-xs text-muted-foreground">
              {item.section}{item.shelf ? ` · ${item.shelf} shelf` : ''}
            </p>
          )}
        </div>
      </div>

      <dl className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] gap-x-4 gap-y-2 border-t border-border pt-3">
        {item.regionCode ? (
          <>
            <dt className="metadata-label">Region</dt>
            <dd className="metadata-value text-right">{item.regionCode}</dd>
          </>
        ) : null}
        {item.purchaseSource ? (
          <>
            <dt className="metadata-label">Bought from</dt>
            <dd className="metadata-value text-right">{item.purchaseSource}</dd>
          </>
        ) : null}
        {item.purchaseDate ? (
          <>
            <dt className="metadata-label">Bought</dt>
            <dd className="metadata-value text-right"><time dateTime={item.purchaseDate}>{item.purchaseDate}</time></dd>
          </>
        ) : null}
        {item.purchasePrice ? (
          <>
            <dt className="metadata-label">Paid</dt>
            <dd className="metadata-value text-right">£{item.purchasePrice}</dd>
          </>
        ) : null}
      </dl>

      <SpecBadges
        videoSpecs={item.videoSpecs}
        audioSpecs={item.audioSpecs}
        regionCode={item.regionCode}
      />

      {item.notes ? (
        <p className="border-l-2 border-accent pl-3 text-sm italic leading-6 text-muted-foreground">
          {item.notes}
        </p>
      ) : null}
      {item.hasPlaybackIssues && (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <span className="font-semibold">Playback issue</span>
          {item.playbackNotes ? `: ${item.playbackNotes}` : ''}
        </p>
      )}

      {canEdit && (
        <div className="flex flex-wrap gap-2 border-t border-border pt-3">
          <Button type="button" size="sm" variant="secondary" onClick={() => onEdit(item)}>
            <Pencil aria-hidden /> Edit copy
          </Button>
          {item.condition !== 'damaged' && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => markDamaged.mutate()}
              disabled={markDamaged.isPending}
              className="text-destructive hover:bg-destructive/10 hover:text-destructive"
            >
              {markDamaged.isPending ? (
                <Loader2 className="animate-spin" aria-hidden />
              ) : (
                <ShieldAlert aria-hidden />
              )}
              Mark damaged
            </Button>
          )}
        </div>
      )}

      {/* Batch W3 (#249): both people lend, borrow and say a disc is back. Since Y1 (#264)
          both edit the copy, above, too. Only owned copies get a card, so a sold disc
          never offers a loan. */}
      <div className="border-t border-border pt-3">
        <LendButton collectionItemId={item.id} />
      </div>

      {/* Batch T6: the stored value is for both people and costs nothing to show; the live
          check beside it spends an eBay lookup, so it stays with the admin's tools. */}
      {(isAdmin || item.valuation) && (
        <div className="space-y-3 border-t border-border pt-3">
          <h3 className="metadata-label">{isAdmin ? 'Value and resale' : 'Value'}</h3>
          {item.valuation ? <StoredValue valuation={item.valuation} /> : null}
          {isAdmin && (
            <>
              <ValuePanel
                filmTitle={filmTitle}
                year={year}
                formatCode={bestFormat(item.formats)}
                condition={item.condition}
                isSeries={isSeries}
              />
              <div className="border-t border-border pt-3">
                {/* Batch X6: the asking price starts from the disc's value as a used copy. */}
                <SalePanel
                  copy={item}
                  movieId={movieId}
                  suggestedPrice={item.valuation?.status === 'priced' ? item.valuation.price : null}
                />
              </div>
            </>
          )}
        </div>
      )}

      <div className="mt-auto border-t border-border pt-3">
        <h3 className="metadata-label">Disc photos</h3>
        <PhotoGallery itemId={item.id} canEdit={isAdmin} />
      </div>

      {markDamaged.isError && (
        <p role="alert" className="text-sm text-destructive">
          {queryErrorMessage(markDamaged.error, 'Could not update this disc.')}
        </p>
      )}
    </article>
  )
}

export default function MovieDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const goBack = useGoBack('/movies')
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<Tab>('copies')
  const [correcting, setCorrecting] = useState(false)
  const [editing, setEditing] = useState<CollectionCopy | null>(null)
  const { profile } = useAuth()
  const isAdmin = profile?.role === 'admin'
  // `DECISIONS.md` #264, superseding #37: Mark adds discs (#155), so he edits and moves
  // them too. The Trash, the audit history and the eBay tools stay Craig's.
  const canEdit = profile != null
  const movieId = id ?? ''
  const [searchParams, setSearchParams] = useSearchParams()
  const justUpgraded = searchParams.get('upgraded') === '1'

  const movieQuery = useQuery({
    queryKey: ['movie', movieId],
    queryFn: () => fetchMovie(movieId),
    enabled: movieId.length > 0,
  })
  const copiesQuery = useQuery({
    queryKey: ['movie-copies', movieId],
    // `includeSold`, so §4.4's "removes from active views" does not come to mean
    // "unreachable". The two groups are split below: owned discs first, gone ones after.
    queryFn: () => fetchCopies(movieId, true),
    enabled: movieId.length > 0,
  })

  const { addRecentItem } = useRecentItems()
  const viewedMovie = movieQuery.data
  // Phase 6.3's "recent items" index. Keyed on the movie's own id, not the route
  // param, so identifying a film mid-visit (which can change the id — see `identified`
  // below) still records the film that's actually on screen.
  useEffect(() => {
    if (!viewedMovie) return
    addRecentItem({
      id: viewedMovie.id,
      title: viewedMovie.title,
      year: viewedMovie.year,
      posterPath: viewedMovie.posterPath,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewedMovie?.id])

  function identified(movie: MovieDetail) {
    queryClient.setQueryData(['movie', movie.id], movie)
    void queryClient.invalidateQueries({ queryKey: ['movies'] })
    void queryClient.invalidateQueries({ queryKey: ['search'] })
    void queryClient.invalidateQueries({ queryKey: ['movie-copies', movie.id] })
    // The Archive's "Still to identify" count is one fewer (Mark, 14 Oct).
    void queryClient.invalidateQueries({ queryKey: ['collection-facets'] })
    setCorrecting(false)
    if (movie.id !== movieId) navigate(`/movies/${movie.id}`, { replace: true })
  }

  if (movieQuery.fetchStatus === 'paused' && movieQuery.data === undefined) {
    return (
      <div className="page-shell-narrow">
        <StatePanel
          tone="offline"
          title="This film is not available offline"
          description="Reconnect to load the film record, or return to the cached collection."
          action={(
            <div className="flex flex-wrap justify-center gap-2">
              <Button type="button" variant="outline" onClick={() => void movieQuery.refetch()}>
                Try again
              </Button>
              <Button asChild variant="ghost"><Link to="/movies">Back to collection</Link></Button>
            </div>
          )}
        />
      </div>
    )
  }

  if (movieQuery.isPending) {
    return (
      <div className="page-shell-narrow">
        <StatePanel tone="loading" title="Opening film record" description="Loading archive details…" />
      </div>
    )
  }

  if (movieQuery.isError || !movieQuery.data) {
    return (
      <div className="page-shell-narrow">
        <StatePanel
          tone="error"
          title="Could not open this film"
          description={queryErrorMessage(movieQuery.error, 'The film record did not respond.')}
          action={(
            <div className="flex flex-wrap justify-center gap-2">
              <Button type="button" variant="outline" onClick={() => void movieQuery.refetch()}>
                Try again
              </Button>
              <Button asChild variant="ghost"><Link to="/movies">Back to collection</Link></Button>
            </div>
          )}
        />
      </div>
    )
  }

  const movie = movieQuery.data
  const allCopies = copiesQuery.data ?? []
  // "Owned" matches the server's `owned_copy()`: a disc listed for sale is still a disc
  // on the shelf, and only a sale or a donation takes it out of the collection.
  const copies = allCopies.filter(
    (copy) => copy.listingStatus === 'in_collection' || copy.listingStatus === 'listed_for_sale',
  )
  const goneCopies = allCopies.filter((copy) => !copies.includes(copy))
  const copiesState = listState(copiesQuery, copies.length === 0)
  const runtime = movie.runtimeMinutes
    ? `${Math.floor(movie.runtimeMinutes / 60)}h ${movie.runtimeMinutes % 60}m`
    : null
  const rating = movie.tmdbRating ? movie.tmdbRating.toFixed(1) : null
  const backdrop = backdropUrl(movie.backdropPath)
  // Batch S2, snag 9. Both builders live in `lib/external-links.ts` so each branch can be
  // asserted directly — the Letterboxd one had two branches and only ever took the worse.
  const imdbHref = imdbUrl(movie)
  const letterboxdHref = letterboxdUrl(movie)

  const tabs: { key: Tab; label: string; count?: number }[] = [
    { key: 'copies', label: 'Owned copies', count: movie.copyCount },
    { key: 'overview', label: 'Overview' },
    { key: 'crew', label: 'Crew', count: movie.crew.length },
    // Batch 16 (§7.1, §7.2). One tab, because "where can I watch this" and "what else
    // is like it" are the same question asked twice.
    { key: 'watch', label: 'Where to watch' },
  ]

  function moveTab(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let nextIndex: number | null = null
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length
    if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length
    if (event.key === 'Home') nextIndex = 0
    if (event.key === 'End') nextIndex = tabs.length - 1
    if (nextIndex === null) return

    event.preventDefault()
    const next = tabs[nextIndex].key
    setTab(next)
    requestAnimationFrame(() => document.getElementById(`movie-tab-${next}`)?.focus())
  }

  const panelLabelledBy = `movie-tab-${tab}`

  return (
    <div className="min-h-full pb-24 lg:pb-12">
      <div className="relative h-44 overflow-hidden bg-surface-sunken sm:h-52 lg:h-60">
        {backdrop ? (
          <img src={backdrop} alt="" className="absolute inset-0 h-full w-full object-cover opacity-45" />
        ) : null}
        <div className="absolute inset-0 bg-gradient-to-t from-background via-background/40 to-brand-ink/25" />
        {/* Batch V1, snag 5. Back to wherever the film was opened from (Deals, Wanted, a
            movie night, search), and to the Archive only with no history behind it. It used
            to go to the Archive every time. Hidden below 1024px, where the top bar's arrow
            does the same job: two back controls on a phone was the snag. */}
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={goBack}
          className="absolute left-4 top-4 hidden sm:left-6 lg:left-8 lg:inline-flex"
        >
          <ArrowLeft aria-hidden /> Back
        </Button>
      </div>

      <div className="relative mx-auto -mt-16 w-full max-w-[96rem] px-4 sm:px-6 lg:px-8">
        <header className="flex items-end gap-4 sm:gap-6">
          <div className="w-24 shrink-0 overflow-hidden rounded-lg border border-border bg-muted shadow-lift sm:w-28 md:w-36">
            <Poster path={movie.posterPath} title={movie.title} className="w-full" eager />
          </div>
          <div className="min-w-0 flex-1 pb-1">
            {movie.tagline ? (
              <p className="mb-1 line-clamp-2 text-sm italic text-muted-foreground">{movie.tagline}</p>
            ) : null}
            <h1 className="font-display text-2xl font-semibold leading-tight text-foreground sm:text-4xl lg:text-5xl">
              {movie.title}
            </h1>
            <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-muted-foreground">
              {movie.year ? <span>{movie.year}</span> : null}
              {runtime ? <span className="inline-flex items-center gap-1"><Clock className="h-4 w-4" aria-hidden />{runtime}</span> : null}
              {rating ? <span className="inline-flex items-center gap-1"><Star className="h-4 w-4 fill-accent text-accent" aria-hidden />{rating}</span> : null}
              {movie.bestFormatOwned ? <FormatBadge format={movie.bestFormatOwned} /> : null}
              <span className="inline-flex items-center gap-1 font-medium text-foreground">
                <Disc3 className="h-4 w-4 text-primary" aria-hidden />
                {movie.copyCount} {movie.copyCount === 1 ? 'owned copy' : 'owned copies'}
              </span>
            </div>
            {movie.locations.length > 0 ? (
              <p className="mt-2 flex items-start gap-1.5 text-sm text-muted-foreground">
                <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
                <span>{movie.locations.map((location) => location.label).join(' · ')}</span>
              </p>
            ) : null}
          </div>
        </header>

        <div className="mt-5 flex flex-wrap gap-2 sm:ml-[9.5rem] lg:ml-[10.5rem]">
          {imdbHref ? (
            <Button asChild size="sm" variant="outline">
              <a href={imdbHref} target="_blank" rel="noreferrer">IMDb <ExternalLink aria-hidden /></a>
            </Button>
          ) : null}
          {movie.identified ? (
            <Button asChild size="sm" variant="outline">
              <a href={letterboxdHref} target="_blank" rel="noreferrer">Letterboxd <ExternalLink aria-hidden /></a>
            </Button>
          ) : null}
          {movie.identified ? (
            <Button type="button" size="sm" variant="secondary" onClick={() => setCorrecting((value) => !value)}>
              <RefreshCcw aria-hidden /> {correcting ? 'Cancel correction' : 'Correct match'}
            </Button>
          ) : null}
        </div>

        <ReviewLinks reviews={movie.reviews} className="mt-4 max-w-3xl sm:ml-[9.5rem] lg:ml-[10.5rem]" />

        {(!movie.identified || correcting) ? (
          <div className="mt-8">
            <IdentifyPanel movieId={movie.id} storedTitle={movie.title} onIdentified={identified} />
          </div>
        ) : null}

        <div className="mt-8 grid min-w-0 gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(19rem,24rem)]">
          <section className="min-w-0" aria-label="Film record">
            {/* Each tab is `shrink-0` (Batch U3's browser check). On a touch screen
                `touch-target`'s 44px minimum width replaces a flex item's automatic one, so
                at 375px the tabs shrank below their labels and each count spilled onto the
                next tab. Now the strip scrolls instead. */}
            <div
              role="tablist"
              aria-label="Film details"
              className="flex gap-1 overflow-x-auto border-b border-border"
            >
              {tabs.map(({ key, label, count }, index) => (
                <button
                  key={key}
                  id={`movie-tab-${key}`}
                  type="button"
                  role="tab"
                  aria-selected={tab === key}
                  aria-controls={`movie-panel-${key}`}
                  tabIndex={tab === key ? 0 : -1}
                  onClick={() => setTab(key)}
                  onKeyDown={(event) => moveTab(event, index)}
                  className={`touch-target -mb-px min-h-11 shrink-0 whitespace-nowrap border-b-2 px-3 py-2 text-sm font-semibold transition-colors sm:px-4 ${tab === key ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
                >
                  {label}
                  {count !== undefined && count > 0 ? (
                    <span className="ml-1.5 rounded-full bg-muted px-1.5 py-0.5 text-xs">{count}</span>
                  ) : null}
                </button>
              ))}
            </div>

            {tab === 'copies' ? (
              <div id="movie-panel-copies" role="tabpanel" aria-labelledby={panelLabelledBy} tabIndex={0} className="mt-6 space-y-5 focus:outline-none">
                {/* §4.2's tail. Arrived at by confirming "this is an upgrade" on the add
                    form, which is what puts `?upgraded=1` on this URL — so the prompt
                    appears exactly once, for the person who just upgraded. */}
                {justUpgraded && canEdit ? (
                  <UpgradePrompt
                    movieId={movie.id}
                    filmTitle={movie.title}
                    isSeries={movie.mediaType === 'tv'}
                    copies={copies}
                    onDismiss={() => setSearchParams({}, { replace: true })}
                  />
                ) : null}
                <div className="flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="page-kicker">The archive answer</p>
                    <h2 className="section-heading">Owned copies</h2>
                    <p className="mt-1 text-sm text-muted-foreground">Format, edition and shelf for every catalogued copy.</p>
                  </div>
                  {canEdit ? (
                    <Button asChild size="sm">
                      <Link to="/collection/add"><Plus aria-hidden /> Add a copy</Link>
                    </Button>
                  ) : null}
                </div>

                {copiesState === 'loading' ? (
                  <StatePanel tone="loading" title="Loading owned copies" description="Checking editions and shelf locations…" />
                ) : copiesState === 'offline' ? (
                  <StatePanel
                    tone="offline"
                    title="Copy details are not cached"
                    description="Reconnect to check editions and locations for this film."
                    action={<Button type="button" variant="outline" onClick={() => void copiesQuery.refetch()}>Try again</Button>}
                  />
                ) : copiesState === 'error' ? (
                  <StatePanel
                    tone="error"
                    title="Could not load the owned copies"
                    description={queryErrorMessage(copiesQuery.error, 'The collection record did not respond.')}
                    action={<Button type="button" variant="outline" onClick={() => void copiesQuery.refetch()}>Try again</Button>}
                  />
                ) : copiesState === 'empty' ? (
                  <StatePanel
                    tone="empty"
                    title="No live copies in the collection"
                    description={isAdmin ? 'Add a copy if this film should still be in the archive.' : 'Add a copy if this film should still be in the archive. Craig can restore one from the Trash.'}
                    icon={Disc3}
                  />
                ) : (
                  <div className="grid gap-4 xl:grid-cols-2">
                    {copies.map((copy) => (
                      <CopyCard
                        key={copy.id}
                        item={copy}
                        movieId={movie.id}
                        filmTitle={movie.title}
                        year={movie.year}
                        isSeries={movie.mediaType === 'tv'}
                        canEdit={canEdit}
                        isAdmin={isAdmin}
                        onEdit={setEditing}
                      />
                    ))}
                  </div>
                )}

                {/* §4.4. Sold and donated discs keep their row — nothing is deleted —
                    so they are shown here rather than vanishing. The audit log is the
                    other half of "remains in audit/trash". */}
                {goneCopies.length > 0 && (
                  <section className="mt-8 border-t border-border pt-5">
                    <h2 className="section-heading">No longer in the collection</h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {goneCopies.length === 1 ? 'One disc has' : `${goneCopies.length} discs have`}{' '}
                      left the shelves. The record stays, including what it fetched.
                    </p>
                    <ul className="mt-3 space-y-2">
                      {goneCopies.map((copy) => (
                        <li
                          key={copy.id}
                          className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-muted/40 px-3 py-2.5 text-sm"
                        >
                          <span className="flex flex-wrap items-center gap-2">
                            {copy.formats.map((format) => (
                              <FormatBadge key={format} format={format} />
                            ))}
                            <Badge tone="neutral">
                              {LISTING_STATUS_LABELS[copy.listingStatus as ListingStatus] ??
                                copy.listingStatus}
                            </Badge>
                          </span>
                          {copy.listingPrice ? (
                            <span className="text-muted-foreground">£{copy.listingPrice}</span>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
              </div>
            ) : null}

            {tab === 'overview' ? (
              <div id="movie-panel-overview" role="tabpanel" aria-labelledby={panelLabelledBy} tabIndex={0} className="mt-6 space-y-8 focus:outline-none">
                {movie.overview ? (
                  <p className="max-w-3xl text-[0.9375rem] leading-7 text-muted-foreground">{movie.overview}</p>
                ) : movie.identified ? (
                  <p className="text-sm text-muted-foreground">No overview is available for this film.</p>
                ) : (
                  <p className="text-sm text-muted-foreground">Choose the film above to add its overview and cast.</p>
                )}

                {movie.cast.length > 0 ? (
                  <section>
                    <h2 className="section-heading mb-4">Cast</h2>
                    <div className="flex gap-4 overflow-x-auto pb-3">
                      {movie.cast.map((member) => (
                        <div key={`${member.tmdbPersonId}-${member.personName}`} className="w-24 shrink-0 text-center">
                          <div className="mx-auto flex h-20 w-20 items-center justify-center overflow-hidden rounded-full bg-muted text-xl text-muted-foreground">
                            {member.profilePath ? (
                              <img src={`https://image.tmdb.org/t/p/w185${member.profilePath}`} alt="" className="h-full w-full object-cover" loading="lazy" />
                            ) : member.personName.charAt(0)}
                          </div>
                          <p className="mt-2 line-clamp-2 text-sm font-medium text-foreground">{member.personName}</p>
                          {member.characterName ? <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{member.characterName}</p> : null}
                        </div>
                      ))}
                    </div>
                  </section>
                ) : null}
              </div>
            ) : null}

            {tab === 'crew' ? (
              <div id="movie-panel-crew" role="tabpanel" aria-labelledby={panelLabelledBy} tabIndex={0} className="mt-6 focus:outline-none">
                {movie.crew.length === 0 ? (
                  <StatePanel tone="empty" title="No crew data available" compact />
                ) : (
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    {movie.crew.map((member) => (
                      <div key={`${member.role}-${member.tmdbPersonId}-${member.personName}`} className="archive-panel px-4 py-3">
                        <p className="text-sm font-semibold text-foreground">{member.personName}</p>
                        <p className="mt-0.5 text-xs capitalize text-muted-foreground">{member.role}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : null}

            {tab === 'watch' ? (
              <div id="movie-panel-watch" role="tabpanel" aria-labelledby={panelLabelledBy} tabIndex={0} className="mt-6 space-y-8 focus:outline-none">
                <section className="space-y-3">
                  <h2 className="section-heading">Streaming</h2>
                  <StreamingPanel movieId={movie.id} />
                </section>
                <section className="space-y-3">
                  <h2 className="section-heading">If you liked this</h2>
                  <RecommendationsPanel movieId={movie.id} />
                </section>
              </div>
            ) : null}
          </section>

          <aside className="min-w-0 space-y-4" aria-label="Personal film tools">
            <WatchPanel movieId={movie.id} />
            {/* Batch T8a. Anyone's, on the film: its real title is what eBay is searched for. */}
            {movie.identified ? <PriceAlertPanel movieId={movie.id} title={movie.title} /> : null}
            {/* Admin-only: `GET /admin/audit` is, so a viewer would only watch it fail. */}
            {isAdmin ? <ItemHistory movieId={movie.id} /> : null}
          </aside>
        </div>
      </div>

      {editing ? (
        <CopyEditor movieId={movie.id} copy={editing} isAdmin={isAdmin} onClose={() => setEditing(null)} />
      ) : null}
    </div>
  )
}
