import { useQuery } from '@tanstack/react-query'
import { ChevronRight, ListChecks } from 'lucide-react'
import { Link } from 'react-router-dom'

import { StatePanel } from '@/components/ui/state-panel'
import { useAuth } from '@/context/auth'
import { fetchNeedsYou, posterUrl } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { needsYouCopy } from '@/lib/needs-you'

/** How many items the row shows before it points at Loans for the rest. */
const SHOWN = 5

/**
 * AC1 (#335): what the person signed in can act on now, at the top of Home, for everyone.
 *
 * The API decides who sees what from the loan rows on every read, so a disc confirmed shelved
 * leaves everyone's row at once. Hidden while it loads and when there is nothing to do; a
 * failed or offline read says so, because a hidden row would read as "nothing needs you".
 * Craig's operational "Needs attention" row is separate and stays his alone.
 */
export function NeedsYouRow() {
  const { profile } = useAuth()
  const query = useQuery({
    queryKey: ['needs-you', profile?.id],
    queryFn: fetchNeedsYou,
    enabled: Boolean(profile),
  })
  const items = query.data?.items ?? []
  const state = listState(query, items.length === 0)
  if (!profile || state === 'loading' || state === 'empty') return null
  if (state === 'offline') {
    return <StatePanel compact tone="offline" title="What needs you is not cached here" description="Reconnect to see which discs are waiting on you." />
  }
  if (state === 'error') {
    return (
      <StatePanel
        compact
        tone="error"
        title="Could not check what needs you"
        description={queryErrorMessage(query.error, 'Could not load the discs waiting on you.')}
      />
    )
  }
  return (
    <section aria-labelledby="needs-you-heading" className="archive-panel p-4">
      <h2 id="needs-you-heading" className="flex items-center gap-2 font-display text-base font-semibold text-foreground">
        <ListChecks aria-hidden className="size-4 text-primary" />
        Needs you
        {/* The list already says how many; the count is for the eye. */}
        <span aria-hidden className="rounded-full bg-primary/15 px-2 py-0.5 text-xs font-semibold text-primary">
          {items.length}
        </span>
      </h2>
      <ul className="mt-2 divide-y divide-border">
        {items.slice(0, SHOWN).map((item) => {
          const copy = needsYouCopy(item)
          return (
            <li key={`${item.kind}:${item.loanId}`}>
              <Link
                to={copy.to}
                className="touch-target flex min-h-14 items-center gap-3 py-2.5 text-foreground hover:text-primary"
              >
                <img
                  src={posterUrl(item.posterPath, 'w92')}
                  alt=""
                  loading="lazy"
                  className="h-12 w-8 shrink-0 rounded-sm border border-border object-cover"
                />
                <span className="min-w-0 flex-1">
                  <span className="line-clamp-2 text-sm font-semibold">{copy.title}</span>
                  <span className="mt-0.5 block text-xs text-muted-foreground">{copy.detail}</span>
                </span>
                <ChevronRight aria-hidden className="size-4 shrink-0 text-muted-foreground" />
              </Link>
            </li>
          )
        })}
      </ul>
      {items.length > SHOWN ? (
        <Link to="/loans" className="mt-2 inline-block text-sm font-medium text-primary underline-offset-2 hover:underline">
          See all {items.length} on Loans
        </Link>
      ) : null}
    </section>
  )
}
