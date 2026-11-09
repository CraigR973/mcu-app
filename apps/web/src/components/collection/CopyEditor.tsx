import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus, Save, Trash2, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import CopyForm from '@/components/collection/CopyForm'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import {
  formatLabel,
  StaleEditError,
  type CollectionCopy,
  type CollectionItemFields,
  type Condition,
} from '@/lib/api'
import { addCopyPath, addedDiscFormats, inFormOrder } from '@/lib/copy-formats'
import { deleteOrQueue, updateOrQueue } from '@/lib/sync'
import { queryErrorMessage } from '@/lib/query-state'

/** "4K UHD", "4K UHD and DVD": the formats named in a sentence, best first. */
function named(formats: readonly string[]): string {
  const labels = inFormOrder(formats).map((code) => formatLabel(code) ?? code)
  return labels.length <= 1 ? (labels[0] ?? '') : `${labels.slice(0, -1).join(', ')} and ${labels[labels.length - 1]}`
}

/** Whether anything but the formats differs from the copy as it was opened. */
function otherFieldsChanged(copy: CollectionCopy, fields: CollectionItemFields): boolean {
  return JSON.stringify({ ...fieldsFrom(copy), formats: [] }) !== JSON.stringify({ ...fields, formats: [] })
}

interface Props {
  movieId: string
  copy: CollectionCopy
  /** Only the admin can restore from the Trash, so the delete confirmation says who can. */
  isAdmin: boolean
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
export default function CopyEditor({ movieId, copy, isAdmin, onClose }: Props) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [fields, setFields] = useState<CollectionItemFields>(() => fieldsFrom(copy))
  // AE1 (#355, point 10): the disc formats a save would add beside another disc. While set,
  // the footer asks "one box, or a separate copy?" instead of saving.
  const [askingAbout, setAskingAbout] = useState<string[] | null>(null)
  const askRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (askingAbout) askRef.current?.scrollIntoView?.({ block: 'nearest' })
  }, [askingAbout])
  // Batch Y1 (#264): both people can delete now, and only Craig can restore, so one stray
  // tap on a phone must not be enough. The first tap asks; the second deletes.
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const confirmRef = useRef<HTMLDivElement>(null)
  // While it asks, the question and its two answers are all the footer holds, scrolled into
  // view. Y1's version grew a warning above the buttons, which pushed "Yes" off a phone's
  // screen and left Save in its place: Mark tapped Save, and the disc stayed (13 Oct).
  useEffect(() => {
    if (confirmingDelete) confirmRef.current?.scrollIntoView?.({ block: 'nearest' })
  }, [confirmingDelete])

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

  /** Save, unless the edit puts a second disc in this copy: then ask which is meant first. */
  function trySave() {
    const added = addedDiscFormats(copy.formats, fields.formats)
    if (added.length > 0) {
      setAskingAbout(added)
      return
    }
    save.mutate()
  }

  /** "A separate copy": this copy is left as it was, and Add a copy opens for the same film
   *  with the new format chosen. Nothing is saved here. */
  function addSeparateCopy(added: readonly string[]) {
    onClose()
    navigate(addCopyPath(movieId, added))
  }

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

        {/* Held still while the question below is open, so its answer is about what it names. */}
        <CopyForm value={fields} onChange={setFields} disabled={pending || askingAbout !== null} />

        {error && (
          <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error instanceof StaleEditError
              ? 'This disc was changed somewhere else while you were editing. Close and reopen it to see the current version.'
              : queryErrorMessage(error, 'That change could not be saved.')}
          </p>
        )}

        {askingAbout ? (
          <div
            ref={askRef}
            role="alertdialog"
            aria-label="One box with both discs, or a separate copy?"
            className="space-y-3 rounded-md border border-warning/45 bg-warning/10 p-3"
          >
            <p className="text-sm font-semibold text-foreground">One box with both discs, or a separate copy?</p>
            <p className="text-sm text-foreground">
              One box makes this copy {named(fields.formats)}, a combo pack. A separate copy leaves this one as{' '}
              {named(copy.formats)} and adds the {named(askingAbout)} as its own copy.
            </p>
            {otherFieldsChanged(copy, fields) ? (
              <p className="text-sm text-muted-foreground">Your other changes here are not kept if you add a separate copy.</p>
            ) : null}
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
              <Button type="button" disabled={pending} onClick={() => save.mutate()} className="w-full sm:w-auto">
                {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                One box with both discs
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={pending}
                onClick={() => addSeparateCopy(askingAbout)}
                className="w-full sm:w-auto"
              >
                <Plus className="h-4 w-4" />
                A separate copy
              </Button>
              <Button type="button" variant="ghost" disabled={pending} onClick={() => setAskingAbout(null)} className="w-full sm:w-auto">
                Back
              </Button>
            </div>
          </div>
        ) : confirmingDelete ? (
          <div
            ref={confirmRef}
            role="alertdialog"
            aria-label="Move this copy to the Trash?"
            className="space-y-3 rounded-md border border-destructive/30 bg-destructive/10 p-3"
          >
            <p className="text-sm font-semibold text-destructive">Move this copy to the Trash?</p>
            <p className="text-sm text-destructive">
              {isAdmin ? 'You can restore it from the Trash.' : 'Only Craig can bring it back.'}
            </p>
            <div className="flex flex-col gap-2 sm:flex-row">
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
                Yes, move to trash
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={pending}
                onClick={() => setConfirmingDelete(false)}
                className="w-full sm:w-auto"
              >
                Keep it
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col-reverse gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
            <Button
              type="button"
              variant="destructive"
              disabled={pending}
              onClick={() => setConfirmingDelete(true)}
              className="w-full sm:w-auto"
            >
              <Trash2 className="h-4 w-4" />
              Move to trash
            </Button>
            <div className="flex flex-col-reverse gap-2 sm:flex-row">
              <Button type="button" variant="ghost" disabled={pending} onClick={onClose} className="w-full sm:w-auto">
                Cancel
              </Button>
              <Button
                type="button"
                disabled={pending || fields.formats.length === 0}
                onClick={trySave}
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
        )}
      </div>
    </Dialog>
  )
}
