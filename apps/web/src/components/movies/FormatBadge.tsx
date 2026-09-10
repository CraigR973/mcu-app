import { Badge } from '@/components/ui/badge'
import { formatLabel } from '@/lib/api'
import { cn } from '@/lib/utils'

const formatTones: Record<string, string> = {
  '4k_uhd': 'border-quality-4k/40 bg-quality-4k/14 text-quality-4k',
  'blu_ray': 'border-quality-bluray/40 bg-quality-bluray/14 text-quality-bluray',
  'dvd': 'border-quality-dvd/40 bg-quality-dvd/14 text-quality-dvd',
  'download': 'border-quality-digital/40 bg-quality-digital/14 text-quality-digital',
}

interface FormatBadgeProps {
  format: string
  className?: string
}

export function FormatBadge({ format, className }: FormatBadgeProps) {
  return (
    <Badge className={cn(formatTones[format], className)}>
      {formatLabel(format)}
    </Badge>
  )
}

