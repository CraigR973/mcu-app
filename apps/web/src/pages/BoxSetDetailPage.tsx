import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, X } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
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
    <div className="archive-panel space-y-3 p-4 sm:p-5">
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
        <Button type="button" variant="ghost" size="icon" onClick={onDone} aria-label="Close disc picker">
          <X className="h-4 w-4" />
        </Button>
      </div>

      {movieId === null ? (
        query.trim().length <= 1 ? (
          <p className="text-sm text-muted-foreground">Enter at least two characters to find a film.</p>
        ) : searchQuery.isPending ? (
          <StatePanel compact tone="loading" title="Searching the collection" />
        ) : searchQuery.fetchStatus === 'paused' && searchQuery.data === undefined ? (
          <StatePanel compact tone="offline" title="Search needs the network" />
        ) : searchQuery.isError ? (
          <StatePanel
            compact
            tone="error"
            title="Search unavailable"
            description={queryErrorMessage(searchQuery.error, 'Could not search the collection.')}
          />
        ) : (searchQuery.data?.items.length ?? 0) === 0 ? (
          <StatePanel compact tone="empty" title="No collection films match" />
        ) : (
          <ul className="divide-y divide-border">
            {searchQuery.data?.items.map((movie) => (
              <li key={movie.id}>
                <button
                  type="button"
                  className="min-h-11 w-full rounded-md px-3 py-2 text-left text-sm text-foreground hover:bg-muted"
                  onClick={() => setMovieId(movie.id)}
                >
                  {movie.title}
                  {movie.year === null ? '' : ` (${String(movie.year)})`}
                </button>
              </li>
            ))}
          </ul>
        )
      ) : (
        copiesQuery.isPending ? (
          <StatePanel compact tone="loading" title="Loading owned copies" />
        ) : copiesQuery.fetchStatus === 'paused' && copiesQuery.data === undefined ? (
          <StatePanel compact tone="offline" title="Owned copies need the network" />
        ) : copiesQuery.isError ? (
          <StatePanel
            compact
            tone="error"
            title="Owned copies unavailable"
            description={queryErrorMessage(copiesQuery.error, 'Could not load this film’s copies.')}
          />
        ) : (copiesQuery.data?.length ?? 0) === 0 ? (
          <StatePanel compact tone="empty" title="No owned copies to add" />
        ) : (
          <ul className="divide-y divide-border">
            {copiesQuery.data?.map((copy) => (
              <li key={copy.id}>
                <button
                  type="button"
                  disabled={add.isPending}
                  className="min-h-11 w-full rounded-md px-3 py-2 text-left text-sm text-foreground hover:bg-muted disabled:opacity-50"
                  onClick={() => add.mutate(copy.id)}
                >
                  {copy.formats.map((f) => formatLabel(f)).join(' + ')} ·{' '}
                  {copy.location ?? 'Unfiled'}
                </button>
              </li>
            ))}
          </ul>
        )
      )}

      {add.isError ? (
        <p role="alert" className="text-sm text-destructive">
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
      <div className="page-shell-narrow">
        <StatePanel
          tone="error"
          title="Box set unavailable"
          description={queryErrorMessage(setQuery.error, 'Could not load this box set.')}
          action={(
            <Button asChild variant="outline">
              <Link to="/box-sets">Back to box sets</Link>
            </Button>
          )}
        />
      </div>
    )
  }
  if (setQuery.fetchStatus === 'paused' && !boxSet) {
    return (
      <div className="page-shell-narrow">
        <StatePanel tone="offline" title="This box set needs the network" />
      </div>
    )
  }
  if (!boxSet) {
    return (
      <div className="page-shell-narrow">
        <StatePanel tone="loading" title="Opening box set" />
      </div>
    )
  }

  return (
    <div className="page-shell-narrow space-y-5">
      <PageHeader
        eyebrow="Box set"
        title={boxSet.name}
        backTo="/box-sets"
        backLabel="All box sets"
        meta={[
          boxSet.label,
          boxSet.seriesName,
          completionLabel(boxSet),
        ].filter(Boolean).join(' · ')}
        actions={profile?.role === 'admin' ? (
          <Button
            type="button"
            variant="outline"
            aria-label="Delete box set"
            disabled={destroy.isPending}
            onClick={() => destroy.mutate()}
          >
            <Trash2 className="h-4 w-4" />
            Delete set
          </Button>
        ) : null}
      />

      {destroy.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {queryErrorMessage(destroy.error, 'Could not delete this box set.')}
        </p>
      ) : null}
      {remove.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {queryErrorMessage(remove.error, 'Could not remove that disc from the set.')}
        </p>
      ) : null}

      {profile?.role === 'admin' ? (
        adding ? (
          <AddDisc boxSetId={id} onDone={() => setAdding(false)} />
        ) : (
          <Button type="button" variant="outline" onClick={() => setAdding(true)}>
            <Plus className="h-4 w-4" />
            Add a disc
          </Button>
        )
      ) : null}

      {boxSet.items.length === 0 ? (
        <StatePanel
          tone="empty"
          title="No discs in this set yet"
          description={profile?.role === 'admin' ? 'Add an owned copy to begin cataloguing the box.' : undefined}
        />
      ) : (
        <ul className="space-y-2">
          {boxSet.items.map((item) => (
            <li
              key={item.collectionItemId}
              className="archive-panel flex items-center gap-3 p-3 sm:p-4"
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
                  size="icon"
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
        <section className="archive-panel p-4 sm:p-5">
          <h2 className="section-heading">Volumes in this series</h2>
          <ul className="mt-2 divide-y divide-border">
            {boxSet.volumes.map((volume) => (
              <li key={volume.id} className="py-2 text-sm">
                <Link to={`/box-sets/${volume.id}`} className="inline-flex min-h-11 items-center font-medium text-foreground hover:underline">
                  {volume.name}
                </Link>
                <span className="text-muted-foreground"> · {completionLabel(volume)}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  )
}
