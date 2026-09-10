import { LayoutGrid, List, AlignJustify } from 'lucide-react'
import type { ViewMode } from '../../hooks/useViewPreference'

interface Props {
  value: ViewMode
  onChange: (mode: ViewMode) => void
}

const MODES: { mode: ViewMode; icon: React.ReactNode; label: string }[] = [
  { mode: 'grid', icon: <LayoutGrid size={16} aria-hidden />, label: 'Grid' },
  { mode: 'list', icon: <List size={16} aria-hidden />, label: 'List' },
  { mode: 'compact', icon: <AlignJustify size={16} aria-hidden />, label: 'Compact' },
]

export function ViewToggle({ value, onChange }: Props) {
  return (
    <div className="flex items-center overflow-hidden rounded-md border border-input bg-card" role="group" aria-label="Collection layout">
      {MODES.map(({ mode, icon, label }) => (
        <button
          key={mode}
          type="button"
          aria-label={`${label} view`}
          aria-pressed={value === mode}
          onClick={() => onChange(mode)}
          className={[
            'touch-target flex min-h-11 items-center justify-center gap-2 border-r border-border px-3 text-sm font-semibold transition-colors last:border-r-0',
            value === mode
              ? 'bg-primary/12 text-primary'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground',
          ].join(' ')}
        >
          {icon}
          <span className="hidden xl:inline">{label}</span>
        </button>
      ))}
    </div>
  )
}
