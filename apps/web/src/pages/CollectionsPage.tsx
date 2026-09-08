import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Pin, Plus, Sparkles, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { SmartCollection } from '@mcu/shared'

import { COLLECTION_ICONS } from '@/components/collections/icons'
import { SmartCollectionEditor } from '@/components/collections/SmartCollectionEditor'
import { Button } from '@/components/ui/button'
import {
  createSmartCollection,
  deleteSmartCollection,
  describeFilters,
  fetchSmartCollections,
  updateSmartCollection,
  type SmartCollectionInput,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

function Card({
  collection,
  onEdit,
}: {
  collection: SmartCollection
  onEdit: () => void
}) {
  const queryClient = useQueryClient()
  const Icon = COLLECTION_ICONS[collection.icon]

  const remove = useMutation({
    mutationFn: () => deleteSmartCollection(collection.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['smart-collections'] })
    },
  })

  return (
    <li className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
      <Icon className="h-5 w-5 shrink-0 text-primary" />
      <div className="min-w-0 flex-1">
        <Link
          to={`/collections/${collection.id}`}
          className="font-medium text-foreground hover:underline"
        >
          {collection.name}
        </Link>
        <p className="truncate text-xs text-muted-foreground">
          {describeFilters(collection.filters)}
        </p>
      </div>
      {collection.isPinned ? (
        <Pin className="h-4 w-4 shrink-0 text-muted-foreground" aria-label="Pinned to dashboard" />
      ) : null}
      <Button type="button" variant="ghost" size="sm" onClick={onEdit} aria-label="Edit">
        <Pencil className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        aria-label="Delete"
        disabled={remove.isPending}
        onClick={() => remove.mutate()}
      >
        <Trash2 className="h-4 w-4" />
      </Button>
    </li>
  )
}

/**
 * §11.5's smart collections — §6.31's "saved filter sets that update as the catalog
 * changes".
 *
 * Deleting one is immediate and unconfirmed, unlike every other delete in this app.
 * That is deliberate: a smart collection owns no data. It is a saved question, and
 * losing one costs the ten seconds it took to describe — there is nothing here for a
 * trash to hold.
 */
export default function CollectionsPage() {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<SmartCollection | 'new' | null>(null)

  const collectionsQuery = useQuery({
    queryKey: ['smart-collections'],
    queryFn: () => fetchSmartCollections(),
  })
  const items = collectionsQuery.data?.items ?? []
  const state = listState(collectionsQuery, items.length === 0)

  const save = useMutation({
    mutationFn: (input: SmartCollectionInput) =>
      editing === 'new' || editing === null
        ? createSmartCollection(input)
        : updateSmartCollection(editing.id, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['smart-collections'] })
      setEditing(null)
    },
  })

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Smart collections</h1>
          <p className="text-sm text-muted-foreground">
            Saved filters that stay current. Add a disc that matches and it appears here
            without anything being updated.
          </p>
        </div>
        {editing === null ? (
          <Button type="button" size="sm" onClick={() => setEditing('new')}>
            <Plus className="h-4 w-4" />
            New
          </Button>
        ) : null}
      </div>

      {editing !== null ? (
        <SmartCollectionEditor
          existing={editing === 'new' ? undefined : editing}
          pending={save.isPending}
          error={save.isError ? queryErrorMessage(save.error, 'Could not save.') : null}
          onSave={(input) => save.mutate(input)}
          onCancel={() => {
            save.reset()
            setEditing(null)
          }}
        />
      ) : null}

      {state === 'loading' ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : state === 'offline' ? (
        <p className="text-sm text-muted-foreground">
          Waiting for the network — your collections could not be loaded yet.
        </p>
      ) : state === 'error' ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(collectionsQuery.error, 'Could not load your collections.')}
        </p>
      ) : state === 'empty' ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <Sparkles className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">
            No smart collections yet. Try &ldquo;Unwatched 4Ks from the 2010s&rdquo;.
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {items.map((collection) => (
            <Card
              key={collection.id}
              collection={collection}
              onEdit={() => {
                save.reset()
                setEditing(collection)
              }}
            />
          ))}
        </ul>
      )}
    </div>
  )
}
