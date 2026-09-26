import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Save, Trash2, X } from 'lucide-react'

import CopyForm from '@/components/collection/CopyForm'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import {
  StaleEditError,
  type CollectionCopy,
  type CollectionItemFields,
  type Condition,
} from '@/lib/api'
import { deleteOrQueue, updateOrQueue } from '@/lib/sync'

interface Props {
  movieId: string
  copy: CollectionCopy
  onClose: () => void
}

/** Turn a copy as the read surface returns it into the editable field set.
 *
 *  Only the fields `PUT /collection/{id}` accepts. AV specs, photos, the barcode and
 *  the listing status are on the copy but belong to later phases, and the endpoint
 *  deliberately does not touch them. */
export function fieldsFrom(copy: CollectionCopy): CollectionItemFields {
  return {
    formats: copy.formats,
    location: copy.location,
    section: copy.section,
    shelf: copy.shelf,
    subCategory: copy.subCategory,
    edition: copy.edition,
    notes: copy.notes,
    condition: (copy.condition as Condition | null) ?? null,
    hasPlaybackIssues: copy.hasPlaybackIssues,
    playbackNotes: copy.playbackNotes,
    purchasePrice: copy.purchasePrice,
    purchaseSource: copy.purchaseSource,
    purchaseDate: copy.purchaseDate,
  }
}

/**
 * §3.2's edit form and soft delete, as a dialog over the film's detail page.
 *
 * The whole editable field set goes up on every save, which is what makes the API's
 * `PUT` honest: "absent" means the user cleared it, not that an older client never
 * knew about the field.
 */
export default function CopyEditor({ movieId, copy, onClose }: Props) {
  const queryClient = useQueryClient()
  const [fields, setFields] = useState<CollectionItemFields>(() => fieldsFrom(copy))

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ['movie-copies', movieId] })
    void queryClient.invalidateQueries({ queryKey: ['movie', movieId] })
    // The grid badges `bestFormatOwned` and the filter bar counts shelves; a format or
    // location change makes both stale.
    void queryClient.invalidateQueries({ queryKey: ['movies'] })
    void queryClient.invalidateQueries({ queryKey: ['search'] })
    void queryClient.invalidateQueries({ queryKey: ['facets'] })
    void queryClient.invalidateQueries({ queryKey: ['item-history', movieId] })
    void queryClient.invalidateQueries({ queryKey: ['trash'] })
  }

  const save = useMutation({
    mutationFn: () =>
      // `baseUpdatedAt` is what stops this edit overwriting a newer one if it ends up
      // waiting in the queue. Sent even when online: an online save can still race a
      // change made on the other person's phone a second earlier.
      updateOrQueue(copy.id, movieId, { ...fields, baseUpdatedAt: copy.updatedAt }),
    onSuccess: () => {
      refresh()
      onClose()
    },
  })

  const remove = useMutation({
    mutationFn: () => deleteOrQueue(copy.id, movieId),
    onSuccess: () => {
      refresh()
      onClose()
    },
  })

  const pending = save.isPending || remove.isPending
  const error = save.error ?? remove.error

  return (
    <Dialog open onClose={onClose} label="Edit this copy" className="sm:max-w-2xl">
      <div className="space-y-5 p-4 sm:p-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="section-heading">Edit this copy</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Changes are recorded in the audit log.
            </p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="Close"
          >
            <X aria-hidden />
          </Button>
        </div>

        <CopyForm value={fields} onChange={setFields} disabled={pending} />

        {error && (
          <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error instanceof StaleEditError
              ? 'This disc was changed somewhere else while you were editing. Close and reopen it to see the current version.'
              : error instanceof Error
                ? error.message
                : 'That change could not be saved.'}
          </p>
        )}

        <div className="flex flex-col-reverse gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
          <Button
            type="button"
            variant="destructive"
            disabled={pending}
            onClick={() => remove.mutate()}
            className="w-full sm:w-auto"
          >
            {remove.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
            Move to trash
          </Button>
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <Button type="button" variant="ghost" disabled={pending} onClick={onClose} className="w-full sm:w-auto">
              Cancel
            </Button>
            <Button
              type="button"
              disabled={pending || fields.formats.length === 0}
              onClick={() => save.mutate()}
              className="w-full sm:w-auto"
            >
              {save.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              Save changes
            </Button>
          </div>
        </div>
      </div>
    </Dialog>
  )
}
