import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, CloudOff, Loader2, RefreshCw, Trash2, WifiOff } from 'lucide-react'

import { useOnlineStatus } from '@/hooks/useOnlineStatus'
import { useSyncQueue } from '@/hooks/useSyncQueue'
import { discardQueued, flushQueue, retryQueued } from '@/lib/sync'
import { Button } from '@/components/ui/button'

/**
 * What the app says about the network and about writes it is still holding.
 *
 * Deliberately a **banner and a panel, not a toast.** A toast is right for something that
 * happened and is over; every state here is one that is still true and that the person
 * may need to act on — the connection is gone, three changes are waiting, one was
 * refused. `the-coupon` uses toasts because a pick is a single moment; a catalogue of
 * pending edits is a list.
 */
export default function OfflineBanner() {
  const isOnline = useOnlineStatus()
  const { entries, blocked, pending } = useSyncQueue()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [syncing, setSyncing] = useState(false)

  async function sync() {
    setSyncing(true)
    try {
      await flushQueue()
      // Anything that landed changes the collection, the counts and the shelf facets.
      void queryClient.invalidateQueries({ queryKey: ['movies'] })
      void queryClient.invalidateQueries({ queryKey: ['search'] })
      void queryClient.invalidateQueries({ queryKey: ['facets'] })
      void queryClient.invalidateQueries({ queryKey: ['movie-copies'] })
      void queryClient.invalidateQueries({ queryKey: ['trash'] })
    } finally {
      setSyncing(false)
    }
  }

  if (isOnline && pending === 0) return null

  const tone = blocked.length > 0
    ? 'bg-destructive/15 border-destructive/40 text-foreground'
    : isOnline
      ? 'bg-primary/10 border-primary/30 text-foreground'
      : 'bg-warning/12 border-warning/40 text-foreground'

  return (
    <div role={blocked.length > 0 ? 'alert' : 'status'} aria-live="polite" data-testid="offline-banner" className={`border-b ${tone}`}>
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-3 px-4 py-2 text-sm">
        {blocked.length > 0 ? (
          <AlertTriangle className="h-4 w-4 shrink-0 text-destructive" />
        ) : isOnline ? (
          <CloudOff className="h-4 w-4 shrink-0" />
        ) : (
          <WifiOff className="h-4 w-4 shrink-0" />
        )}

        <span className="flex-1">
          {!isOnline && 'You’re offline. You can still browse, and any changes are saved on this device.'}
          {isOnline && blocked.length > 0 && (
            <>
              {blocked.length === 1 ? 'One change needs' : `${blocked.length} changes need`} your
              attention before it can be saved.
            </>
          )}
          {isOnline && blocked.length === 0 && pending > 0 && (
            <>
              {pending === 1 ? 'One change is' : `${pending} changes are`} waiting to sync.
            </>
          )}
        </span>

        {pending > 0 && (
          <Button
            type="button"
            onClick={() => setOpen((value) => !value)}
            variant="ghost"
            size="sm"
          >
            {open ? 'Hide' : 'Show'} {pending === 1 ? 'change' : 'changes'}
          </Button>
        )}

        {isOnline && pending > 0 && (
          <Button
            type="button"
            onClick={() => void sync()}
            disabled={syncing}
            size="sm"
          >
            {syncing ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <RefreshCw className="h-3 w-3" />
            )}
            Sync now
          </Button>
        )}
      </div>

      {open && pending > 0 && (
        <ul className="mx-auto max-w-5xl space-y-1.5 px-4 pb-3">
          {entries.map((entry) => (
            <li
              key={entry.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-background/70 px-3 py-2 text-xs"
            >
              <span className="min-w-0">
                <span className="font-medium text-foreground">{entry.label}</span>
                {/* The distinction the whole queue is built on, said plainly. */}
                <span className="ml-2 text-muted-foreground">
                  {entry.error !== undefined
                    ? entry.error
                    : entry.state === 'unconfirmed'
                      ? 'Sent, but we never heard back — we’ll check rather than send it twice.'
                      : 'Waiting to send.'}
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-2">
                {entry.error !== undefined && entry.id !== undefined && (
                  <Button
                    type="button"
                    onClick={() => void retryQueued(entry.id!)}
                    variant="ghost"
                    size="sm"
                  >
                    Try again
                  </Button>
                )}
                {entry.id !== undefined && (
                  <Button
                    type="button"
                    onClick={() => void discardQueued(entry.id!)}
                    aria-label="Discard this change"
                    variant="ghost"
                    size="icon"
                  >
                    <Trash2 className="h-4 w-4 text-muted-foreground" aria-hidden />
                  </Button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
