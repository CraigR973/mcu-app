import type { AiConversation } from '@mcu/shared'
import { Trash2, X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { StatePanel } from '@/components/ui/state-panel'
import { cn } from '@/lib/utils'

interface Props {
  items: AiConversation[]
  selectedId: string | null
  loading: boolean
  error: string | null
  busy: boolean
  open: boolean
  onClose: () => void
  onSelect: (id: string) => void
  onDelete: (item: AiConversation) => void
  onReload: () => void
}

export function AssistantHistory({ items, selectedId, loading, error, busy, open, onClose, onSelect, onDelete, onReload }: Props) {
  return (
    <aside id="assistant-history" aria-label="Assistant conversations" className={cn('archive-panel min-h-0 flex-1 flex-col gap-3 p-3 md:w-64 md:flex-none', open ? 'flex' : 'hidden md:flex')}>
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-display text-lg font-semibold">Recent chats</h2>
        <Button type="button" variant="ghost" size="icon" className="md:hidden" aria-label="Back to conversation" onClick={onClose}><X aria-hidden /></Button>
      </div>
      <p className="text-xs text-muted-foreground">Your latest 50 chats. Only you can read them.</p>
      {loading ? <StatePanel compact tone="loading" title="Loading recent chats" /> : null}
      {error ? <StatePanel compact tone="error" title="Recent chats unavailable" description={error} action={<Button type="button" variant="outline" onClick={onReload}>Reload recent chats</Button>} /> : null}
      {!loading && !error && items.length === 0 ? <p className="text-sm text-muted-foreground">No saved chats yet. Your first question starts one.</p> : null}
      <ul aria-label="Conversation history" className="min-h-0 flex-1 space-y-1 overflow-y-auto">
        {items.map(item => (
          <li key={item.id} className="flex items-start gap-1">
            <button type="button" disabled={busy} aria-current={item.id === selectedId ? 'page' : undefined} onClick={() => onSelect(item.id)} className={cn('min-h-11 min-w-0 flex-1 rounded-md px-2 py-2 text-left text-sm hover:bg-muted disabled:opacity-50', item.id === selectedId && 'bg-primary/10 text-primary')}>
              <span className="block break-words [overflow-wrap:anywhere]">{item.title}</span>
              <time className="mt-1 block text-xs text-muted-foreground" dateTime={item.updatedAt}>{new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(item.updatedAt))}</time>
            </button>
            <Button type="button" variant="ghost" size="icon" aria-label={`Delete ${item.title}`} disabled={busy} onClick={() => onDelete(item)}><Trash2 aria-hidden /></Button>
          </li>
        ))}
      </ul>
    </aside>
  )
}
