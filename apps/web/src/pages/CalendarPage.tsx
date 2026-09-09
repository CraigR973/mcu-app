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
import { cn } from '@/lib/utils'

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
    <div className="flex items-center gap-2">
      {entry.posterPath ? (
        <img
          src={posterUrl(entry.posterPath, 'w92')}
          alt=""
          loading="lazy"
          className="h-10 w-7 shrink-0 rounded object-cover"
        />
      ) : null}
      <div className="min-w-0">
        <p className="truncate text-xs font-medium text-foreground">{entry.title}</p>
        <p className="text-[11px] text-muted-foreground">{entry.typeLabel}</p>
      </div>
    </div>
  )
  return (
    <li>
      {entry.movieId ? (
        <Link to={`/movies/${entry.movieId}`} className="block hover:opacity-80">
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
    } catch {
      // Clipboard access can be refused, and the URL is on screen to select by hand.
      setCopied(false)
    }
  }

  return (
    <div className="space-y-2 rounded-lg border border-border bg-card p-4">
      <h2 className="text-sm font-semibold text-foreground">Subscribe in your calendar</h2>
      <p className="text-xs text-muted-foreground">
        A private link your calendar app can follow. Anyone with it can read this
        calendar&rsquo;s release dates &mdash; nothing about your collection, watches or
        account. Generating a new link stops the old one working.
      </p>

      {url ? (
        <div className="space-y-2">
          <code className="block break-all rounded-md bg-muted px-2 py-1.5 text-[11px] text-foreground">
            {url}
          </code>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="outline" onClick={() => void copy()}>
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              {copied ? 'Copied' : 'Copy link'}
            </Button>
            <a
              href={webcalUrl(url)}
              className="inline-flex items-center gap-1.5 rounded-md border border-input px-2.5 py-1 text-xs font-medium text-foreground hover:bg-muted"
            >
              <CalendarDays className="h-4 w-4" />
              Open in Calendar
            </a>
          </div>
          <p className="text-[11px] text-muted-foreground">
            {subscribe.data?.replacedPrevious
              ? 'Your previous link has stopped working.'
              : 'This is the only time the link is shown — copy it now.'}
          </p>
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
        <p className="text-sm text-destructive">
          {queryErrorMessage(subscribe.error, 'Could not create a link.')}
        </p>
      ) : null}
    </div>
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
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Release calendar</h1>
          <p className="text-sm text-muted-foreground">
            What&rsquo;s coming, in the genres this collection leans on.
          </p>
        </div>
        {profile?.role === 'admin' ? (
          <Button
            type="button"
            size="sm"
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
        ) : null}
      </div>

      {ingest.isSuccess ? (
        <p className="text-sm text-muted-foreground">
          {ingest.data.created} new, {ingest.data.updated} moved, {ingest.data.unchanged}{' '}
          unchanged
          {ingest.data.errors.length > 0
            ? `, ${String(ingest.data.errors.length)} failed`
            : ''}
          .
        </p>
      ) : null}

      <div className="flex items-center justify-between gap-2">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          aria-label="Previous month"
          onClick={() => setMonth((current) => shift(current, -1))}
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <p className="text-sm font-semibold text-foreground">{monthLabel(month)}</p>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          aria-label="Next month"
          onClick={() => setMonth((current) => shift(current, 1))}
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {state === 'loading' ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : state === 'offline' ? (
        <p className="text-sm text-muted-foreground">
          Waiting for the network — the calendar could not be loaded yet.
        </p>
      ) : state === 'error' ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(monthQuery.error, 'Could not load the calendar.')}
        </p>
      ) : state === 'empty' ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <CalendarDays className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">Nothing scheduled in this month.</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {Object.entries(days)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([day, entries]) => (
              <li key={day} className="rounded-lg border border-border bg-card p-3">
                <p className={cn('mb-2 text-xs font-semibold text-foreground')}>
                  {new Date(`${day}T00:00:00`).toLocaleDateString(undefined, {
                    weekday: 'long',
                    day: 'numeric',
                    month: 'short',
                  })}
                </p>
                <ul className="space-y-2">
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
