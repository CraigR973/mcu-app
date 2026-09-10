import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, ImagePlus, Loader2, Trash2, X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  deleteItemPhoto,
  fetchItemPhotos,
  itemPhotoUrl,
  uploadItemPhoto,
} from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

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
  const [error, setError] = useState<string | null>(null)

  const photos = useQuery({
    queryKey: ['item-photos', itemId],
    queryFn: () => fetchItemPhotos(itemId),
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['item-photos', itemId] })

  const upload = useMutation({
    mutationFn: (file: File) => uploadItemPhoto(itemId, file),
    onSuccess: () => {
      setError(null)
      void invalidate()
    },
    onError: (cause) =>
      setError(queryErrorMessage(cause, 'That photo could not be uploaded.')),
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

  return (
    <div className="mt-3">
      {items.length > 0 ? (
        <ul className="flex flex-wrap gap-2">
          {items.map((photo) => (
            <li key={photo.id} className="group relative">
              <button
                type="button"
                onClick={() => setViewing(photo.id)}
                aria-label={photo.caption ?? 'Open photo'}
              >
                <img
                  src={itemPhotoUrl(photo.url)}
                  alt={photo.caption ?? ''}
                  loading="lazy"
                  className="h-20 w-20 rounded object-cover"
                />
              </button>
              {canEdit ? (
                <button
                  type="button"
                  aria-label="Delete photo"
                  onClick={() => remove.mutate(photo.id)}
                  disabled={remove.isPending}
                  className="absolute -right-1 -top-1 rounded-full bg-background p-1 opacity-0 shadow transition-opacity group-hover:opacity-100 focus:opacity-100"
                >
                  <Trash2 className="h-3 w-3 text-destructive" aria-hidden />
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-muted-foreground">No photos of this disc yet.</p>
      )}

      {canEdit ? (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {/* `capture` opens the camera on a phone and is ignored on a laptop, which is
              why there are two inputs rather than one plus a user-agent check. */}
          <input
            ref={cameraRef}
            type="file"
            accept="image/*"
            capture="environment"
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
              <Loader2 className="mr-1 h-3 w-3 animate-spin" aria-hidden />
            ) : (
              <Camera className="mr-1 h-3 w-3" aria-hidden />
            )}
            Take a photo
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={upload.isPending || remaining === 0}
            onClick={() => fileRef.current?.click()}
          >
            <ImagePlus className="mr-1 h-3 w-3" aria-hidden />
            Choose a file
          </Button>
          <span className="text-xs text-muted-foreground">
            {remaining === 0 ? 'Five is the limit' : `${remaining} left`}
          </span>
        </div>
      ) : null}

      {error ? <p className="mt-2 text-xs text-destructive">{error}</p> : null}

      {viewing ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          role="dialog"
          aria-modal="true"
          onClick={() => setViewing(null)}
        >
          <img
            src={itemPhotoUrl(items.find((photo) => photo.id === viewing)?.url ?? '')}
            alt=""
            className="max-h-full max-w-full rounded shadow-2xl"
          />
          <button
            type="button"
            aria-label="Close"
            className="absolute right-4 top-4 rounded-full bg-background p-2"
            onClick={() => setViewing(null)}
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
      ) : null}
    </div>
  )
}
