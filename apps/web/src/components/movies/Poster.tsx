import { useState } from 'react'

import { posterUrl } from '@/lib/api'
import { cn } from '@/lib/utils'

interface PosterProps {
  path: string | null
  title: string
  size?: string
  decorative?: boolean
  className?: string
  eager?: boolean
}

/** One poster contract: 2:3 artwork, local fallback, useful alt text only when the
 * image is not already described by adjacent link text. */
export function Poster({ path, title, size = 'w342', decorative = false, className, eager = false }: PosterProps) {
  const [failed, setFailed] = useState(false)
  const src = failed ? '/placeholder-poster.svg' : posterUrl(path, size)

  return (
    <img
      src={src}
      alt={decorative ? '' : `${title} poster`}
      loading={eager ? 'eager' : 'lazy'}
      decoding="async"
      className={cn('aspect-[2/3] bg-muted object-cover', className)}
      onError={() => setFailed(true)}
    />
  )
}

