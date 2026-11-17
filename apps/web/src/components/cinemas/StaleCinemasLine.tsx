import { AlertTriangle } from 'lucide-react'

import { staleCinemasLine, type ProgrammeVenue } from '@/lib/cinemas'
import { cn } from '@/lib/utils'

/**
 * AG3 (CT52-01, UX54-01): "4 cinemas not read since Wed 11 Nov", said where people look: at the
 * top of At the cinema, beside its cinema filter, and under Home's strip heading. It asks the one
 * stale test (`lib/cinemas.ts`), the film page's, and says nothing while every cinema is current.
 */
export function StaleCinemasLine({ venues, now, compact = false, className }: { venues: ProgrammeVenue[]; now: number; compact?: boolean; className?: string }) {
  const line = staleCinemasLine(venues, now)
  if (!line) return null
  return (
    <p
      role="status"
      className={cn(
        'flex items-start gap-2 text-foreground',
        compact ? 'text-xs leading-5' : 'rounded-md border border-warning/50 bg-warning/10 p-3 text-sm',
        className,
      )}
    >
      <AlertTriangle className={cn('shrink-0 text-warning', compact ? 'mt-0.5 h-3.5 w-3.5' : 'mt-0.5 h-4 w-4')} aria-hidden />
      <span><span className="font-semibold">{line}.</span>{compact ? '' : ' Their times may be out of date; check the official programmes.'}</span>
    </p>
  )
}
