import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, RotateCcw, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import {
  fetchTrash,
  formatLabel,
  posterUrl,
  restoreCollectionItem,
  type TrashItem,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

function Row({ item }: { item: TrashItem }) {
  const queryClient = useQueryClient()

  const restore = useMutation({
    mutationFn: () => restoreCollectionItem(item.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['trash'] })
      // Restoring puts a disc back in every count: the film's copies, the grid's
      // format badge, and the shelf facets.
      void queryClient.invalidateQueries({ queryKey: ['movies'] })
      void queryClient.invalidateQueries({ queryKey: ['search'] })
      void queryClient.invalidateQueries({ queryKey: ['facets'] })
      void queryClient.invalidateQueries({ queryKey: ['movie-copies', item.movieId] })
      void queryClient.invalidateQueries({ queryKey: ['item-history', item.movieId] })
    },
  })

  return (
    <li className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
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
          {item.formats.map((format) => formatLabel(format)).join(' + ')} · {item.locationLabel}
        </p>
        <p className="text-[11px] text-muted-foreground">
          Removed {new Date(item.deletedAt).toLocaleString()}
        </p>
      </div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={restore.isPending}
        onClick={() => restore.mutate()}
      >
        {restore.isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <RotateCcw className="h-4 w-4" />
        )}
        Restore
      </Button>
    </li>
  )
}

/**
 * §3.2's "deleted items appear in Trash UI", and the restore half of §13.5.
 *
 * **There is no permanent delete here.** §13.5 owns it along with the other
 * soft-deleting tables, and it is the one action in this area that cannot be undone —
 * shipping it before the batch that specifies it would be the wrong order to take that
 * risk in.
 */
export default function TrashPage() {
  const trashQuery = useQuery({ queryKey: ['trash'], queryFn: fetchTrash })
  const items = trashQuery.data?.items ?? []
  const state = listState(trashQuery, items.length === 0)

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Trash</h1>
        <p className="text-sm text-muted-foreground">
          Discs removed from the collection. Restoring brings one back exactly as it was.
        </p>
      </div>

      {state === 'loading' ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : state === 'offline' ? (
        <p className="text-sm text-muted-foreground">
          Waiting for the network — the trash could not be loaded yet.
        </p>
      ) : state === 'error' ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(trashQuery.error, 'Could not load the trash.')}
        </p>
      ) : state === 'empty' ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <Trash2 className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">Nothing has been removed.</p>
        </div>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => (
            <Row key={item.id} item={item} />
          ))}
        </ul>
      )}
    </div>
  )
}
