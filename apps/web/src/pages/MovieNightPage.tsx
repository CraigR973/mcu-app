import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Loader2, Popcorn, Square } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-4">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <Popcorn className="h-6 w-6" aria-hidden />
          Movie night
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Both of you swipe through the collection. When you both like the same film,
          that's tonight sorted.
        </p>
      </header>

      <section className="rounded-lg border border-border p-4">
        <h2 className="font-semibold">Start one</h2>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="mb-1 block text-muted-foreground">Nothing older than</span>
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
          <Button onClick={() => start.mutate()} disabled={start.isPending}>
            {start.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Popcorn className="mr-2 h-4 w-4" aria-hidden />
            )}
            Start swiping
          </Button>
        </div>
        {start.isError ? (
          <p className="mt-2 text-sm text-destructive">
            {queryErrorMessage(start.error, 'Could not start a movie night.')}
          </p>
        ) : null}
      </section>

      <section className="rounded-lg border border-border p-4">
        <h2 className="font-semibold">Yours</h2>
        {state === 'loading' ? <p className="mt-2 text-sm text-muted-foreground">Loading…</p> : null}
        {state === 'offline' ? (
          <p className="mt-2 text-sm text-muted-foreground">Waiting for the network…</p>
        ) : null}
        {state === 'error' ? (
          <p className="mt-2 text-sm text-destructive">
            {queryErrorMessage(sessions.error, 'Could not load your movie nights.')}
          </p>
        ) : null}
        {state === 'empty' ? (
          <p className="mt-2 text-sm text-muted-foreground">You have not had one yet.</p>
        ) : null}
        {state === 'ready' ? (
          <ul className="mt-2 divide-y divide-border">
            {sessions.data?.items.map((session) => (
              <li key={session.id} className="flex flex-wrap items-center gap-2 py-3">
                <Link
                  to={`/movie-night/${session.id}`}
                  className="min-w-0 flex-1 text-sm hover:underline"
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
                      onClick={() => {
                        // The origin is the web app's, not the API's — the invite is a
                        // page a person opens.
                        void navigator.clipboard
                          ?.writeText(`${window.location.origin}${session.invitePath}`)
                          .then(() => setCopied(session.id))
                      }}
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
    <div className="mx-auto max-w-md p-8 text-center">
      {join.isPending ? (
        <p className="text-sm text-muted-foreground">Joining…</p>
      ) : join.isError ? (
        <>
          <p className="text-sm text-destructive">
            {queryErrorMessage(join.error, 'That invite is not valid.')}
          </p>
          <Link to="/movie-night" className="mt-3 inline-block text-sm underline">
            Start your own instead
          </Link>
        </>
      ) : null}
    </div>
  )
}
