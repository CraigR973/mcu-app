import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { Poster } from '@/components/movies/Poster'

/**
 * A row of Home — Batch W2, snag 3 (`DECISIONS.md` #249: "make all the sections look like
 * highlights so it is a carousel").
 *
 * A heading, an optional line under it and an optional link beside it, then cards that
 * scroll sideways and snap, as V5's Highlights rows did. **On a phone the row runs to the
 * screen's edges**, so the next card shows at the edge and says there is more, while the
 * first card still lines up with the page's text (the negative margins undo
 * `page-shell-narrow`'s padding at each width, and `scroll-px` puts it back for snapping).
 */
export function ShelfHeading({
  id,
  title,
  icon: Icon,
  caption,
  action,
}: {
  id: string
  title: string
  icon?: LucideIcon
  caption?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="flex items-end justify-between gap-3">
      <div className="min-w-0">
        <h2 id={id} className="section-heading flex items-center gap-2 text-lg">
          {Icon ? <Icon className="h-5 w-5 shrink-0 text-primary" aria-hidden /> : null}
          {title}
        </h2>
        {caption ? <p className="mt-0.5 text-xs leading-5 text-muted-foreground">{caption}</p> : null}
      </div>
      {action ? <div className="shrink-0 pb-0.5 text-sm font-semibold">{action}</div> : null}
    </div>
  )
}

/** The sideways row itself, for a section with more than one (The collection has two). */
export function ShelfRow({ label, children }: { label?: string; children: ReactNode }) {
  return (
    <ul
      aria-label={label}
      className="-mx-4 flex snap-x scroll-px-4 gap-3 overflow-x-auto px-4 pb-2 sm:-mx-6 sm:scroll-px-6 sm:px-6 lg:-mx-8 lg:scroll-px-8 lg:px-8"
    >
      {children}
    </ul>
  )
}

/** A titled section of one sideways row. */
export function Shelf({
  id,
  title,
  icon,
  caption,
  action,
  children,
}: {
  id: string
  title: string
  icon?: LucideIcon
  caption?: ReactNode
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section aria-labelledby={id} className="space-y-3">
      <ShelfHeading id={id} title={title} icon={icon} caption={caption} action={action} />
      <ShelfRow>{children}</ShelfRow>
    </section>
  )
}

/** "All releases", "All 40": the link beside a row's heading. */
export function ShelfLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="text-primary hover:underline">
      {children}
    </Link>
  )
}

/** A film's poster, its title and a line about it; it opens the film's page when it has one. */
export function PosterCard({
  to,
  title,
  posterPath,
  detail,
}: {
  to: string | null
  title: string
  posterPath: string | null
  detail?: ReactNode
}) {
  const body = (
    <>
      <Poster
        path={posterPath}
        title={title}
        size="w154"
        decorative
        className="aspect-[2/3] w-full rounded-md border border-border object-cover"
      />
      <span className="mt-1.5 block line-clamp-2 text-xs font-semibold leading-4 text-foreground group-hover:text-primary">
        {title}
      </span>
      {detail ? <span className="mt-0.5 block text-xs leading-4 text-muted-foreground">{detail}</span> : null}
    </>
  )
  return (
    <li className="w-24 shrink-0 snap-start sm:w-28">
      {to ? (
        <Link to={to} className="group block rounded-md">
          {body}
        </Link>
      ) : (
        <div>{body}</div>
      )}
    </li>
  )
}
