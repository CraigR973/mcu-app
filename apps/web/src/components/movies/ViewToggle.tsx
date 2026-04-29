import { LayoutGrid, List, AlignJustify } from 'lucide-react'
import { ViewMode } from '../../hooks/useViewPreference'

interface Props {
  value: ViewMode
  onChange: (mode: ViewMode) => void
}

const MODES: { mode: ViewMode; icon: React.ReactNode; label: string }[] = [
  { mode: 'grid',    icon: <LayoutGrid size={16} />,   label: 'Grid' },
  { mode: 'list',    icon: <List size={16} />,          label: 'List' },
  { mode: 'compact', icon: <AlignJustify size={16} />, label: 'Compact' },
]

export function ViewToggle({ value, onChange }: Props) {
  return (
    <div className="flex items-center rounded-md border border-zinc-700 overflow-hidden">
      {MODES.map(({ mode, icon, label }) => (
        <button
          key={mode}
          title={label}
          onClick={() => onChange(mode)}
          className={[
            'flex items-center justify-center px-2.5 py-1.5 transition-colors',
            value === mode
              ? 'bg-zinc-600 text-white'
              : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200',
          ].join(' ')}
        >
          {icon}
        </button>
      ))}
    </div>
  )
}
