import { useTheme } from '@/context/theme'
import { cn } from '@/lib/utils'

/**
 * The mark and the wordmark together.
 *
 * Two approved arrangements, each with its own minimum width. The minimums are about the
 * `CINEMATIC UNIVERSE` subtitle: below them its cap height drops under about 6 px and it
 * stops being words. They are enforced in development rather than merely documented,
 * because a lockup quietly shrunk to fit a container is the usual way an identity decays.
 *
 * A call site that genuinely has to go under states why in `underMinimumReason`; the
 * string is there to be read in review, not to silence a warning cheaply.
 */

const VARIANTS = {
  horizontal: {
    /** `docs/brand/logo-system/stack-family/README.md` — navigation, footer, wide positions. */
    minimumWidth: 280,
    aspect: 1600 / 420,
    dark: '/brand/horizontal-lockup-dark.svg',
    light: '/brand/horizontal-lockup-light.svg',
  },
  stacked: {
    /** Square login, onboarding and profile contexts. */
    minimumWidth: 320,
    aspect: 1,
    dark: '/brand/stacked-lockup-dark.svg',
    light: '/brand/stacked-lockup-light.svg',
  },
} as const

export type LockupVariant = keyof typeof VARIANTS

interface BrandLockupProps {
  variant: LockupVariant
  /** Rendered width in CSS pixels. Defaults to the approved minimum for the variant. */
  width?: number
  /**
   * Accessible name. Omit only where the lockup is genuinely decorative — it contains the
   * app's name, so on a page that does not otherwise say it, this is the name.
   */
  label?: string
  /** Why this instance renders below the approved minimum. Required if it does. */
  underMinimumReason?: string
  className?: string
}

export function BrandLockup({
  variant,
  width,
  label,
  underMinimumReason,
  className,
}: BrandLockupProps) {
  const { resolvedTheme } = useTheme()
  const spec = VARIANTS[variant]
  const renderedWidth = width ?? spec.minimumWidth
  const renderedHeight = Math.round(renderedWidth / spec.aspect)

  if (import.meta.env.DEV && renderedWidth < spec.minimumWidth && !underMinimumReason) {
    console.warn(
      `BrandLockup: the ${variant} lockup is drawn at ${renderedWidth}px against an approved ` +
        `minimum of ${spec.minimumWidth}px. Use a BrandMark plus text, or pass ` +
        '`underMinimumReason` to record the trade-off.',
    )
  }

  return (
    <img
      src={resolvedTheme === 'dark' ? spec.dark : spec.light}
      alt={label ?? ''}
      width={renderedWidth}
      height={renderedHeight}
      // Reserving both axes keeps the surrounding column from jumping while the SVG
      // decodes — the login panel and the onboarding card both size themselves off it.
      style={{ width: renderedWidth, height: renderedHeight }}
      decoding="async"
      draggable={false}
      className={cn('block max-w-full select-none', className)}
    />
  )
}
