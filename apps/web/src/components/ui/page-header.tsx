import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

import { usePageTitle } from '@/components/layouts/page-chrome'
import { cn } from '@/lib/utils'

interface PageHeaderProps {
  title: ReactNode
  eyebrow?: ReactNode
  description?: ReactNode
  meta?: ReactNode
  actions?: ReactNode
  backTo?: string
  backLabel?: string
  className?: string
}

/**
 * A page's name, and what it does.
 *
 * **Batch T3, snag 1: below 1024px the words move to the top bar.** A phone used to spend
 * a kicker, a large title and a line of description above every page — the same block, on
 * every page, before anything the page was for. Now the title is announced to the shell
 * and shown there, the back link becomes the top bar's arrow, and this renders only its
 * actions. A header with no actions renders nothing at all on a phone. Desktop is unchanged.
 */
export function PageHeader({
  title,
  eyebrow,
  description,
  meta,
  actions,
  backTo,
  backLabel = 'Back',
  className,
}: PageHeaderProps) {
  usePageTitle(typeof title === 'string' ? title : null)

  // `meta` stays on a phone: it carries facts, not decoration — "2 overdue" on Loans,
  // "11 still being sought" on Wanted.
  const showsOnPhone = Boolean(actions) || Boolean(meta)

  return (
    <header className={cn('page-header', !showsOnPhone && 'hidden lg:flex', className)}>
      <div className="min-w-0">
        <div className="hidden lg:block">
          {backTo && (
            <Link
              to={backTo}
              className="mb-4 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden />
              {backLabel}
            </Link>
          )}
          {eyebrow && <p className="page-kicker eyebrow-rule">{eyebrow}</p>}
          <h1 className="page-title">{title}</h1>
          {description && <div className="page-description">{description}</div>}
        </div>
        {meta && <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground lg:mt-3">{meta}</div>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}
