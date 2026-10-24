import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useAuth } from '@/context/auth'
import { Button } from '@/components/ui/button'
import { clearCraigNote, fetchAttention, type Attention } from '@/lib/api'
import { formatDayMonth } from '@/lib/utils'

type AttentionDestination = { to: string; label: string } | { advice: string }

/** AA2: every health-check key has one repair destination, or honest owner guidance. */
export function attentionDestination(key: string): AttentionDestination {
  if (key.startsWith('job:')) return { to: '/admin', label: 'Open Admin jobs' }
  if (key === 'ebay:listings') return { to: '/settings', label: 'Open eBay settings' }
  if (key.endsWith(':notifications')) return { to: '/settings', label: 'Open device settings' }
  if (key === 'specs:halted') return { to: '/specs', label: 'Open Disc specs' }
  if (key.endsWith(':lockout')) return { to: '/settings', label: 'Open Settings' }
  if (key.startsWith('identify:')) return { to: '/identify', label: 'Open Identify films' }
  if (key === 'deals:freshness') return { to: '/retailers', label: 'Open Retailers' }
  if (key === 'assistant:failures') return { to: '/assistant', label: 'Open Assistant settings' }
  if (key === 'api:readiness') return { advice: 'Ask Craig to complete the server set-up.' }
  if (key === 'database:size') return { advice: 'Ask Craig to review the database size.' }
  if (key === 'check:stale') return { to: '/admin', label: 'Open Admin jobs' }
  return { advice: 'Ask Craig to review this check.' }
}

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

/** Batch X12a: a line from Mark stays until Craig has read it and says so. */
function ClearNote({ noteId }: { noteId: string }) {
  const queryClient = useQueryClient()
  const clear = useMutation({
    mutationFn: () => clearCraigNote(noteId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['attention'] }),
  })
  return (
    <Button
      type="button"
      size="sm"
      variant="outline"
      className="ml-2 align-middle"
      disabled={clear.isPending}
      onClick={() => clear.mutate()}
    >
      Clear
    </Button>
  )
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
            {item.noteId ? <ClearNote noteId={item.noteId} /> : null}
            {!item.noteId ? <AttentionAction destination={attentionDestination(item.key)} /> : null}
          </li>
        ))}
      </ul>
    </section>
  )
}

function AttentionAction({ destination }: { destination: AttentionDestination }) {
  if ('advice' in destination) return <span className="text-muted-foreground"> · {destination.advice}</span>
  return <Link to={destination.to} className="ml-2 underline underline-offset-2">{destination.label}</Link>
}
