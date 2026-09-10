import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Loader2,
  RefreshCw,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import type { CalendarEntry } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import { useAuth } from '@/context/auth'
import {
  calendarFeedUrl,
  fetchCalendarMonth,
  ingestCalendar,
  posterUrl,
  subscribeToCalendar,
  webcalUrl,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

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

function Entry({ entry }: { entry: CalendarEntry }) {
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
        <p className="mt-0.5 text-[11px] text-muted-foreground">{entry.typeLabel}</p>
      </div>
    </div>
  )
  return (
    <li className="py-1.5 first:pt-0 last:pb-0">
      {entry.movieId ? (
        <Link to={`/movies/${entry.movieId}`} className="-mx-2 block rounded-md px-2 hover:bg-muted/60">
          {body}
        </Link>
      ) : (
        body
      )}
    </li>
  )
}

/**
 * §7.4's subscribe control.
 *
 * **The URL is shown once and rotating is the only recovery.** The token is hashed at
 * rest, so nothing — not this app, not the database — can show it again. Subscribing a
 * second time revokes the first link, which the copy says plainly: someone who has pasted
 * the link somewhere they regret needs to know that pressing the button again is the fix,
 * and someone who has not needs to know that pressing it breaks their calendar.
 */
function SubscribePanel() {
  const [copied, setCopied] = useState(false)
  const [copyError, setCopyError] = useState(false)

  const subscribe = useMutation({
    mutationFn: subscribeToCalendar,
    onSuccess: () => setCopied(false),
  })
  const url = subscribe.data ? calendarFeedUrl(subscribe.data.path) : null

  async function copy() {
    if (!url) return
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setCopyError(false)
    } catch {
      // Clipboard access can be refused, and the URL is on screen to select by hand.
      setCopied(false)
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
        A private link your calendar app can follow. Anyone with it can read this
        calendar&rsquo;s release dates &mdash; nothing about your collection, watches or
        account. Generating a new link stops the old one working.
      </p>

      {url ? (
        <div className="space-y-2">
          <code className="block break-all rounded-md border border-border bg-surface-sunken px-3 py-2 text-xs leading-5 text-foreground">
            {url}
          </code>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="outline" onClick={() => void copy()}>
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              {copied ? 'Copied' : 'Copy link'}
            </Button>
            <a
              href={webcalUrl(url)}
              className="touch-target inline-flex min-h-11 items-center gap-2 rounded-md border border-input px-3 py-2 text-sm font-semibold text-foreground hover:bg-muted"
            >
              <CalendarDays className="h-4 w-4" aria-hidden />
              Open in Calendar
            </a>
          </div>
          <p className="text-[11px] text-muted-foreground">
            {subscribe.data?.replacedPrevious
              ? 'Your previous link has stopped working.'
              : 'This is the only time the link is shown — copy it now.'}
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
          disabled={subscribe.isPending}
          onClick={() => subscribe.mutate()}
        >
          {subscribe.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Get my calendar link
        </Button>
      )}

      {subscribe.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {queryErrorMessage(subscribe.error, 'Could not create a link.')}
        </p>
      ) : null}
    </section>
  )
}

/** §7.4's monthly calendar view, and §7.3's ingestion control for an admin. */
export default function CalendarPage() {
  const { profile } = useAuth()
  const queryClient = useQueryClient()
  const [month, setMonth] = useState(() => monthKey(new Date()))

  const monthQuery = useQuery({
    queryKey: ['calendar-month', month],
    queryFn: () => fetchCalendarMonth(month),
  })
  const days = monthQuery.data?.days ?? {}
  const state = listState(monthQuery, Object.keys(days).length === 0)

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
        title="Release calendar"
        description="Forthcoming cinema and home-media dates in the genres this collection leans on."
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

      <div className="archive-panel flex items-center justify-between gap-2 p-2 sm:p-3">
        <Button
          type="button"
          size="icon"
          variant="ghost"
          aria-label="Previous month"
          onClick={() => setMonth((current) => shift(current, -1))}
        >
          <ChevronLeft className="h-4 w-4" aria-hidden />
        </Button>
        <h2 className="font-display text-xl font-semibold text-foreground" aria-live="polite">{monthLabel(month)}</h2>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          aria-label="Next month"
          onClick={() => setMonth((current) => shift(current, 1))}
        >
          <ChevronRight className="h-4 w-4" aria-hidden />
        </Button>
      </div>

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
        <StatePanel tone="empty" icon={CalendarDays} title="Nothing is scheduled this month" description="Move to another month to continue browsing the release programme." />
      ) : (
        <ul className="space-y-4">
          {Object.entries(days)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([day, entries]) => (
              <li key={day} className="archive-panel grid gap-3 p-4 sm:grid-cols-[9rem_minmax(0,1fr)] sm:p-5">
                <p className="font-display text-lg font-semibold text-foreground">
                  {new Date(`${day}T00:00:00`).toLocaleDateString(undefined, {
                    weekday: 'long',
                    day: 'numeric',
                    month: 'short',
                  })}
                </p>
                <ul className="divide-y divide-border">
                  {entries.map((entry) => (
                    <Entry key={entry.id} entry={entry} />
                  ))}
                </ul>
              </li>
            ))}
        </ul>
      )}

      <SubscribePanel />
    </div>
  )
}
