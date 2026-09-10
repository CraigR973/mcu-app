import type { HTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

type BadgeTone = 'neutral' | 'primary' | 'success' | 'warning' | 'danger' | 'info'

const tones: Record<BadgeTone, string> = {
  neutral: 'border-border bg-muted text-foreground',
  primary: 'border-primary/30 bg-primary/12 text-primary',
  success: 'border-success/30 bg-success/12 text-success',
  warning: 'border-warning/35 bg-warning/12 text-warning',
  danger: 'border-destructive/35 bg-destructive/12 text-destructive',
  info: 'border-info/35 bg-info/12 text-info',
}

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone
}

export function Badge({ className, tone = 'neutral', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex min-h-5 items-center rounded-sm border px-1.5 py-0.5 text-[0.6875rem] font-semibold leading-none',
        tones[tone],
        className,
      )}
      {...props}
    />
  )
}

