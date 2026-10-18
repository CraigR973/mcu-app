import { useQuery } from '@tanstack/react-query'
import { formatDate } from '@/lib/utils'
import { Eye, Pencil, Plus, RotateCcw, Trash2, type LucideIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ActivityEvent, ActivityKind } from '@mcu/shared'

import { fetchActivity, posterUrl } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

const KIND_ICON: Record<ActivityKind, LucideIcon> = {
  added: Plus,
  watched: Eye,
  edited: Pencil,
  removed: Trash2,
  restored: RotateCcw,
}

const KIND_VERB: Record<ActivityKind, string> = {
  added: 'added',
  watched: 'watched',
  edited: 'edited',
  removed: 'removed',
  restored: 'restored',
}

function Row({ event }: { event: ActivityEvent }) {
  const Icon = KIND_ICON[event.kind]
  const title = event.movieTitle ?? event.detail ?? 'something'
  const content = (
    <>
      <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
      {event.movieTitle ? (
        <img
          src={posterUrl(event.posterPath, 'w92')}
          alt=""
          loading="lazy"
          className="h-9 w-6 shrink-0 rounded object-cover"
        />
      ) : null}
      <p className="min-w-0 flex-1 truncate text-xs text-foreground">
        <span className="text-muted-foreground">{event.actorName ?? 'Someone'} </span>
        {KIND_VERB[event.kind]} <span className="font-medium">{title}</span>
      </p>
      <time className="shrink-0 text-xs text-muted-foreground" dateTime={event.at}>
        {formatDate(event.at)}
      </time>
    </>
  )
  // Batch X12b (UX48-06): the whole row opens the film, 44px tall, where the review found a
  // 15px title link to hit.
  return (
    <li>
      {event.movieId ? (
        <Link
          to={`/movies/${event.movieId}`}
          className="flex min-h-11 items-center gap-2.5 py-1.5 hover:bg-muted/50"
        >
          {content}
        </Link>
      ) : (
        <div className="flex min-h-11 items-center gap-2.5 py-1.5">{content}</div>
      )}
    </li>
  )
}

/**
 * §13.2's activity feed — "last 20 events across all users".
 *
 * **Two of the four sources §13.2 names do not exist yet**: price drops are Batch 20 and
 * loans are Batch 15. Both add rows to the same endpoint when they land, so nothing here
 * changes. What is shown is real — watches, and every admin write.
 */
export function ActivityFeed({ limit = 20 }: { limit?: number }) {
  const activityQuery = useQuery({
    queryKey: ['activity', limit],
    queryFn: () => fetchActivity(limit),
  })
  const events = activityQuery.data?.items ?? []
  const state = listState(activityQuery, events.length === 0)

  if (state === 'loading') return <p className="text-sm text-muted-foreground">Loading…</p>
  if (state === 'offline') {
    return (
      <p className="text-sm text-muted-foreground">
        Waiting for the network — recent activity could not be loaded yet.
      </p>
    )
  }
  if (state === 'error') {
    return (
      <p className="text-sm text-destructive">
        {queryErrorMessage(activityQuery.error, 'Could not load recent activity.')}
      </p>
    )
  }
  if (state === 'empty') {
    return (
      <p className="text-sm text-muted-foreground">
        Nothing yet. Watches and changes to the collection appear here.
      </p>
    )
  }

  return (
    <ul className="divide-y divide-border">
      {events.map((event) => (
        <Row key={event.id} event={event} />
      ))}
    </ul>
  )
}
