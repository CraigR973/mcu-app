import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Plus, Trash2, X } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/context/auth'
import {
  addBoxSetItem,
  completionLabel,
  deleteBoxSet,
  fetchBoxSet,
  fetchCopies,
  fetchSearch,
  formatLabel,
  posterUrl,
  removeBoxSetItem,
} from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

/**
 * Adding a disc to a box, in the order a person has one in their hand: find the film,
 * then say *which copy*.
 *
 * The junction points at a `collection_item`, not a film, and the distinction is real —
 * a film owned on 4K and on DVD is two rows, and only one of them came in the box. A
 * picker that stopped at the film would have to guess, and would guess wrong for exactly
 * the films most likely to be in a box set.
 */
function AddDisc({ boxSetId, onDone }: { boxSetId: string; onDone: () => void }) {
  const queryClient = useQueryClient()
  const [query, setQuery] = useState('')
  const [movieId, setMovieId] = useState<string | null>(null)

  const searchQuery = useQuery({
    queryKey: ['search', query],
    queryFn: () => fetchSearch(query, 8),
    enabled: query.trim().length > 1,
  })

  const copiesQuery = useQuery({
    queryKey: ['movie-copies', movieId],
    queryFn: () => fetchCopies(movieId ?? ''),
    enabled: movieId !== null,
  })

  const add = useMutation({
    mutationFn: (collectionItemId: string) => addBoxSetItem(boxSetId, collectionItemId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['box-set', boxSetId] })
      void queryClient.invalidateQueries({ queryKey: ['box-sets'] })
      onDone()
    },
  })

  return (
    <div className="space-y-3 rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2">
        <Input
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
            setMovieId(null)
          }}
          placeholder="Find a film already in the collection"
          aria-label="Find a film"
        />
        <Button type="button" variant="ghost" size="sm" onClick={onDone} aria-label="Close">
          <X className="h-4 w-4" />
        </Button>
      </div>

      {movieId === null ? (
        <ul className="space-y-1">
          {(searchQuery.data?.items ?? []).map((movie) => (
            <li key={movie.id}>
              <button
                type="button"
                className="w-full rounded px-2 py-1 text-left text-sm text-foreground hover:bg-muted"
                onClick={() => setMovieId(movie.id)}
              >
                {movie.title}
                {movie.year === null ? '' : ` (${String(movie.year)})`}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <ul className="space-y-1">
          {(copiesQuery.data ?? []).map((copy) => (
            <li key={copy.id}>
              <button
                type="button"
                disabled={add.isPending}
                className="w-full rounded px-2 py-1 text-left text-sm text-foreground hover:bg-muted"
                onClick={() => add.mutate(copy.id)}
              >
                {copy.formats.map((f) => formatLabel(f)).join(' + ')} ·{' '}
                {copy.location ?? 'Unfiled'}
              </button>
            </li>
          ))}
        </ul>
      )}

      {add.isError ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(add.error, 'Could not add that disc.')}
        </p>
      ) : null}
    </div>
  )
}

/** §11.4's "dedicated box set view" — the discs in one box, and its sibling volumes. */
export default function BoxSetDetailPage() {
  const { id = '' } = useParams<{ id: string }>()
  const { profile } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [adding, setAdding] = useState(false)

  const setQuery = useQuery({ queryKey: ['box-set', id], queryFn: () => fetchBoxSet(id) })
  const boxSet = setQuery.data

  const remove = useMutation({
    mutationFn: (collectionItemId: string) => removeBoxSetItem(id, collectionItemId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['box-set', id] })
      void queryClient.invalidateQueries({ queryKey: ['box-sets'] })
    },
  })

  const destroy = useMutation({
    mutationFn: () => deleteBoxSet(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['box-sets'] })
      void navigate('/box-sets')
    },
  })

  if (setQuery.isError) {
    return (
      <p className="p-8 text-sm text-destructive">
        {queryErrorMessage(setQuery.error, 'Could not load this box set.')}
      </p>
    )
  }
  if (!boxSet) return <p className="p-8 text-sm text-muted-foreground">Loading…</p>

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-8">
      <div className="flex items-start gap-3">
        <Link
          to="/box-sets"
          className="mt-1 text-muted-foreground hover:text-foreground"
          aria-label="Back to box sets"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-bold text-foreground">{boxSet.name}</h1>
          <p className="text-sm text-muted-foreground">
            {[boxSet.label, boxSet.seriesName, completionLabel(boxSet)]
              .filter(Boolean)
              .join(' · ')}
          </p>
        </div>
        {profile?.role === 'admin' ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label="Delete box set"
            disabled={destroy.isPending}
            onClick={() => destroy.mutate()}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        ) : null}
      </div>

      {profile?.role === 'admin' ? (
        adding ? (
          <AddDisc boxSetId={id} onDone={() => setAdding(false)} />
        ) : (
          <Button type="button" size="sm" variant="outline" onClick={() => setAdding(true)}>
            <Plus className="h-4 w-4" />
            Add a disc
          </Button>
        )
      ) : null}

      {boxSet.items.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No discs in this set yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {boxSet.items.map((item) => (
            <li
              key={item.collectionItemId}
              className="flex items-center gap-3 rounded-lg border border-border bg-card p-3"
            >
              <img
                src={posterUrl(item.posterPath, 'w92')}
                alt=""
                className="h-16 w-11 shrink-0 rounded object-cover"
                loading="lazy"
              />
              <div className="min-w-0 flex-1">
                <Link
                  to={`/movies/${item.movieId}`}
                  className="font-medium text-foreground hover:underline"
                >
                  {item.movieTitle}
                </Link>
                <p className="text-xs text-muted-foreground">
                  {item.discNumber === null ? '' : `Disc ${String(item.discNumber)} · `}
                  {item.formats.map((f) => formatLabel(f)).join(' + ')} · {item.locationLabel}
                </p>
              </div>
              {profile?.role === 'admin' ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  aria-label={`Remove ${item.movieTitle}`}
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(item.collectionItemId)}
                >
                  <X className="h-4 w-4" />
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {boxSet.volumes.length > 0 ? (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold text-foreground">Volumes in this series</h2>
          <ul className="space-y-1">
            {boxSet.volumes.map((volume) => (
              <li key={volume.id} className="text-sm">
                <Link to={`/box-sets/${volume.id}`} className="text-foreground hover:underline">
                  {volume.name}
                </Link>
                <span className="text-muted-foreground"> · {completionLabel(volume)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
