import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Loader2, Popcorn, Square } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import {
  createMovieNight,
  endMovieNight,
  fetchMovieNights,
  joinMovieNight,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

/** §8.3 — start a movie night, or join one somebody sent you. */
export default function MovieNightPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [decadeFrom, setDecadeFrom] = useState('')
  const [copied, setCopied] = useState<string | null>(null)
  const [copyError, setCopyError] = useState<string | null>(null)

  const sessions = useQuery({ queryKey: ['movie-nights'], queryFn: fetchMovieNights })

  const start = useMutation({
    mutationFn: () =>
      createMovieNight(decadeFrom ? { decadeFrom: Number(decadeFrom) } : {}),
    onSuccess: (session) => {
      void queryClient.invalidateQueries({ queryKey: ['movie-nights'] })
      navigate(`/movie-night/${session.id}`)
    },
  })

  const finish = useMutation({
    mutationFn: (id: string) => endMovieNight(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['movie-nights'] }),
  })

  const state = listState(sessions, (sessions.data?.items.length ?? 0) === 0)

  async function copyInvite(invitePath: string, sessionId: string) {
    setCopyError(null)
    try {
      if (!navigator.clipboard) throw new Error('Clipboard access is unavailable in this browser.')
      await navigator.clipboard.writeText(`${window.location.origin}${invitePath}`)
      setCopied(sessionId)
    } catch (cause) {
      setCopyError(queryErrorMessage(cause, 'The invite link could not be copied.'))
    }
  }

  return (
    <div className="page-shell-narrow space-y-6">
      <PageHeader
        eyebrow="Screening room"
        title="Movie night"
        description="Both of you work through the same private shortlist. When you both choose a film, tonight is sorted."
      />

      <section className="archive-panel p-4 sm:p-5">
        <h2 className="section-heading">Start a screening</h2>
        <form
          className="mt-3 flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault()
            start.mutate()
          }}
        >
          <label className="text-sm">
            <span className="field-label">Nothing older than</span>
            <Input
              type="number"
              min={1900}
              max={2100}
              placeholder="any year"
              className="w-32"
              value={decadeFrom}
              onChange={(event) => setDecadeFrom(event.target.value)}
            />
          </label>
          <Button type="submit" disabled={start.isPending}>
            {start.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Popcorn className="mr-2 h-4 w-4" aria-hidden />
            )}
            Start swiping
          </Button>
        </form>
        {start.isError ? (
          <p role="alert" className="mt-2 text-sm text-destructive">
            {queryErrorMessage(start.error, 'Could not start a movie night.')}
          </p>
        ) : null}
      </section>

      <section className="archive-panel p-4 sm:p-5">
        <h2 className="section-heading">Your screenings</h2>
        {state === 'loading' ? (
          <StatePanel compact className="mt-3" tone="loading" title="Loading screenings" />
        ) : null}
        {state === 'offline' ? (
          <StatePanel
            compact
            className="mt-3"
            tone="offline"
            title="Screenings need the network"
            description="Reconnect to load your shared sessions."
          />
        ) : null}
        {state === 'error' ? (
          <StatePanel
            compact
            className="mt-3"
            tone="error"
            title="Screenings unavailable"
            description={queryErrorMessage(sessions.error, 'Could not load your movie nights.')}
          />
        ) : null}
        {state === 'empty' ? (
          <StatePanel
            compact
            className="mt-3"
            tone="empty"
            title="No screenings yet"
            description="Start one above, then share its private invite with the other person."
          />
        ) : null}
        {finish.isError ? (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {queryErrorMessage(finish.error, 'That screening could not be ended.')}
          </p>
        ) : null}
        {copyError ? <p role="alert" className="mt-3 text-sm text-destructive">{copyError}</p> : null}
        {state === 'ready' ? (
          <ul className="mt-2 divide-y divide-border">
            {sessions.data?.items.map((session) => (
              <li key={session.id} className="flex flex-wrap items-center gap-2 py-3">
                <Link
                  to={`/movie-night/${session.id}`}
                  className="touch-target flex min-w-0 flex-1 items-center text-sm hover:underline"
                >
                  {new Date(session.createdAt).toLocaleString()} ·{' '}
                  {session.participantCount === 1 ? 'just you' : `${session.participantCount} people`}
                  {session.status === 'ended' ? ' · ended' : ''}
                </Link>
                {session.status === 'open' ? (
                  <>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => void copyInvite(session.invitePath, session.id)}
                    >
                      <Copy className="mr-1 h-3 w-3" aria-hidden />
                      {copied === session.id ? 'Copied' : 'Invite'}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => finish.mutate(session.id)}
                      disabled={finish.isPending}
                    >
                      <Square className="mr-1 h-3 w-3" aria-hidden />
                      End
                    </Button>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  )
}

/** §8.3's acceptance — *"second user joins via URL"*. */
export function MovieNightJoinPage() {
  const navigate = useNavigate()
  const token = window.location.pathname.split('/').pop() ?? ''
  const join = useQuery({
    queryKey: ['movie-night-join', token],
    queryFn: async () => {
      const session = await joinMovieNight(token)
      navigate(`/movie-night/${session.id}`, { replace: true })
      return session
    },
    // Joining is a write. Retrying it on a failure would be retrying a write, and the
    // failure here is almost always "that invite is not valid" — which retrying cannot fix.
    retry: false,
  })

  return (
    <div className="page-shell-narrow flex min-h-[60dvh] items-center justify-center">
      {join.isPending ? (
        <StatePanel compact tone="loading" title="Joining the screening" />
      ) : join.isError ? (
        <StatePanel
          compact
          tone="error"
          title="Invite unavailable"
          description={queryErrorMessage(join.error, 'That invite is not valid.')}
          action={(
            <Button asChild variant="outline">
              <Link to="/movie-night">Start your own instead</Link>
            </Button>
          )}
        />
      ) : null}
    </div>
  )
}
