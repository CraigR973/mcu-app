import { useQuery } from '@tanstack/react-query'
import { BellOff, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useAuth } from '@/context/auth'
import { fetchOwnAttention } from '@/lib/api'

/**
 * AG3 (UX54-02): a person's own Home says when their phone is not getting notifications, which
 * the daily check used to tell only the admin. Worked out as it is read, so it goes the moment
 * notifications are turned on. For both people; a failed or offline read says nothing, since a
 * missing notice must not read as a problem of its own.
 */
export function PhoneNotice() {
  const { profile } = useAuth()
  const query = useQuery({ queryKey: ['own-attention', profile?.id], queryFn: fetchOwnAttention, enabled: Boolean(profile) })
  const trouble = query.data?.notifications
  if (!trouble) return null
  return (
    <Link
      to="/settings?tab=notifications"
      className="archive-panel flex min-h-14 items-center gap-3 border-warning/50 p-4 text-foreground hover:text-primary"
    >
      <span aria-hidden className="flex size-10 shrink-0 items-center justify-center rounded-full bg-warning/15 text-warning">
        <BellOff className="size-5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold">
          {trouble === 'noDevice' ? 'This phone is not getting notifications' : 'Your notifications are not reaching a phone'}
        </span>
        <span className="block text-xs text-muted-foreground">
          {trouble === 'noDevice' ? 'Cinema trips, loans and finds will not reach you.' : 'None sent in the last three days arrived.'} · Turn on
        </span>
      </span>
      <ChevronRight aria-hidden className="size-4 shrink-0 text-muted-foreground" />
    </Link>
  )
}
