import type { ProgrammeVenue } from '@/lib/cinemas'
import { COVERAGE_LABELS, londonTime, programmeUrl } from '@/lib/cinemas'

export function ProgrammeLink({ href, children }: { href: string; children: React.ReactNode }) {
  const safe = programmeUrl(href)
  return safe ? <a href={safe} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer" className="inline-flex min-h-11 items-center text-sm font-semibold text-primary underline underline-offset-4">{children}</a> : null
}

export function ProgrammeCoverage({ venues, now }: { venues: ProgrammeVenue[]; now: number }) {
  return (
    <details className="archive-panel p-4">
      <summary className="cursor-pointer py-2 font-semibold">Coverage and sources</summary>
      <div className="mt-3 space-y-5">
        {venues.map((venue) => (
          <section key={venue.id} aria-label={`${venue.name} coverage`} className="border-t border-border pt-3">
            <h2 className="font-semibold">{venue.name}</h2>
            <p className="text-sm text-muted-foreground">Source: {venue.source === 'cinematimes' ? 'CinemaTimes' : venue.source}</p>
            <ul className="mt-2 space-y-2 text-sm">
              {venue.coverage.map((day) => (
                <li key={day.localDate}>
                  <p>{day.localDate} · {day.lastSuccessUtc && (now - Date.parse(day.lastSuccessUtc) >= 30 * 3600000 || day.upstreamUtc && now - Date.parse(day.upstreamUtc) >= 36 * 3600000) && day.status !== 'failed' && day.status !== 'notEnabled' ? 'Saved programme is stale' : COVERAGE_LABELS[day.status]}</p>
                  <p className="text-muted-foreground">{day.lastSuccessUtc ? `Checked ${londonTime(day.lastSuccessUtc)}` : 'No successful check recorded'}{day.lastAttemptUtc && day.lastAttemptUtc !== day.lastSuccessUtc ? ` · Attempted ${londonTime(day.lastAttemptUtc)}` : ''}</p>
                  <p className="text-muted-foreground">{day.upstreamUtc ? `Source updated ${londonTime(day.upstreamUtc)}${day.upstreamAge === 'stale' ? ' · stale' : ''}` : 'Source update time unverified'}</p>
                  {day.sourceUpdateLabel ? <p className="text-muted-foreground">Source label: {day.sourceUpdateLabel}</p> : null}
                  {day.error ? <p className="text-destructive">{day.error}</p> : null}
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap gap-x-5"><ProgrammeLink href={venue.sourceUrl}>Source programme</ProgrammeLink><ProgrammeLink href={venue.officialUrl}>Official programme</ProgrammeLink></div>
          </section>
        ))}
        <p className="text-xs text-muted-foreground">Listings are scheduled each morning at 08:00 UTC. Recent dates alone do not establish a New release; Older films includes returning films of any age.</p>
        <p className="text-xs text-muted-foreground">Film metadata uses TMDB. This product uses the TMDB API but is not endorsed or certified by TMDB.</p>
      </div>
    </details>
  )
}
