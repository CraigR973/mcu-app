import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '@/context/auth'
import { useOnlineStatus } from '@/hooks/useOnlineStatus'
import { fetchCinemaProgramme } from '@/lib/api'
import { londonDate, londonTime, OFFICIAL_PROGRAMMES, RELEASE_LABELS, shiftDate, showingBooking, type ProgrammeVenue, type ReleaseFilter } from '@/lib/cinemas'
import { queryErrorMessage } from '@/lib/query-state'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import { Button } from '@/components/ui/button'
import { ProgrammeCoverage, ProgrammeLink } from '@/components/cinemas/ProgrammeCoverage'

const FILTERS = Object.keys(RELEASE_LABELS) as ReleaseFilter[]

export default function CinemasPage() {
  const { profile } = useAuth()
  const online = useOnlineStatus()
  const [now, setNow] = useState(Date.now)
  const [from, setFrom] = useState(londonDate)
  const [to, setTo] = useState(londonDate)
  const [venueIds, setVenueIds] = useState<string[] | null>(null)
  const [category, setCategory] = useState<ReleaseFilter>('all')
  useEffect(() => {
    const tick = () => setNow(Date.now())
    const timer = window.setInterval(tick, 30_000)
    window.addEventListener('focus', tick)
    window.addEventListener('online', tick)
    window.addEventListener('offline', tick)
    return () => { window.clearInterval(timer); window.removeEventListener('focus', tick); window.removeEventListener('online', tick); window.removeEventListener('offline', tick) }
  }, [])
  const validDates = Boolean(from && to && from <= to && (Date.parse(to) - Date.parse(from)) / 86400000 < 14)
  const validVenues = venueIds === null || venueIds.length > 0
  const query = useQuery({
    queryKey: ['cinema-programme', profile?.id, from, to, venueIds, category],
    queryFn: () => fetchCinemaProgramme({ dateFrom: from, dateTo: to, venueIds, releaseCategory: category }),
    enabled: Boolean(profile) && validDates && validVenues,
    placeholderData: (previous, previousQuery) => previousQuery?.queryKey[1] === profile?.id ? previous : undefined,
  })
  const data = query.data
  const ready = data && !query.isPlaceholderData && validDates && validVenues
  const venues = data?.venues ?? []
  const selected = venues.filter((venue) => venueIds === null || venueIds.includes(venue.id))
  const venueMap = new Map(venues.map((venue) => [venue.id, venue]))
  function toggleVenue(venue: ProgrammeVenue) {
    const current = venueIds ?? venues.map((item) => item.id)
    setVenueIds(current.includes(venue.id) ? current.filter((id) => id !== venue.id) : [...current, venue.id].sort())
  }
  const counts = ready ? data.categoryCounts : null
  const total = counts ? counts.newRelease + counts.olderFilm + counts.unclassified : null
  const connected = online && !query.isError && !query.isPlaceholderData
  const hasFailedOrStaleCoverage = selected.some((venue) => venue.coverage.some((day) => day.status === 'failed' || day.status === 'stale' || day.lastSuccessUtc && now - Date.parse(day.lastSuccessUtc) >= 30 * 3600000 || day.upstreamUtc && now - Date.parse(day.upstreamUtc) >= 36 * 3600000))
  return (
    <div className="page-shell-narrow space-y-5">
      <PageHeader title="Cinemas" eyebrow="Plan a screening" description="Films and events at your cinemas, with source coverage and checked times." />
      <p className="text-sm text-muted-foreground">Stored listings · UK times. Check tickets with the cinema.</p>
      <section className="archive-panel space-y-4 p-4" aria-label="Programme filters">
        <div className="grid grid-cols-2 gap-3">
          <label className="min-w-0 text-sm font-semibold">From date<input type="date" value={from} onChange={(event) => setFrom(event.target.value)} className="mt-1 block min-h-11 w-full min-w-0 rounded-md border border-input bg-background px-2 text-base" /></label>
          <label className="min-w-0 text-sm font-semibold">To date<input type="date" value={to} onChange={(event) => setTo(event.target.value)} className="mt-1 block min-h-11 w-full min-w-0 rounded-md border border-input bg-background px-2 text-base" /></label>
        </div>
        <div className="flex gap-2"><Button variant="outline" onClick={() => { const day = londonDate(); setFrom(day); setTo(day) }}>Today</Button><Button variant="outline" onClick={() => { const day = shiftDate(londonDate(), 1); setFrom(day); setTo(day) }}>Tomorrow</Button><Button variant="outline" aria-label="Reload view" onClick={() => { setNow(Date.now()); void query.refetch() }} disabled={!online || !validDates || !validVenues || query.isFetching}>Reload</Button></div>
        {!validDates ? <p role="alert" className="text-sm text-destructive">Select one to fourteen dates, with the end on or after the start.</p> : null}
        <details><summary className="cursor-pointer py-2 text-sm font-semibold">Choose cinemas ({venueIds?.length ?? venues.length} selected)</summary><fieldset><legend className="sr-only">Cinemas</legend><div className="grid gap-x-4 sm:grid-cols-2">
          {venues.map((venue) => <label key={venue.id} className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={venueIds === null || venueIds.includes(venue.id)} onChange={() => toggleVenue(venue)} className="h-4 w-4 accent-primary" />{venue.name}</label>)}
        </div></fieldset></details>
        {!validVenues ? <p role="alert" className="text-sm text-destructive">Select at least one cinema.</p> : null}
        <label className="block text-sm font-semibold">Release category<select value={category} onChange={(event) => setCategory(event.target.value as ReleaseFilter)} className="mt-1 block min-h-11 w-full rounded-md border border-input bg-background px-3 text-base">{FILTERS.map((value) => <option key={value} value={value}>{RELEASE_LABELS[value]} ({counts ? value === 'all' ? total : counts[value] : '…'} {counts && (value === 'all' ? total : counts[value]) === 1 ? 'screening' : 'screenings'})</option>)}</select></label>
      </section>
      {!online ? <p role="status" className="rounded-md border border-border bg-muted p-3 text-sm">Offline · saved programme only. Showing booking links are paused; use an official programme when connected.</p> : null}
      {query.isError ? <StatePanel tone="error" title="Programme view could not be refreshed" description={queryErrorMessage(query.error, 'Try again when connected. Saved data may be out of date.')} /> : null}
      {!data && (query.isError || !online) ? <section className="archive-panel p-4" aria-label="Official cinema programmes"><h2 className="font-semibold">Official cinema programmes</h2><div className="grid gap-x-4 sm:grid-cols-2">{OFFICIAL_PROGRAMMES.map(([name, href]) => <ProgrammeLink key={href} href={href}>{name}</ProgrammeLink>)}</div></section> : null}
      {!ready && !query.isError && validDates && validVenues ? <StatePanel tone={online ? 'loading' : 'offline'} title={online ? 'Loading cinema programmes' : 'No saved programme for this selection'} /> : null}
      {ready ? <>
        <p role="status" className="text-sm text-muted-foreground">{data.returnedShowingCount.toLocaleString('en-GB')} {data.returnedShowingCount === 1 ? 'screening' : 'screenings'} · {data.films.length.toLocaleString('en-GB')} {data.films.length === 1 ? 'programme group' : 'programme groups'} · snapshot {londonTime(data.generatedAtUtc)}</p>
        {!data.selectionComplete ? <p className="rounded-md border border-border bg-muted p-3 text-sm">Partial coverage: some dates or cinemas are not fully checked. Missing listings do not mean nothing is showing.</p> : null}
        {hasFailedOrStaleCoverage ? <p role="status" className="rounded-md border border-border bg-muted p-3 text-sm">Some saved programmes are stale or their latest check failed. Showing ticket links are paused for affected dates; check the official programmes.</p> : null}
        {data.truncated ? <p role="alert" className="text-sm font-semibold text-destructive">Programme limited to 2,000 screenings. Narrow your date or venue selection.</p> : null}
        {counts && counts.unclassified > 0 ? <p className="text-sm text-muted-foreground">Across all categories: {counts.unclassified.toLocaleString('en-GB')} {counts.unclassified === 1 ? 'screening has' : 'screenings have'} an unverified release run.</p> : null}
        <ProgrammeCoverage venues={selected} now={now} />
        {data.films.length === 0 ? <StatePanel tone="empty" title={category === 'all' ? 'No listings returned for this selection' : category === 'unclassified' ? 'No unclassified screenings found' : `No verified ${RELEASE_LABELS[category].toLowerCase()} found`} description={category === 'unclassified' ? 'Try All films to see the other categories. Coverage above still applies.' : 'Try another category or date. Unclassified and unchecked programmes may contain other films.'} /> : null}
        <div className="space-y-4">
          {data.films.map((film) => <article key={film.id} aria-label={film.title} className="archive-panel p-4">
            <h2 className="font-display text-xl font-semibold">{film.movieId && film.identityStatus === 'verified' ? <Link to={`/movies/${film.movieId}`} className="hover:underline">{film.title}</Link> : film.title}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{film.yearConfidence === 'verified' && film.originalYear !== null ? `Original year ${film.originalYear}` : 'Year unverified'} · {film.identityStatus === 'verified' ? 'Identity verified' : film.identityStatus === 'conflict' ? 'Programme title differs — check cinema' : 'Identity unverified · possible duplicate programme'}</p>
            {film.owned !== null || film.watched !== null ? <p className="mt-1 text-sm">{film.owned === true ? 'In the collection' : film.owned === false ? 'Not in the collection' : 'Collection match unverified'} · {film.watched === true ? 'You have watched this' : film.watched === false ? 'You have not watched this' : 'Your watch status unverified'}</p> : null}
            <ul className="mt-3 divide-y divide-border">
              {film.showings.map((showing) => {
                const venue = venueMap.get(showing.venueId)
                if (!venue) return null
                const booking = showingBooking(showing, venue, now, connected)
                return <li key={showing.id} className="space-y-1 py-3">
                  <p className="font-semibold">{venue.name} · {londonTime(showing.startsAtUtc)}</p>
                  {showing.sourceTitle !== film.title ? <p className="text-sm text-muted-foreground">Programme title: {showing.sourceTitle}</p> : null}
                  <p className="text-sm">{RELEASE_LABELS[showing.releaseCategory]}{showing.reissue ? ' · Reissue' : ''}{showing.screen ? ` · ${showing.screen}` : ''}{showing.formats.length ? ` · ${showing.formats.join(', ')}` : ''}</p>
                  {showing.sourceReleaseDate ? <p className="text-xs text-muted-foreground">Source release date: {showing.sourceReleaseDate} · original year shown separately above</p> : null}
                  <p className="text-xs text-muted-foreground">Seen {londonTime(showing.lastSeenUtc)} · {showing.upstreamAge === 'unknown' ? 'Source update time unverified' : `Source age ${showing.upstreamAge}`}{showing.confirmation === 'unconfirmed' ? ' · Showing unconfirmed' : ''}</p>
                  {showing.observationStale || now - Date.parse(showing.lastSeenUtc) >= 30 * 60 * 60 * 1000 ? <p className="text-sm text-muted-foreground">Saved showing is stale</p> : null}
                  {showing.releaseCategory !== 'unclassified' ? <p className="text-xs text-muted-foreground">{showing.categoryEvidence.description}</p> : null}
                  <div className="flex flex-wrap items-center gap-x-5">{booking ? <a href={booking} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer" className="inline-flex min-h-11 items-center rounded-md bg-primary px-3 text-sm font-semibold text-primary-foreground" onClick={(event) => { if (!showingBooking(showing, venue, Date.now(), online && !query.isError)) { event.preventDefault(); setNow(Date.now()) } }}>Check tickets</a> : <span className="text-sm text-muted-foreground">Showing booking unconfirmed or unavailable</span>}<ProgrammeLink href={venue.officialUrl}>Official programme</ProgrammeLink></div>
                </li>
              })}
            </ul>
          </article>)}
        </div>
      </> : null}
    </div>
  )
}
