import { useEffect, useState } from 'react'

import { authFetch } from '@/lib/auth-tokens'
import { cn } from '@/lib/utils'

type Hero = 'five' | 'single'

interface PrivateHeroProps {
  hero: Hero
  alt: string
  className?: string
}

/**
 * AA8's photo collage, fetched with the person's bearer token rather than exposed as a
 * public Vercel file. The object URL never reaches history, server logs, or an image URL.
 */
export function PrivateHero({ hero, alt, className }: PrivateHeroProps) {
  const [source, setSource] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    let objectUrl: string | null = null

    void authFetch(`/brand/heroes/${hero}`)
      .then(async (response) => {
        if (!response.ok) throw new Error('Brand artwork could not be loaded.')
        objectUrl = URL.createObjectURL(await response.blob())
        if (active) {
          setSource(objectUrl)
        } else {
          URL.revokeObjectURL(objectUrl)
        }
      })
      .catch(() => {
        // The banner is decorative. A transient network error must not hide Home itself.
      })

    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [hero])

  if (!source) return <div aria-hidden className={cn('animate-pulse bg-muted', className)} />

  return <img src={source} alt={alt} className={className} />
}
