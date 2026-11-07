import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Clapperboard,
  Copy,
  Disc3,
  Loader2,
  RefreshCw,
  Sparkle,
} from 'lucide-react'
import { Link, NavLink, useSearchParams } from 'react-router-dom'
import type { CalendarEntry, CalendarSubscription } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import { useAuth } from '@/context/auth'
import {
  calendarFeedUrl,
  ingestCalendar,
  posterUrl,
  subscribeToCalendar,
  webcalUrl,
} from '@/lib/api'
import { cinemaFilmPath } from '@/lib/cinemas'
import { cn, formatWeekdayDate } from '@/lib/utils'
import { ComingToDisc } from '@/components/releases/ComingToDisc'
import {
  CALENDAR_PATHS,
  CALENDAR_TYPES,
  DISC_FILTERS,
  discFilter,
  isPhysical,
  readMonth,
  showingAtCinemas,
  unmatchedListings,
  type CinemaShowing,
  type ReleaseCalendar,
} from '@/lib/releases'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { useCalendarMonthQuery, useCinemaFilmsQuery, useDiscReleasesQuery, useNewReleasesQuery } from '@/lib/release-queries'

function monthKey(date: Date): string {
  return `${String(date.getFullYear())}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

function monthLabel(key: string): string {
  const [year, month] = key.split('-').map(Number)
  return new Date(year, month - 1, 1).toLocaleDateString(undefined, {
    month: 'long',
    year: 'numeric',
  })
}

function shift(key: string, by: number): string {
  const [year, month] = key.split('-').map(Number)
  return monthKey(new Date(year, month - 1 + by, 1))
}

const VIEW_LINK = 'touch-target inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-3 text-sm font-semibold transition-colors'
const CHIP = 'touch-target inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-full border px-3 text-sm font-semibold transition-colors'
const CHIP_ON = 'border-primary bg-primary text-primary-foreground'
const CHIP_OFF = 'border-border bg-card text-foreground hover:border-primary/40'

/**
 * AC7 (#343): Releases is two calendars, each with its own address, as Movie night is two views.
 * The month goes with the switch, and the switch replaces the address rather than adding to
 * history, as tabs do, so the back arrow leaves Releases instead of flipping between them.
 */
function Views({ month }: { month: string | null }) {
  const search = month ? `?month=${month}` : ''
  const link = ({ isActive }: { isActive: boolean }) =>
    cn(VIEW_LINK, isActive ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')
  return (
    <nav aria-label="Release calendars" className="grid grid-cols-2 gap-1 rounded-lg bg-muted p-1">
      <NavLink to={{ pathname: CALENDAR_PATHS.disc, search }} end replace className={link}>
        <Disc3 className="h-4 w-4" aria-hidden />Disc releases
      </NavLink>
      <NavLink to={{ pathname: CALENDAR_PATHS.cinema, search }} replace className={link}>
        <Clapperboard className="h-4 w-4" aria-hidden />Cinema releases
      </NavLink>
    </nav>
  )
}

function Entry({ entry, calendar, showing }: { entry: CalendarEntry; calendar: ReleaseCalendar; showing?: CinemaShowing }) {
  const physical = isPhysical(entry)
  // A cinema release showing at one of the nine opens its showings; otherwise a film the
  // collection holds opens its archive page, as every entry always has.
  const to = showing ? cinemaFilmPath(showing.key) : entry.movieId ? `/movies/${entry.movieId}` : null
  const body = (
    <div className="flex min-h-12 items-center gap-3">
      {entry.posterPath ? (
        <img
          src={posterUrl(entry.posterPath, 'w92')}
          alt=""
          loading="lazy"
          className="h-12 w-8 shrink-0 rounded-sm border border-border object-cover"
        />
      ) : null}
      <div className="min-w-0">
        <p className="line-clamp-2 text-sm font-semibold leading-5 text-foreground">{entry.title}</p>
        {/* Batch S6 kept disc dates visibly distinct from cinema dates in one list; since AC7
            each calendar holds one kind, so the disc chip names the format or the sale, and a
            cinema release says where it is showing instead of "In cinemas" on every row. */}
        {calendar === 'disc' ? (
          <p className="mt-1">
            <span
              className={cn(
                'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold',
                physical
                  ? 'border-primary/40 bg-primary/10 text-primary'
                  : 'border-border bg-muted/60 text-muted-foreground',
              )}
            >
              {physical ? <Disc3 className="h-3 w-3" aria-hidden /> : null}
              {entry.typeLabel}
            </span>
          </p>
        ) : showing ? (
          <p className="mt-1">
            <span className="inline-flex items-center gap-1 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
              <Clapperboard className="h-3 w-3" aria-hidden />
              {showing.venues === 1 ? 'At one of your cinemas' : `At ${String(showing.venues)} of your cinemas`}
            </span>
          </p>
        ) : null}
      </div>
    </div>
  )
  return (
    <li className="py-1.5 first:pt-0 last:pb-0">
      {to ? (
        <Link to={to} className="-mx-2 block rounded-md px-2 hover:bg-muted/60">
          {body}
        </Link>
      ) : (
        body
      )}
    </li>
  )
}

/**
 * One calendar's month — §7.4's monthly view, one per calendar since AC7.
 *
 * It asks the API for its own types (#344), and keeps only those on the device too, so a month
 * cached before AC7, or an API not yet deployed, cannot put cinema dates among the discs. The
 * month and the disc filter live in the address, so a film's page comes back to the same view.
 */
function MonthView({ calendar, month, onMonth }: { calendar: ReleaseCalendar; month: string; onMonth: (month: string) => void }) {
  const [params, setParams] = useSearchParams()
  const [now] = useState(Date.now)
  const types = CALENDAR_TYPES[calendar]

  const monthQuery = useCalendarMonthQuery(month, calendar)
  // The cinema calendar reads which releases are showing from AC4's own read, shared with At
  // the cinema and Home, so opening one after another costs nothing more.
  const cinemaQuery = useCinemaFilmsQuery(calendar === 'cinema')
  const showing = calendar === 'cinema' ? showingAtCinemas(cinemaQuery.data, now) : new Map<number, CinemaShowing>()

  const held = Object.entries(monthQuery.data?.days ?? {})
    .map(([day, entries]) => [day, entries.filter((entry) => types.includes(entry.releaseType))] as const)
    .filter(([, entries]) => entries.length > 0)
    .sort(([a], [b]) => a.localeCompare(b))
  const state = listState(monthQuery, held.length === 0)

  const show = calendar === 'disc' ? discFilter(params.get('show')) : 'all'
  const shown = calendar === 'disc' ? (DISC_FILTERS.find((filter) => filter.value === show)?.types ?? types) : types
  const days = held
    .map(([day, entries]) => [day, entries.filter((entry) => shown.includes(entry.releaseType))] as const)
    .filter(([, entries]) => entries.length > 0)
  const count = (filterTypes: readonly string[]) =>
    held.reduce((sum, [, entries]) => sum + entries.filter((entry) => filterTypes.includes(entry.releaseType)).length, 0)

  function setShow(value: string) {
    setParams((current) => {
      const next = new URLSearchParams(current)
      if (value === 'all') next.delete('show')
      else next.set('show', value)
      return next
    }, { replace: true })
  }

  const unmatched = unmatchedListings(cinemaQuery.data, now)
  const filterLabel = DISC_FILTERS.find((filter) => filter.value === show)?.label ?? ''

  return (
    <section className="space-y-4" aria-label={calendar === 'disc' ? 'Disc releases by month' : 'Cinema releases by month'}>
      <div className="archive-panel flex items-center justify-between gap-2 p-2 sm:p-3">
        <Button type="button" size="icon" variant="ghost" aria-label="Previous month" onClick={() => onMonth(shift(month, -1))}>
          <ChevronLeft className="h-4 w-4" aria-hidden />
        </Button>
        <h2 className="font-display text-xl font-semibold text-foreground" aria-live="polite">{monthLabel(month)}</h2>
        <Button type="button" size="icon" variant="ghost" aria-label="Next month" onClick={() => onMonth(shift(month, 1))}>
          <ChevronRight className="h-4 w-4" aria-hidden />
        </Button>
      </div>

      {calendar === 'disc' && state === 'ready' ? (
        <div role="group" aria-label="Show" className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0">
          {DISC_FILTERS.map((filter) => (
            <button
              key={filter.value}
              type="button"
              aria-pressed={show === filter.value}
              onClick={() => setShow(filter.value)}
              className={cn(CHIP, show === filter.value ? CHIP_ON : CHIP_OFF)}
            >
              {filter.label}
              <span className={cn('tabular-nums', show === filter.value ? 'text-primary-foreground/80' : 'text-muted-foreground')}>
                {count(filter.types)}
              </span>
            </button>
          ))}
        </div>
      ) : null}

      {state === 'loading' ? (
        <StatePanel tone="loading" title="Setting the programme" />
      ) : state === 'offline' ? (
        <StatePanel tone="offline" title="This month is not cached here" description="Reconnect to load release dates on this device." />
      ) : state === 'error' ? (
        <StatePanel
          tone="error"
          title="The release calendar is unavailable"
          description={queryErrorMessage(monthQuery.error, 'Could not load the calendar.')}
        />
      ) : state === 'empty' ? (
        <StatePanel
          tone="empty"
          icon={calendar === 'disc' ? Disc3 : Clapperboard}
          title={calendar === 'disc' ? 'No disc releases or sales this month' : 'No cinema releases this month'}
          description="Move to another month to continue browsing the release programme."
        />
      ) : days.length === 0 ? (
        <StatePanel compact tone="empty" icon={Disc3} title={`No ${filterLabel.toLowerCase()} this month`} description="Choose All to see the month’s other dates." />
      ) : (
        <ul className="space-y-4">
          {days.map(([day, entries]) => (
            <li key={day} className="archive-panel grid gap-3 p-4 sm:grid-cols-[9rem_minmax(0,1fr)] sm:p-5">
              <p className="font-display text-lg font-semibold text-foreground">{formatWeekdayDate(day)}</p>
              <ul className="divide-y divide-border">
                {entries.map((entry) => (
                  <Entry
                    key={entry.id}
                    entry={entry}
                    calendar={calendar}
                    showing={entry.tmdbId === null ? undefined : showing.get(entry.tmdbId)}
                  />
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}

      {/* Until AC3's mornings match every listing, some films showing are not one film yet. They
          are said, not guessed at: a title alone never links a release (#327, #342). */}
      {calendar === 'cinema' && state === 'ready' ? (
        <p className="text-xs text-muted-foreground">
          {cinemaQuery.isError
            ? 'Could not check what is showing at your cinemas, so no release opens its showings right now.'
            : cinemaQuery.data
              ? `A release showing at your cinemas opens its showings.${unmatched > 0 ? ` ${String(unmatched)} cinema ${unmatched === 1 ? 'listing is' : 'listings are'} not matched to a film yet; a release among them links once it is. Matching runs each morning.` : ''}`
              : null}
        </p>
      ) : null}
    </section>
  )
}

/**
 * The old `/discover`, TMDB's films coming to cinemas in the genres on the shelves. **Kept whole**
 * since Batch S6, and on the cinema calendar since AC7: it is what makes a film with no date in
 * the calendar still visible. A film showing at one of the nine opens its showings there too.
 */
function ComingSoon() {
  const [now] = useState(Date.now)
  const releasesQuery = useNewReleasesQuery(true)
  const cinemaQuery = useCinemaFilmsQuery(true)
  const showing = showingAtCinemas(cinemaQuery.data, now)
  const comingSoon = releasesQuery.data?.items ?? []
  const state = listState(releasesQuery, comingSoon.length === 0)

  return (
    <section className="space-y-3" aria-labelledby="coming-soon-heading">
      <h2 id="coming-soon-heading" className="section-heading flex items-center gap-2">
        <Sparkle className="h-5 w-5 text-primary" aria-hidden />
        Coming soon
      </h2>
      <p className="-mt-1 text-sm text-muted-foreground">
        Forthcoming releases selected from the genres already represented on your shelves
        {releasesQuery.data && releasesQuery.data.basedOnGenres.length > 0
          ? ` — ${releasesQuery.data.basedOnGenres.join(' · ')}`
          : ''}
        .
      </p>

      {state === 'loading' ? (
        <StatePanel compact tone="loading" title="Looking up cinema releases" />
      ) : state === 'offline' ? (
        <StatePanel compact tone="offline" title="Cinema releases need a connection" />
      ) : state === 'error' ? (
        <StatePanel
          compact
          tone="error"
          title="The release programme is unavailable"
          description={queryErrorMessage(releasesQuery.error, 'Could not load new releases.')}
        />
      ) : state === 'empty' ? (
        <StatePanel
          compact
          tone="empty"
          icon={Sparkle}
          title="Nothing suitable is scheduled"
          description="No forthcoming releases match this collection’s genres right now."
        />
      ) : (
        <ul className="grid grid-cols-2 gap-x-3 gap-y-7 sm:grid-cols-3 sm:gap-x-5 md:grid-cols-4 lg:grid-cols-5">
          {comingSoon.map((item) => {
            const atCinemas = showing.get(item.tmdbId)
            const card = (
              <article className="group space-y-3">
                <div className="relative overflow-hidden rounded-md border border-border bg-muted shadow-soft">
                  <img
                    src={posterUrl(item.posterPath, 'w342')}
                    alt=""
                    loading="lazy"
                    className={cn(
                      'aspect-[2/3] w-full object-cover transition-opacity',
                      item.ownership === 'owned' ? '' : 'opacity-90',
                    )}
                  />
                  {item.ownership === 'owned' ? (
                    <span className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-full border border-success/40 bg-background/95 px-2 py-1 text-xs font-semibold text-success shadow-soft">
                      <Check className="h-3 w-3" aria-hidden />
                      Owned
                    </span>
                  ) : null}
                </div>
                <div>
                  <h3 id={`coming-soon-${String(item.tmdbId)}`} className="line-clamp-2 text-sm font-semibold leading-5 text-foreground group-hover:text-primary" title={item.title}>
                    {item.title}
                  </h3>
                  <p className="mt-1 text-xs tabular-nums text-muted-foreground">
                    {item.releaseDate ?? 'Date to be confirmed'}
                  </p>
                  {atCinemas ? (
                    <p id={`coming-soon-${String(item.tmdbId)}-cinemas`} className="mt-1 flex items-center gap-1 text-xs font-semibold text-primary">
                      <Clapperboard className="h-3 w-3" aria-hidden />
                      {atCinemas.venues === 1 ? 'At one of your cinemas' : `At ${String(atCinemas.venues)} of your cinemas`}
                    </p>
                  ) : null}
                  {item.matchedGenres.length > 0 ? (
                    <p className="mt-1 truncate text-xs text-muted-foreground">
                      {item.matchedGenres.join(' · ')}
                    </p>
                  ) : null}
                </div>
              </article>
            )
            const to = atCinemas ? cinemaFilmPath(atCinemas.key) : item.movieId ? `/movies/${item.movieId}` : null
            return (
              <li key={item.tmdbId}>
                {/* Named by its title (and where it is showing): a browser does not name a link
                    from an article inside it, so the card's link read as "link" alone. */}
                {to ? (
                  <Link
                    to={to}
                    aria-labelledby={atCinemas ? `coming-soon-${String(item.tmdbId)} coming-soon-${String(item.tmdbId)}-cinemas` : `coming-soon-${String(item.tmdbId)}`}
                    className="block rounded-md"
                  >
                    {card}
                  </Link>
                ) : card}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

interface FeedLink {
  name: string
  detail: string
  url: string
}

/** The links one press gave, the calendar on screen first; one link from an API before AC7. */
function feedLinks(data: CalendarSubscription, view: ReleaseCalendar): FeedLink[] {
  const disc = data.discPath ? { name: 'Disc releases', detail: '4K, Blu-ray and sale dates', url: calendarFeedUrl(data.discPath) } : null
  const cinema = data.cinemaPath ? { name: 'Cinema releases', detail: 'UK cinema dates', url: calendarFeedUrl(data.cinemaPath) } : null
  const both = { name: 'Both calendars', detail: 'every date, as the one link did before', url: calendarFeedUrl(data.path) }
  const ordered = view === 'disc' ? [disc, cinema] : [cinema, disc]
  return [...ordered.filter((link): link is FeedLink => link !== null), both]
}

/**
 * §7.4's subscribe control.
 *
 * **The URL is shown once and rotating is the only recovery.** The token is hashed at
 * rest, so nothing — not this app, not the database — can show it again. Subscribing a
 * second time revokes the first link, which the copy says plainly: someone who has pasted
 * the link somewhere they regret needs to know that pressing the button again is the fix,
 * and someone who has not needs to know that pressing it breaks their calendar.
 *
 * **AC7: one press gives a link per calendar and one for both** (#344). They share the one
 * token a person has, so the next press stops all three, the both-calendars link that a
 * calendar app may already follow among them; asking per calendar would have broken the other.
 */
function SubscribePanel({ view, layoutPending }: { view: ReleaseCalendar; layoutPending: boolean }) {
  const [copied, setCopied] = useState<string | null>(null)
  const [copyError, setCopyError] = useState(false)

  const subscribe = useMutation({
    mutationFn: subscribeToCalendar,
    onSuccess: () => setCopied(null),
  })
  const links = subscribe.data ? feedLinks(subscribe.data, view) : []

  async function copy(url: string) {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(url)
      setCopyError(false)
    } catch {
      // Clipboard access can be refused, and the URL is on screen to select by hand.
      setCopied(null)
      setCopyError(true)
    }
  }

  return (
    <section className="archive-panel space-y-4 p-5" aria-labelledby="calendar-subscribe-heading">
      <div>
        <p className="page-kicker">Private feed</p>
        <h2 id="calendar-subscribe-heading" className="section-heading">Subscribe in your calendar</h2>
      </div>
      <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
        Private links your calendar app can follow: one for each calendar, or both together.
        Anyone with a link can read its release dates &mdash; nothing about your collection,
        watches or account. Getting new links stops the old ones working.
      </p>

      {links.length > 0 ? (
        <div className="space-y-2">
          <div className="divide-y divide-border">
            {links.map((link) => {
              const id = `feed-${link.name.toLowerCase().replace(/\W+/g, '-')}`
              return (
                <div key={link.url} role="group" aria-labelledby={id} className="space-y-2 py-3 first:pt-0">
                  <p id={id} className="text-sm font-semibold text-foreground">
                    {link.name}
                    <span className="font-normal text-muted-foreground"> · {link.detail}</span>
                  </p>
                  <code className="block break-all rounded-md border border-border bg-surface-sunken px-3 py-2 text-xs leading-5 text-foreground">
                    {link.url}
                  </code>
                  <div className="flex flex-wrap gap-2">
                    <Button type="button" size="sm" variant="outline" onClick={() => void copy(link.url)}>
                      {copied === link.url ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                      {copied === link.url ? 'Copied' : 'Copy link'}
                    </Button>
                    <a
                      href={webcalUrl(link.url)}
                      className="touch-target inline-flex min-h-11 items-center gap-2 rounded-md border border-input px-3 py-2 text-sm font-semibold text-foreground hover:bg-muted"
                    >
                      <CalendarDays className="h-4 w-4" aria-hidden />
                      Open in Calendar
                    </a>
                  </div>
                </div>
              )
            })}
          </div>
          <p className="text-xs text-muted-foreground">
            {subscribe.data?.replacedPrevious
              ? 'Your previous links have stopped working. A calendar app that followed one needs one of these instead.'
              : 'This is the only time these links are shown — copy the ones you want now.'}
          </p>
          {copyError ? (
            <p role="alert" className="text-sm text-destructive">
              Your browser blocked copying. Select the link above and copy it manually.
            </p>
          ) : null}
        </div>
      ) : (
        <Button
          type="button"
          size="sm"
          disabled={layoutPending || subscribe.isPending}
          aria-busy={layoutPending || subscribe.isPending}
          onClick={() => subscribe.mutate()}
        >
          {layoutPending || subscribe.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
          Get my calendar links
        </Button>
      )}

      {subscribe.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {queryErrorMessage(subscribe.error, 'Could not create the links.')}
        </p>
      ) : null}
    </section>
  )
}

/**
 * Releases — Batch S6's merge of Calendar and Coming soon (snag 2), two calendars since AC7.
 *
 * **Discs and cinemas are two calendars** (#343, the 4 Nov snags' point 5). One list of both
 * had discs outnumbered about six to one on 4 Nov. `/calendar` is Disc releases: Coming to disc,
 * then the month's 4K and Blu-ray releases and sale dates. `/calendar/cinema` is Cinema
 * releases: the month's UK cinema dates, a film showing at one of the nine opening its page
 * under At the cinema, then TMDB's Coming soon. "Refresh from TMDB" is unchanged on both.
 *
 * **Physical releases are few, and the disc calendar says why.** TMDB's UK physical dates are
 * community-maintained, so Coming to disc says how fresh they are and that some are missing,
 * rather than implying that no discs are coming.
 */
export default function ReleasesPage({ view = 'disc' }: { view?: ReleaseCalendar }) {
  const { profile } = useAuth()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const chosen = readMonth(params.get('month'))
  const month = chosen ?? monthKey(new Date())
  const monthQuery = useCalendarMonthQuery(month, view)
  const cinemaQuery = useCinemaFilmsQuery(view === 'cinema')
  const releasesQuery = useNewReleasesQuery(view === 'cinema')
  const discQuery = useDiscReleasesQuery(view === 'disc')
  const layoutQueries = view === 'disc' ? [monthQuery, discQuery] : [monthQuery, cinemaQuery, releasesQuery]
  // A late programme can move the button between pointer-down and pointer-up. Observe
  // shared queries directly, without readiness effects, duplicate fetches or click retries.
  // A terminal error/paused offline read has settled; reconnect/refetch will hold it again.
  const layoutPending = layoutQueries.some(query => query.isFetching || (query.isPending && query.fetchStatus !== 'paused'))

  function setMonth(next: string) {
    setParams((current) => {
      const updated = new URLSearchParams(current)
      updated.set('month', next)
      return updated
    }, { replace: true })
  }

  const ingest = useMutation({
    mutationFn: () => ingestCalendar(false),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['calendar-month'] })
      void queryClient.invalidateQueries({ queryKey: ['calendar'] })
    },
  })

  return (
    <div className="page-shell-narrow space-y-7">
      <PageHeader
        eyebrow="Programme diary"
        title="Releases"
        description={view === 'cinema'
          ? 'UK cinema opening dates, and what is showing at your nine cinemas.'
          : 'What is coming to disc in 4K and on Blu-ray, and the sales worth waiting for.'}
        actions={profile?.role === 'admin' ? (
          <Button
            type="button"
            variant="outline"
            disabled={ingest.isPending}
            onClick={() => ingest.mutate()}
          >
            {ingest.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Refresh from TMDB
          </Button>
        ) : undefined}
      />

      {ingest.isSuccess ? (
        <p role="status" className="rounded-md border border-success/30 bg-success/10 px-4 py-3 text-sm text-foreground">
          {ingest.data.created} new, {ingest.data.updated} moved, {ingest.data.unchanged}{' '}
          unchanged
          {ingest.data.errors.length > 0
            ? `, ${String(ingest.data.errors.length)} failed`
            : ''}
          .
        </p>
      ) : null}
      {ingest.isError ? (
        <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {queryErrorMessage(ingest.error, 'Could not refresh the release calendar.')}
        </p>
      ) : null}

      <Views month={chosen} />

      {view === 'disc' ? (
        <>
          {/* Batch T5, snag 9: the next disc releases from today, whichever month is below. */}
          <ComingToDisc />
          <MonthView calendar="disc" month={month} onMonth={setMonth} />
        </>
      ) : (
        <>
          <MonthView calendar="cinema" month={month} onMonth={setMonth} />
          <ComingSoon />
        </>
      )}

      <SubscribePanel view={view} layoutPending={layoutPending} />
    </div>
  )
}
