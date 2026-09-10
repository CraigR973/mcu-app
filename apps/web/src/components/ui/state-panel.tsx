import type { LucideIcon } from 'lucide-react'
import { AlertTriangle, CloudOff, Film, Loader2 } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

type StateTone = 'loading' | 'empty' | 'error' | 'offline'

const ICONS: Record<StateTone, LucideIcon> = {
  loading: Loader2,
  empty: Film,
  error: AlertTriangle,
  offline: CloudOff,
}

interface StatePanelProps {
  tone: StateTone
  title: string
  description?: ReactNode
  action?: ReactNode
  icon?: LucideIcon
  compact?: boolean
  className?: string
}

export function StatePanel({
  tone,
  title,
  description,
  action,
  icon,
  compact = false,
  className,
}: StatePanelProps) {
  const Icon = icon ?? ICONS[tone]
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      aria-live={tone === 'loading' ? 'polite' : undefined}
      className={cn('status-panel', compact && 'min-h-0 py-6', className)}
    >
      <span
        className={cn(
          'flex h-11 w-11 items-center justify-center rounded-full bg-muted text-muted-foreground',
          tone === 'error' && 'bg-destructive/10 text-destructive',
          tone === 'offline' && 'bg-warning/12 text-warning',
        )}
      >
        <Icon className={cn('h-5 w-5', tone === 'loading' && 'animate-spin')} aria-hidden />
      </span>
      <div>
        <p className="font-display text-lg font-semibold text-foreground">{title}</p>
        {description && <div className="mt-1 max-w-md text-sm leading-6 text-muted-foreground">{description}</div>}
      </div>
      {action}
    </div>
  )
}
