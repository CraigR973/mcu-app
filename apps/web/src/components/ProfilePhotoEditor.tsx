import { useRef } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { removeProfilePhoto, uploadProfilePhoto } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

export function ProfilePhotoEditor({ profileId }: { profileId: string }) {
  const input = useRef<HTMLInputElement>(null)
  const queries = useQueryClient()
  const save = useMutation({
    mutationFn: (file: File | null) => file ? uploadProfilePhoto(file) : removeProfilePhoto(),
    onSuccess: () => queries.invalidateQueries({ queryKey: ['profile-photo', profileId] }),
  })
  return (
    <section className="archive-panel space-y-3 p-4" aria-labelledby="profile-photo-title">
      <h2 id="profile-photo-title" className="font-semibold">Profile picture</h2>
      <p className="text-sm text-muted-foreground">Choose a photo from your phone. It is resized and kept private to this archive. Without one, your initial appears.</p>
      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" aria-label="Choose profile picture" className="sr-only" disabled={save.isPending} onChange={(event) => {
        const file = event.target.files?.[0]
        if (file) save.mutate(file)
        event.target.value = ''
      }} />
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" disabled={save.isPending} onClick={() => input.current?.click()}>Choose photo</Button>
        <Button type="button" variant="ghost" disabled={save.isPending} onClick={() => save.mutate(null)}>Use my initial</Button>
      </div>
      {save.isPending ? <p role="status">Saving picture…</p> : null}
      {save.isSuccess ? <p role="status">Profile picture saved.</p> : null}
      {save.isError ? <p role="alert" className="text-sm text-destructive">{queryErrorMessage(save.error, 'That picture could not be saved. Try again.')}</p> : null}
    </section>
  )
}
