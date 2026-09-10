import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Pin, Plus, Sparkles, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { SmartCollection } from '@mcu/shared'

import { COLLECTION_ICONS } from '@/components/collections/icons'
import { SmartCollectionEditor } from '@/components/collections/SmartCollectionEditor'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
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
    <li className="archive-panel flex min-h-20 flex-wrap items-center gap-3 p-3 sm:p-4">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary"><Icon className="h-5 w-5" aria-hidden /></span>
      <div className="min-w-0 flex-1">
        <Link
          to={`/collections/${collection.id}`}
          className="font-display text-lg font-semibold text-foreground hover:text-primary"
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
      <Button type="button" variant="ghost" size="icon" onClick={onEdit} aria-label={`Edit ${collection.name}`}>
        <Pencil className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={`Delete ${collection.name}`}
        disabled={remove.isPending}
        onClick={() => remove.mutate()}
      >
        <Trash2 className="h-4 w-4" />
      </Button>
      {remove.isError && <p role="alert" className="w-full text-xs text-destructive">{queryErrorMessage(remove.error, 'This collection could not be deleted.')}</p>}
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
    <div className="page-shell-narrow space-y-5">
      <PageHeader
        eyebrow="Living shelves"
        title="Collections"
        description="Saved questions that stay current as discs enter or leave the archive."
        actions={editing === null ? <Button type="button" onClick={() => setEditing('new')}><Plus aria-hidden />New collection</Button> : undefined}
      />

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
        <StatePanel tone="loading" title="Opening your collections" />
      ) : state === 'offline' ? (
        <StatePanel tone="offline" title="Collections are not cached here" description="Reconnect to load your saved collection views." />
      ) : state === 'error' ? (
        <StatePanel tone="error" title="Collections could not be opened" description={queryErrorMessage(collectionsQuery.error, 'The server did not answer.')} />
      ) : state === 'empty' ? (
        <StatePanel tone="empty" icon={Sparkles} title="No collections yet" description="Try “Unwatched 4Ks from the 2010s” or a favourite director’s films." />
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
