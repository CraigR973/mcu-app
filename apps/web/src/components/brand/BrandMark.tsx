import { useTheme } from '@/context/theme'
import { cn } from '@/lib/utils'

/**
 * The square identity mark.
 *
 * The approved system is responsive by *drawn* artwork, not by scaling one file: each tier
 * below is a separately drawn master, because the detail that makes the concept art
 * ownable at 192 px becomes noise at 32 px, and the geometry that survives 32 px is too
 * heavy at 128 px. `docs/brand/logo-system/stack-family/README.md` is the source of truth.
 *
 * | Rendered size | Artwork |
 * |---|---|
 * | >= 28 px | original screen-print emblem |
 * | < 28 px | pixel-hinted micro mark |
 *
 * The screen-print emblem has one approved field and no light variant — that is deliberate,
 * not an omission. The favicon and notification badge use the micro mark directly.
 */

const CONCEPT_ART = '/brand/app-icon-concept-art-512.png'
const MICRO = '/brand/micro-mark-16.svg'

/** Exported for the unit test: the tier table is the part worth pinning down. */
export function markAsset(size: number, theme: 'light' | 'dark'): string {
  void theme
  if (size >= 28) return CONCEPT_ART
  return MICRO
}

interface BrandMarkProps {
  /** Rendered edge length in CSS pixels. Selects the artwork tier. */
  size: number
  /**
   * Accessible name. Omit when visible brand text sits beside the mark — a logo repeating
   * the words next to it is read twice by a screen reader.
   */
  label?: string
  className?: string
}

export function BrandMark({ size, label, className }: BrandMarkProps) {
  const { resolvedTheme } = useTheme()

  return (
    <img
      src={markAsset(size, resolvedTheme)}
      alt={label ?? ''}
      width={size}
      height={size}
      // Both the attributes and the inline size: the attributes give the box an intrinsic
      // ratio before the file arrives, and the style keeps it there once a stylesheet with
      // its own `img` rules has loaded. Between them nothing reflows as the mark decodes.
      style={{ width: size, height: size }}
      decoding="async"
      draggable={false}
      className={cn('shrink-0 select-none', className)}
    />
  )
}
