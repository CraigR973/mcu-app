import { useEffect, useState } from 'react'

import { bannerName, cachedBanner, loadBanner } from '@/lib/banner-cache'
import { cn } from '@/lib/utils'

/** The letters' own shape, 1125 × 292, so the box is right before the artwork arrives. */
const RATIO = 1125 / 292

/**
 * Home's banner — AC2, Craig's pick T1 (#337).
 *
 * The five photo letters alone, a transparent WebP of 58 KB at a phone's 3x width (100 KB at a
 * desktop's 2x), on a field the page draws in the theme's own colours: cream in light, the v3
 * crimson in dark. "Cinematic Universe" is real text, sharp at any size, where the v3 image
 * baked it in small. Before AC2 this was a 2 MB PNG behind a grey box.
 *
 * The artwork is still private (AA8), fetched with the person's token. After its first load it
 * comes from the device (`banner-cache.ts`), so Home shows no grey box again, and its box keeps
 * its shape either way.
 */
export function HomeBanner({ className }: { className?: string }) {
  const [name] = useState(bannerName)
  const [source, setSource] = useState<string | null>(() => cachedBanner(name))

  useEffect(() => {
    if (source) return
    let active = true
    void loadBanner(name)
      .then((url) => {
        if (active) setSource(url)
      })
      .catch(() => {
        // Decorative: a transient failure must never hide Home itself.
      })
    return () => {
      active = false
    }
  }, [name, source])

  return (
    <div role="img" aria-label="MARK'S Cinematic Universe" className={cn('home-banner-field overflow-hidden rounded-xl border border-border px-5 pb-4 pt-5 shadow-soft', className)}>
      <div style={{ aspectRatio: String(RATIO) }}>
        {source ? (
          <img src={source} alt="" draggable={false} className="block h-full w-full select-none object-contain" />
        ) : (
          <div aria-hidden className="h-full w-full animate-pulse rounded-md bg-muted/50" />
        )}
      </div>
      <div aria-hidden className="mt-3 flex items-center gap-3">
        <span className="h-px flex-1 bg-[hsl(var(--accent))]" />
        <span className="font-marquee text-[13px] font-bold uppercase tracking-[0.42em] text-accent dark:text-[hsl(var(--brand-cream))]">
          Cinematic Universe
        </span>
        <span className="h-px flex-1 bg-[hsl(var(--accent))]" />
      </div>
    </div>
  )
}
