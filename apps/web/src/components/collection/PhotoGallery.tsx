import { useCallback, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, ImagePlus, Loader2, Trash2, X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import {
  deleteItemPhoto,
  fetchItemPhotos,
  itemPhotoUrl,
  uploadItemPhoto,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

interface Props {
  itemId: string
  canEdit: boolean
}

/**
 * §3.10's gallery — photos of one physical disc.
 *
 * **Two file inputs, not one.** `capture="environment"` opens the camera directly on a
 * phone, which is the point of photographing a shelf; on a laptop the same attribute is
 * ignored and the control becomes an ordinary picker, so a separate "choose a file" input
 * is what makes both work without sniffing the user agent.
 *
 * Photos are resized **server-side**, so a phone uploading eight megapixels is normal and
 * the gallery shows what was actually stored.
 */
export function PhotoGallery({ itemId, canEdit }: Props) {
  const queryClient = useQueryClient()
  const cameraRef = useRef<HTMLInputElement | null>(null)
  const fileRef = useRef<HTMLInputElement | null>(null)
  const [viewing, setViewing] = useState<string | null>(null)

  const photos = useQuery({
    queryKey: ['item-photos', itemId],
    queryFn: () => fetchItemPhotos(itemId),
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['item-photos', itemId] })

  const upload = useMutation({
    mutationFn: (file: File) => uploadItemPhoto(itemId, file),
    onSuccess: () => {
      void invalidate()
    },
  })

  const remove = useMutation({
    mutationFn: (photoId: string) => deleteItemPhoto(photoId),
    onSuccess: () => {
      setViewing(null)
      void invalidate()
    },
  })

  const items = photos.data?.items ?? []
  const remaining = photos.data?.remaining ?? 0
  const state = listState(photos, items.length === 0)
  const selectedPhoto = items.find((photo) => photo.id === viewing) ?? null
  const closeLightbox = useCallback(() => setViewing(null), [])

  return (
    <div className="mt-3">
      {state === 'loading' ? (
        <p role="status" className="inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Loading disc photos…
        </p>
      ) : state === 'offline' ? (
        <div className="space-y-2" role="status">
          <p className="text-sm text-muted-foreground">
            Photos are waiting for the network.
          </p>
          <Button type="button" size="sm" variant="outline" onClick={() => void photos.refetch()}>
            Try again
          </Button>
        </div>
      ) : state === 'error' ? (
        <div className="space-y-2" role="alert">
          <p className="text-sm text-destructive">
            {queryErrorMessage(photos.error, 'Could not load the photos for this disc.')}
          </p>
          <Button type="button" size="sm" variant="outline" onClick={() => void photos.refetch()}>
            Try again
          </Button>
        </div>
      ) : items.length > 0 ? (
        <ul className="flex flex-wrap gap-2">
          {items.map((photo) => (
            <li key={photo.id} className="group relative">
              <button
                type="button"
                onClick={() => setViewing(photo.id)}
                aria-label={photo.caption ? `Open photo: ${photo.caption}` : 'Open disc photo'}
                className="touch-target rounded-md focus-visible:ring-2 focus-visible:ring-ring/30"
              >
                <img
                  src={itemPhotoUrl(photo.url)}
                  alt={photo.caption ?? ''}
                  loading="lazy"
                  className="h-20 w-20 rounded object-cover"
                />
              </button>
              {canEdit ? (
                <Button
                  type="button"
                  size="icon"
                  variant="secondary"
                  aria-label="Delete photo"
                  onClick={() => remove.mutate(photo.id)}
                  disabled={remove.isPending}
                  className="absolute -right-2 -top-2 h-9 w-9 rounded-full shadow-soft"
                >
                  <Trash2 className="text-destructive" aria-hidden />
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">No photos of this disc yet.</p>
      )}

      {canEdit && (state === 'empty' || state === 'ready') ? (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {/* `capture` opens the camera on a phone and is ignored on a laptop, which is
              why there are two inputs rather than one plus a user-agent check. */}
          <input
            ref={cameraRef}
            type="file"
            accept="image/*"
            capture="environment"
            aria-label="Take a disc photo"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) upload.mutate(file)
              event.target.value = ''
            }}
          />
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            aria-label="Choose a disc photo"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) upload.mutate(file)
              event.target.value = ''
            }}
          />
          <Button
            size="sm"
            variant="outline"
            disabled={upload.isPending || remaining === 0}
            onClick={() => cameraRef.current?.click()}
          >
            {upload.isPending ? (
              <Loader2 className="animate-spin" aria-hidden />
            ) : (
              <Camera aria-hidden />
            )}
            Take a photo
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={upload.isPending || remaining === 0}
            onClick={() => fileRef.current?.click()}
          >
            <ImagePlus aria-hidden />
            Choose a file
          </Button>
          <span className="text-sm text-muted-foreground">
            {remaining === 0 ? 'Five is the limit' : `${remaining} left`}
          </span>
        </div>
      ) : null}

      {upload.isError ? (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {queryErrorMessage(upload.error, 'That photo could not be uploaded.')}
        </p>
      ) : null}
      {remove.isError ? (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {queryErrorMessage(remove.error, 'That photo could not be deleted.')}
        </p>
      ) : null}

      <Dialog
        open={selectedPhoto !== null}
        onClose={closeLightbox}
        label={selectedPhoto?.caption ? `Disc photo: ${selectedPhoto.caption}` : 'Disc photo'}
        className="overflow-hidden border-brand-champagne/30 bg-brand-ink sm:max-w-5xl"
      >
        {selectedPhoto ? (
          <figure className="relative flex min-h-64 flex-col items-center justify-center p-3 sm:p-5">
            <img
              src={itemPhotoUrl(selectedPhoto.url)}
              alt={selectedPhoto.caption ?? 'Photo of this disc'}
              className="max-h-[78dvh] w-auto rounded-md object-contain shadow-lift"
            />
            {selectedPhoto.caption ? (
              <figcaption className="mt-3 text-sm text-brand-cream/80">
                {selectedPhoto.caption}
              </figcaption>
            ) : null}
            <Button
              type="button"
              aria-label="Close photo"
              size="icon"
              variant="secondary"
              className="absolute right-3 top-3 rounded-full"
              onClick={closeLightbox}
            >
              <X aria-hidden />
            </Button>
          </figure>
        ) : null}
      </Dialog>
    </div>
  )
}
