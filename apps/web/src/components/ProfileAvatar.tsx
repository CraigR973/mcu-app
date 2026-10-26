import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { fetchProfilePhoto } from '@/lib/api'
import { cn } from '@/lib/utils'

/** Private bytes deduplicated per person; every object URL is released on replacement/unmount. */
export function ProfileAvatar({ profileId, name, className }: { profileId?: string | null; name?: string | null; className?: string }) {
  const photo = useQuery({
    queryKey: ['profile-photo', profileId],
    queryFn: () => fetchProfilePhoto(profileId!),
    enabled: Boolean(profileId),
    staleTime: 60_000,
    retry: false,
  })
  const [image, setImage] = useState<{ blob: Blob; url: string } | null>(null)
  const [failed, setFailed] = useState<string | null>(null)
  useEffect(() => {
    if (!photo.data) return
    const url = URL.createObjectURL(photo.data)
    setImage({ blob: photo.data, url })
    return () => { URL.revokeObjectURL(url) }
  }, [photo.data])
  const url = image?.blob === photo.data ? image?.url : null
  return (
    <span aria-hidden className={cn('inline-flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full bg-secondary font-display font-semibold text-secondary-foreground', className)}>
      {url && failed !== url ? <img src={url} alt="" className="h-full w-full object-cover" onError={() => setFailed(url)} /> : name?.slice(0, 1).toUpperCase() ?? '?'}
    </span>
  )
}
