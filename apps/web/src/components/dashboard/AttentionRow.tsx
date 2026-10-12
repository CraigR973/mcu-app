import { useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'

import { useAuth } from '@/context/auth'
import { fetchAttention, type Attention } from '@/lib/api'
import { formatDayMonth } from '@/lib/utils'

/**
 * Batch X2 (DS44-01, UX48-02): what has stopped, at the top of Home, for Craig.
 *
 * None of the seven failures between 9 Sep and 11 Oct reached anyone; each was found days
 * later by someone looking. The daily check (08:00 UTC) records each problem, and this row
 * names them in words. It reads the database, so it works when push is what broke.
 *
 * Hidden when there is nothing wrong, and for Mark, who has nothing here to act on. A failed
 * read hides it too: Home's other rows say when the archive itself is unreachable.
 */
export function AttentionRow() {
  const { profile } = useAuth()
  const isAdmin = profile?.role === 'admin'
  const query = useQuery({ queryKey: ['attention'], queryFn: fetchAttention, enabled: isAdmin })
  if (!isAdmin || !query.data) return null
  return <AttentionList attention={query.data} />
}

export function AttentionList({ attention }: { attention: Attention }) {
  if (attention.items.length === 0) return null
  return (
    <section
      aria-labelledby="attention-heading"
      className="archive-panel space-y-2 border-warning/60 p-4"
    >
      <h2
        id="attention-heading"
        className="flex items-center gap-2 font-display text-base font-semibold text-foreground"
      >
        <AlertTriangle aria-hidden className="size-4 text-warning" />
        Needs attention
      </h2>
      <ul className="space-y-1.5 text-sm text-foreground">
        {attention.items.map((item) => (
          <li key={item.key} className="break-words">
            {item.message}
            {/* A message that already says since when ("… (since 9 Oct).") needs no suffix. */}
            {item.since && !item.message.includes('since ') ? (
              <span className="text-muted-foreground"> · since {formatDayMonth(item.since)}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  )
}
