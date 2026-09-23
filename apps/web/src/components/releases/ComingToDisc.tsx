import { useQuery } from '@tanstack/react-query'
import { Disc3 } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { CalendarEntry } from '@mcu/shared'

import { StatePanel } from '@/components/ui/state-panel'
import { fetchCalendar } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { DISC_WINDOW_DAYS, isPhysical } from '@/lib/releases'
import { cn, formatShortDate } from '@/lib/utils'

function monthHeading(iso: string): string {
  const [year, month] = iso.split('-').map(Number)
  return new Date(year, month - 1, 1).toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })
}

function freshness(refreshedAt: string | null): string {
  if (!refreshedAt) return 'Not refreshed from TMDB yet.'
  const hours = Math.floor((Date.now() - new Date(refreshedAt).getTime()) / 3_600_000)
  if (hours < 1) return 'Updated from TMDB within the hour.'
  if (hours < 24) return `Updated from TMDB ${String(hours)} ${hours === 1 ? 'hour' : 'hours'} ago.`
  return `Updated from TMDB on ${formatShortDate(refreshedAt)}.`
}

function DiscRow({ entry }: { entry: CalendarEntry }) {
  const title = <span className="min-w-0 flex-1 truncate text-sm font-semibold text-foreground">{entry.title}</span>
  return (
    <li className="flex min-h-11 items-center gap-3 py-1.5">
      <span className="w-16 shrink-0 text-sm font-semibold tabular-nums text-foreground">
        {formatShortDate(entry.releaseDate).replace(/ \d{4}$/, '')}
      </span>
      {entry.movieId ? (
        <Link to={`/movies/${entry.movieId}`} className="flex min-w-0 flex-1 hover:text-primary">{title}</Link>
      ) : title}
      <span
        className={cn(
          'inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-[0.6875rem] font-semibold',
          entry.releaseType === '4k_uhd_release'
            ? 'border-primary/40 bg-primary/10 text-primary'
            : 'border-border bg-muted/60 text-muted-foreground',
        )}
      >
        <Disc3 className="h-3 w-3" aria-hidden />
        {entry.typeLabel}
      </span>
    </li>
  )
}

/**
 * The next 4K and Blu-ray releases, from today — Batch T5, snag 9.
 *
 * **Not tied to a month.** Batch S6 drew this from whichever month the calendar was showing,
 * so it was empty unless a disc came out that month. `limit` makes it Home's short version,
 * which hides itself when there is nothing to show.
 */
export function ComingToDisc({ limit }: { limit?: number }) {
  const query = useQuery({
    queryKey: ['calendar', DISC_WINDOW_DAYS],
    queryFn: () => fetchCalendar(DISC_WINDOW_DAYS),
    staleTime: 10 * 60 * 1000,
  })
  const discs = (query.data?.items ?? []).filter(isPhysical)
  const shown = limit ? discs.slice(0, limit) : discs
  const state = listState(query, discs.length === 0)

  if (limit) {
    // Home's version says nothing rather than something empty or broken.
    if (state !== 'ready') return null
    return (
      <section className="space-y-3" aria-labelledby="home-coming-to-disc">
        <div className="flex items-baseline justify-between gap-3">
          <h2 id="home-coming-to-disc" className="section-heading flex items-center gap-2">
            <Disc3 className="h-5 w-5 text-primary" aria-hidden />
            Coming to disc
          </h2>
          <Link to="/calendar" className="text-sm font-semibold text-primary hover:underline">All releases</Link>
        </div>
        <ul className="archive-panel divide-y divide-border px-4">
          {shown.map((entry) => <DiscRow key={entry.id} entry={entry} />)}
        </ul>
      </section>
    )
  }

  const months = new Map<string, CalendarEntry[]>()
  for (const entry of shown) {
    const key = entry.releaseDate.slice(0, 7)
    months.set(key, [...(months.get(key) ?? []), entry])
  }

  return (
    <section className="space-y-3" aria-labelledby="coming-to-disc-heading">
      <h2 id="coming-to-disc-heading" className="section-heading flex items-center gap-2">
        <Disc3 className="h-5 w-5 text-primary" aria-hidden />
        Coming to disc
      </h2>
      {state === 'loading' ? <StatePanel compact tone="loading" title="Looking up disc releases" /> : null}
      {state === 'offline' ? <StatePanel compact tone="offline" title="Disc releases need a connection" /> : null}
      {state === 'error' ? (
        <StatePanel compact tone="error" title="Disc releases are unavailable" description={queryErrorMessage(query.error, 'Could not load the release calendar.')} />
      ) : null}
      {state === 'empty' ? (
        <p className="text-sm text-muted-foreground">No 4K or Blu-ray releases are listed for the next six months yet.</p>
      ) : null}
      {state === 'ready'
        ? [...months.entries()].map(([month, entries]) => (
            <div key={month}>
              <h3 className="px-1 pb-1 text-[0.6875rem] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{monthHeading(`${month}-01`)}</h3>
              <ul className="archive-panel divide-y divide-border px-4">
                {entries.map((entry) => <DiscRow key={entry.id} entry={entry} />)}
              </ul>
            </div>
          ))
        : null}
      {query.data ? (
        <p className="text-xs text-muted-foreground">
          {freshness(query.data.refreshedAt)} Disc dates come from TMDB, where volunteers add them, so some releases
          will be missing.
        </p>
      ) : null}
    </section>
  )
}
