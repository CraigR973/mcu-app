import { useQuery } from '@tanstack/react-query'
import { ChevronDown, Clapperboard, Eye, Info, RefreshCw, Theater } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import { ProgrammeCoverage, ProgrammeLink } from '@/components/cinemas/ProgrammeCoverage'
import { Poster } from '@/components/movies/Poster'
import { Button } from '@/components/ui/button'
import { StatePanel } from '@/components/ui/state-panel'
import { useAuth } from '@/context/auth'
import { useOnlineStatus } from '@/hooks/useOnlineStatus'
import { useProgrammeClock } from '@/hooks/useProgrammeClock'
import { fetchCinemaFilms } from '@/lib/api'
import {
  cinemaFilmPath,
  cinemaSections,
  clock,
  COVERAGE_LABELS,
  dayAndDate,
  listingState,
  londonDate,
  londonTime,
  OFFICIAL_PROGRAMMES,
  programmeDays,
  RELEASE_LABELS,
  runBadge,
  shortDay,
  shortHorizons,
  shortVenueName,
  staleCoverage,
  type CinemaFilms,
  type CinemaFilters,
  type CinemaLine,
  type ProgrammeVenue,
  type ReleaseFilter,
} from '@/lib/cinemas'
import { queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

const RUNS = Object.keys(RELEASE_LABELS) as ReleaseFilter[]
const CHIP = 'touch-target inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-full border px-3 text-sm font-semibold transition-colors'
const CHIP_ON = 'border-primary bg-primary text-primary-foreground'
const CHIP_OFF = 'border-border bg-card text-foreground hover:border-primary/40'

/** The filters, read from the address so a film page's back arrow returns to the same view. */
function readFilters(params: URLSearchParams, data: CinemaFilms | undefined): CinemaFilters {
  const run = params.get('run')
  const day = params.get('day')
  const cinemas = params.getAll('cinema')
  return {
    run: RUNS.includes(run as ReleaseFilter) ? (run as ReleaseFilter) : 'all',
    day: day && /^\d{4}-\d{2}-\d{2}$/.test(day) ? day : null,
    venueIds: cinemas.length === 0 ? null : (data?.venues ?? []).filter((venue) => cinemas.includes(venue.slug)).map((venue) => venue.id),
  }
}

function cinemasLine(line: CinemaLine, venues: Map<string, ProgrammeVenue>): string {
  if (line.venueIds.length > 1) return `${String(line.venueIds.length)} cinemas`
  const venue = venues.get(line.venueIds[0])
  return venue ? shortVenueName(venue) : '1 cinema'
}

function FilmCardContent({ line, venues, today }: { line: CinemaLine; venues: Map<string, ProgrammeVenue>; today: string }) {
  const { card } = line
  const badge = runBadge(line.run, line.runReason)
  return (
    <article aria-label={card.title}>
        <Link to={cinemaFilmPath(card.key)} className="group block rounded-md">
          <div className="relative">
            <Poster path={card.posterPath} title={card.title} size="w185" decorative className="aspect-[2/3] w-full rounded-md border border-border object-cover" />
            {badge ? (
              <span className={cn('absolute bottom-1.5 left-1.5 rounded-sm px-1.5 py-0.5 text-xs font-semibold shadow-sm', badge === 'Rerun' ? 'bg-accent text-accent-foreground' : 'bg-primary text-primary-foreground')}>
                {badge}
              </span>
            ) : null}
            {card.watched ? (
              <span className="absolute right-1.5 top-1.5 inline-flex items-center gap-1 rounded-sm bg-background/90 px-1.5 py-0.5 text-xs font-semibold text-foreground shadow-sm">
                <Eye className="h-3 w-3" aria-hidden />Seen
              </span>
            ) : null}
          </div>
          <h3 className="mt-1.5 line-clamp-2 text-xs font-semibold leading-4 text-foreground group-hover:text-primary">{card.title}</h3>
          <p className="mt-0.5 text-xs leading-4 tabular-nums text-foreground">{shortDay(line.next.day, today)} {clock(line.next.at)}</p>
          <p className="text-xs leading-4 text-muted-foreground">{cinemasLine(line, venues)}</p>
        </Link>
    </article>
  )
}

function FilmCard(props: { line: CinemaLine; venues: Map<string, ProgrammeVenue>; today: string }) {
  return <li><FilmCardContent {...props} /></li>
}

function FilmGrid({ id, title, caption, lines, venues, today }: { id: string; title: string; caption: string; lines: CinemaLine[]; venues: Map<string, ProgrammeVenue>; today: string }) {
  if (lines.length === 0) return null
  return (
    <section aria-labelledby={id} className="space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id={id} className="section-heading">{title}</h2>
        <p className="shrink-0 text-xs text-muted-foreground">{lines.length.toLocaleString('en-GB')} {lines.length === 1 ? 'film' : 'films'}</p>
      </div>
      <p className="-mt-2 text-xs text-muted-foreground">{caption}</p>
      <ul className="grid grid-cols-3 gap-x-3 gap-y-5 sm:grid-cols-4 lg:grid-cols-5">
        {lines.map((line) => <FilmCard key={line.card.key} line={line} venues={venues} today={today} />)}
      </ul>
    </section>
  )
}

function ListingRows({ id, title, caption, icon: Icon, lines, venues, today, isAdmin }: {
  id: string; title: string; caption: string; icon: typeof Clapperboard; lines: CinemaLine[]; venues: Map<string, ProgrammeVenue>; today: string; isAdmin: boolean
}) {
  if (lines.length === 0) return null
  return (
    <section aria-labelledby={id} className="space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id={id} className="section-heading flex items-center gap-2"><Icon className="h-5 w-5 text-primary" aria-hidden />{title}</h2>
        <p className="shrink-0 text-xs text-muted-foreground">{lines.length.toLocaleString('en-GB')}</p>
      </div>
      <p className="-mt-2 text-xs leading-5 text-muted-foreground">{caption}</p>
      <ul className="archive-panel divide-y divide-border overflow-hidden">
        {lines.map((line) => (
          <li key={line.card.key}>
            <article aria-label={line.card.title} className="flex items-center gap-2 pr-3">
              <Link to={cinemaFilmPath(line.card.key)} className="flex min-h-14 min-w-0 flex-1 flex-col justify-center px-4 py-2 hover:bg-muted">
                <span className="truncate text-sm font-semibold text-foreground">{line.card.title}</span>
                <span className="text-xs text-muted-foreground">
                  {listingState(line.card)} · {cinemasLine(line, venues)} · <span className="tabular-nums">{shortDay(line.next.day, today)} {clock(line.next.at)}</span>
                </span>
              </Link>
              {line.card.identityStatus === 'review' && isAdmin ? (
                <Link to="/identify" className="inline-flex min-h-11 shrink-0 items-center text-sm font-semibold text-primary hover:underline">Check which film this is</Link>
              ) : null}
            </article>
          </li>
        ))}
      </ul>
    </section>
  )
}

/** Which cinemas list fewer days than the fortnight: "Coming up" thins out past them. */
function Horizons({ data }: { data: CinemaFilms }) {
  const { to, none } = shortHorizons(data)
  if (to.length === 0 && none.length === 0) return null
  return (
    <section aria-label="How far ahead cinemas list" className="flex gap-3 rounded-md border border-border bg-muted/50 p-3 text-sm">
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
      <div className="min-w-0 space-y-1">
        <p className="font-semibold">Some cinemas list only a few days ahead</p>
        <ul className="space-y-0.5 text-muted-foreground">
          {to.map(({ day, venues }) => (
            <li key={day}>{venues.map(shortVenueName).join(', ')}: listed only to {dayAndDate(day)}</li>
          ))}
          {none.map((venue) => (
            <li key={venue.id}>{shortVenueName(venue)}: no current listing · {COVERAGE_LABELS[venue.coverage[0]?.status ?? 'unavailable'].toLowerCase()}</li>
          ))}
        </ul>
      </div>
    </section>
  )
}

function NewThisWeek({ data, filters, now, venues, today }: { data: CinemaFilms; filters: CinemaFilters; now: number; venues: Map<string, ProgrammeVenue>; today: string }) {
  if (data.newThisWeek === undefined) return <StatePanel tone="empty" title="New this week" description="New this week is not available in this saved programme. Reload when connected." />
  const items = data.newThisWeek.filter((item) => Date.parse(item.recognisedAtUtc) > now - 7 * 86400000 && Date.parse(item.recognisedAtUtc) <= now).filter((item) => filters.run === 'all' || (filters.run === 'olderFilm' ? item.runLabels.includes('Rerun') : filters.run === 'newRelease' ? item.runLabels.some((label) => label === 'First run' || label === 'Preview') : item.runLabels.includes('Unclassified')))
  const lines = cinemaSections({ ...data, films: items.flatMap((item) => item.card ? [item.card] : []) }, filters, now)
  const current = new Map([...lines.thisWeek, ...lines.comingUp].map((line) => [line.card.key, line]))
  const shown = items.filter((item) => current.has(item.key) || ((!item.card || !item.card.slots.some((slot) => slot.startsAtUtc.some((at) => Date.parse(at) > now))) && filters.day === null && filters.venueIds === null))
  return (
    <section aria-labelledby="cinema-new-this-week" className="space-y-3">
      <h2 id="cinema-new-this-week" className="section-heading">New this week</h2>
      <p className="text-sm text-muted-foreground">New programme arrivals and returns after 30 days, added here in the past seven days. Delayed matches show when they were first listed.</p>
      {shown.length === 0 ? <StatePanel tone="empty" title={filters.run === 'olderFilm' ? 'No newly listed older films this week.' : 'No new films at your cinemas this week.'} description="New films appear after the daily programme check. Unmatched listings and incomplete programmes may hold other films." /> : null}
      <ul className="grid grid-cols-3 gap-x-3 gap-y-5 sm:grid-cols-4 lg:grid-cols-5">
        {shown.map((item) => {
          const line = current.get(item.key)
          const extraLabels = item.runLabels.filter((label) => label !== (line ? runBadge(line.run, line.runReason) : null))
          return <li key={item.key} className="space-y-1">
            {line ? <FilmCardContent line={line} venues={venues} today={today} /> : <><p className="text-sm font-semibold">{item.title}</p><p className="text-xs text-muted-foreground">No remaining showings in the saved programme.</p></>}
            {extraLabels.length ? <p className="text-xs text-muted-foreground">{extraLabels.join(' · ')}</p> : null}
            {item.isReturn ? <p className="text-xs font-semibold">Back in the programme</p> : null}
            {londonDate(Date.parse(item.firstListedAtUtc)) !== londonDate(Date.parse(item.recognisedAtUtc)) ? <p className="text-xs text-muted-foreground">First listed {dayAndDate(londonDate(Date.parse(item.firstListedAtUtc)))} · Matched {dayAndDate(londonDate(Date.parse(item.recognisedAtUtc)))}</p> : null}
          </li>
        })}
      </ul>
    </section>
  )
}

/**
 * Movie night's At the cinema view — AC4 (#335, point 3). Film first: what is on this week and
 * what is coming up at the nine, each film once with its poster, run, cinemas and next showing;
 * a film opens its page of every showing. Listings not matched to a film yet, and events, follow
 * as their cinemas list them. The run, day and cinemas filter one saved read, so a filter answers
 * at once and still works offline.
 */
export function AtTheCinema() {
  const { profile } = useAuth()
  const online = useOnlineStatus()
  const [now, tick] = useProgrammeClock()
  const [params, setParams] = useSearchParams()
  // The person is in the key, so another person's watch marks are never drawn (AB7).
  const query = useQuery({ queryKey: ['cinema-films', profile?.id], queryFn: fetchCinemaFilms, enabled: Boolean(profile) })
  const data = query.data
  const newOnly = params.get('view') === 'new-this-week'
  const filters = readFilters(params, data)
  const today = londonDate(now)
  const venues = data?.venues ?? []
  const venueMap = new Map(venues.map((venue) => [venue.id, venue]))
  const selected = venues.filter((venue) => filters.venueIds === null || filters.venueIds.includes(venue.id))
  const days = data ? programmeDays(data, now) : []
  const sections = data && selected.length > 0 ? cinemaSections(data, filters, now) : null
  const nothing = sections !== null && sections.thisWeek.length + sections.comingUp.length + sections.listings.length + sections.events.length === 0

  function update(change: (next: URLSearchParams) => void) {
    setParams((current) => {
      const next = new URLSearchParams(current)
      change(next)
      return next
    }, { replace: true })
  }
  function setRun(run: ReleaseFilter) {
    update((next) => (run === 'all' ? next.delete('run') : next.set('run', run)))
  }
  function setDay(day: string | null) {
    update((next) => (day === null ? next.delete('day') : next.set('day', day)))
  }
  function toggleVenue(venue: ProgrammeVenue) {
    const current = filters.venueIds ?? venues.map((item) => item.id)
    const chosen = current.includes(venue.id) ? current.filter((id) => id !== venue.id) : [...current, venue.id]
    update((next) => {
      next.delete('cinema')
      if (chosen.length === venues.length) return
      const slugs = venues.filter((item) => chosen.includes(item.id)).map((item) => item.slug)
      // No cinema at all is a choice too, and says so rather than showing everything.
      for (const slug of slugs.length ? slugs : ['none']) next.append('cinema', slug)
    })
  }

  return (
    <section aria-label="At the cinema" className="space-y-6">
      {data ? (
        <div className="space-y-3" aria-label="Filters" role="group">
          <div role="group" aria-label="Programme view" className="flex flex-wrap gap-2">
            <button type="button" className={cn(CHIP, !newOnly ? CHIP_ON : CHIP_OFF)} aria-pressed={!newOnly} onClick={() => update((next) => next.delete('view'))}>All films</button>
            <button type="button" className={cn(CHIP, newOnly ? CHIP_ON : CHIP_OFF)} aria-pressed={newOnly} onClick={() => update((next) => next.set('view', 'new-this-week'))}>New this week</button>
          </div>
          <div role="group" aria-label="Run" className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0">
            {RUNS.map((run) => (
              <button key={run} type="button" aria-pressed={filters.run === run} onClick={() => setRun(run)} className={cn(CHIP, filters.run === run ? CHIP_ON : CHIP_OFF)}>
                {RELEASE_LABELS[run]}
                <span className={cn('tabular-nums', filters.run === run ? 'text-primary-foreground/80' : 'text-muted-foreground')}>{sections ? sections.counts[run] : '…'}</span>
              </button>
            ))}
          </div>
          <div role="group" aria-label="Day" className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0">
            <button type="button" aria-pressed={filters.day === null} onClick={() => setDay(null)} className={cn(CHIP, filters.day === null ? CHIP_ON : CHIP_OFF)}>Any day</button>
            {days.map((day) => (
              <button key={day} type="button" aria-pressed={filters.day === day} aria-label={dayAndDate(day)} onClick={() => setDay(day)} className={cn(CHIP, filters.day === day ? CHIP_ON : CHIP_OFF)}>
                {shortDay(day, today)}
              </button>
            ))}
          </div>
          <details className="group">
            <summary className={cn(CHIP, filters.venueIds === null ? CHIP_OFF : 'border-primary/60 bg-primary/10 text-foreground', 'cursor-pointer list-none [&::-webkit-details-marker]:hidden')}>
              Cinemas · {filters.venueIds === null ? 'all nine' : `${String(filters.venueIds.length)} of ${String(venues.length)}`}
              <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" aria-hidden />
            </summary>
            <fieldset className="mt-2 rounded-md border border-border bg-card px-3 py-1">
              <legend className="sr-only">Cinemas</legend>
              <div className="grid gap-x-4 sm:grid-cols-2">
                {venues.map((venue) => (
                  <label key={venue.id} className="flex min-h-11 items-center gap-2 text-sm">
                    <input type="checkbox" checked={filters.venueIds === null || filters.venueIds.includes(venue.id)} onChange={() => toggleVenue(venue)} className="h-4 w-4 accent-primary" />
                    {venue.name}
                  </label>
                ))}
              </div>
            </fieldset>
          </details>
        </div>
      ) : null}

      {!online ? <p role="status" className="rounded-md border border-border bg-muted p-3 text-sm">Offline · saved programme only. Ticket links are paused; use an official programme when connected.</p> : null}
      {query.isError ? <StatePanel tone="error" title="Programme view could not be refreshed" description={queryErrorMessage(query.error, 'Try again when connected. Saved data may be out of date.')} /> : null}
      {!data && (query.isError || !online) ? (
        <section className="archive-panel p-4" aria-label="Official cinema programmes">
          <h2 className="font-semibold">Official cinema programmes</h2>
          <div className="grid gap-x-4 sm:grid-cols-2">{OFFICIAL_PROGRAMMES.map(([name, href]) => <ProgrammeLink key={href} href={href}>{name}</ProgrammeLink>)}</div>
        </section>
      ) : null}
      {!data && !query.isError ? <StatePanel tone={online ? 'loading' : 'offline'} title={online ? 'Loading cinema programmes' : 'No saved programme'} /> : null}

      {data ? (
        <>
          {selected.length === 0 ? <p role="alert" className="text-sm text-destructive">Select at least one cinema.</p> : null}
          {nothing && !newOnly ? (
            <StatePanel
              tone="empty"
              title={filters.run === 'all' ? 'Nothing listed for this choice' : filters.run === 'unclassified' ? 'No unclassified showings' : `No ${RELEASE_LABELS[filters.run].toLowerCase()} listed`}
              description="Try another day, run or cinema. Unchecked programmes may hold other films; coverage is below."
            />
          ) : null}
          {newOnly ? <NewThisWeek data={data} filters={filters} now={now} venues={venueMap} today={today} /> : null}
          {sections && !newOnly ? (
            <>
              {/* One day picked is one grid of that day's films; otherwise this week, then later. */}
              <FilmGrid
                id="cinema-this-week"
                title={filters.day ? dayAndDate(filters.day) : 'This week'}
                caption={filters.day ? 'Films showing this day.' : `Showing from today to ${dayAndDate(data.thisWeekTo)}.`}
                lines={filters.day ? [...sections.thisWeek, ...sections.comingUp] : sections.thisWeek}
                venues={venueMap}
                today={today}
              />
              {/* Before "Coming up", which thins out past the cinemas that list only a few days. */}
              <Horizons data={data} />
              {filters.day ? null : (
                <FilmGrid id="cinema-coming-up" title="Coming up" caption="Opening after this week, as far as the cinemas list." lines={sections.comingUp} venues={venueMap} today={today} />
              )}
              <ListingRows
                id="cinema-listings"
                title="Not matched to a film yet"
                caption="Each cinema chain’s own listing until it is matched to one film, so a film can appear more than once. Matching runs each morning."
                icon={Clapperboard}
                lines={sections.listings}
                venues={venueMap}
                today={today}
                isAdmin={profile?.role === 'admin'}
              />
              <ListingRows id="cinema-events" title="Events and double bills" caption="Live and staged events, and two films for one ticket." icon={Theater} lines={sections.events} venues={venueMap} today={today} isAdmin={profile?.role === 'admin'} />
            </>
          ) : null}
          {sections === null ? <Horizons data={data} /> : null}
          {!data.complete || staleCoverage(selected, now) ? (
            <div className="space-y-2 text-sm text-muted-foreground">
              {!data.complete ? <p>Partial coverage: some dates or cinemas are not fully checked. Missing listings do not mean nothing is showing.</p> : null}
              {staleCoverage(selected, now) ? <p role="status">Some saved programmes are stale or their latest check failed. Ticket links are paused for the dates affected; check the official programmes.</p> : null}
            </div>
          ) : null}
          <ProgrammeCoverage venues={selected} now={now} />
          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            <span>Saved {londonTime(data.generatedAtUtc)}</span>
            <Button variant="outline" size="sm" aria-label="Reload view" onClick={() => { tick(); void query.refetch() }} disabled={!online || query.isFetching}>
              <RefreshCw className={cn('mr-1 h-3.5 w-3.5', query.isFetching && 'animate-spin')} aria-hidden />Reload
            </Button>
          </div>
        </>
      ) : null}
    </section>
  )
}
