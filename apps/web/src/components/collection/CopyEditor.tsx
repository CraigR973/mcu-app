import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Save, Trash2, X } from 'lucide-react'

import CopyForm from '@/components/collection/CopyForm'
import { Button } from '@/components/ui/button'
import {
  deleteCollectionItem,
  updateCollectionItem,
  type CollectionCopy,
  type CollectionItemFields,
  type Condition,
} from '@/lib/api'

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
    mutationFn: () => updateCollectionItem(copy.id, fields),
    onSuccess: () => {
      refresh()
      onClose()
    },
  })

  const remove = useMutation({
    mutationFn: () => deleteCollectionItem(copy.id),
    onSuccess: () => {
      refresh()
      onClose()
    },
  })

  const pending = save.isPending || remove.isPending
  const error = save.error ?? remove.error

  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-black/50 p-4 sm:items-center">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Edit this copy"
        className="w-full max-w-2xl space-y-4 rounded-xl border border-border bg-card p-5 shadow-xl"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-foreground">Edit this copy</h2>
            <p className="text-xs text-muted-foreground">
              Changes are recorded in the audit log.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <CopyForm value={fields} onChange={setFields} disabled={pending} />

        {error && (
          <p className="text-sm text-destructive">
            {error instanceof Error ? error.message : 'That change could not be saved.'}
          </p>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
          <Button
            type="button"
            variant="destructive"
            disabled={pending}
            onClick={() => remove.mutate()}
          >
            {remove.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
            Move to trash
          </Button>
          <div className="flex gap-2">
            <Button type="button" variant="ghost" disabled={pending} onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="button"
              disabled={pending || fields.formats.length === 0}
              onClick={() => save.mutate()}
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
    </div>
  )
}
