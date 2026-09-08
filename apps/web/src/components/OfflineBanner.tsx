import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, CloudOff, Loader2, RefreshCw, Trash2, WifiOff } from 'lucide-react'

import { useOnlineStatus } from '@/hooks/useOnlineStatus'
import { useSyncQueue } from '@/hooks/useSyncQueue'
import { discardQueued, flushQueue, retryQueued } from '@/lib/sync'

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
      : 'bg-amber-500/15 border-amber-500/40 text-foreground'

  return (
    <div role="status" aria-live="polite" data-testid="offline-banner" className={`border-b ${tone}`}>
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
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            className="rounded-md px-2 py-1 text-xs font-medium underline-offset-2 hover:underline"
          >
            {open ? 'Hide' : 'Show'} {pending === 1 ? 'change' : 'changes'}
          </button>
        )}

        {isOnline && pending > 0 && (
          <button
            type="button"
            onClick={() => void sync()}
            disabled={syncing}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-2.5 py-1 text-xs font-semibold text-primary-foreground disabled:opacity-60"
          >
            {syncing ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <RefreshCw className="h-3 w-3" />
            )}
            Sync now
          </button>
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
                  <button
                    type="button"
                    onClick={() => void retryQueued(entry.id!)}
                    className="rounded px-2 py-0.5 font-medium text-primary hover:underline"
                  >
                    Try again
                  </button>
                )}
                {entry.id !== undefined && (
                  <button
                    type="button"
                    onClick={() => void discardQueued(entry.id!)}
                    aria-label="Discard this change"
                    className="text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
