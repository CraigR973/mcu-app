import { Dialog } from '@/components/ui/dialog'

interface Props {
  open: boolean
  onClose: () => void
  isAdmin: boolean
}

interface Row {
  keys: string
  action: string
  adminOnly?: boolean
}

const ROWS: Row[] = [
  { keys: '⌘K / Ctrl K', action: 'Open command palette' },
  { keys: '/', action: 'Focus search' },
  { keys: '?', action: 'Show all shortcuts' },
  { keys: '.', action: 'Open the assistant' },
  { keys: 'g then h', action: 'Go to home' },
  { keys: 'g then c', action: 'Go to collection' },
  { keys: 'g then w', action: 'Go to wanted list' },
  { keys: 'g then s', action: 'Go to settings' },
  { keys: 'n', action: 'Add new item', adminOnly: true },
  { keys: 'Esc', action: 'Close modal / clear search' },
]

/** §7.5's help modal, triggered by `?`. */
export default function ShortcutsHelpModal({ open, onClose, isAdmin }: Props) {
  const rows = ROWS.filter((row) => !row.adminOnly || isAdmin)

  return (
    <Dialog open={open} onClose={onClose} label="Keyboard shortcuts">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">Keyboard shortcuts</h2>
      </div>
      <table className="w-full text-sm">
        <tbody>
          {rows.map((row) => (
            <tr key={row.keys} className="border-b border-border last:border-0">
              <td className="w-40 px-4 py-2">
                <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                  {row.keys}
                </kbd>
              </td>
              <td className="px-4 py-2 text-foreground">{row.action}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Dialog>
  )
}
