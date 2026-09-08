import { useCallback, useEffect, useState } from 'react'

import { listQueue, queueIsAvailable, type QueuedWrite } from '@/lib/offline-queue'
import { subscribeToQueue } from '@/lib/sync'

interface SyncQueue {
  entries: QueuedWrite[]
  /** Entries the person has to decide about — the server refused them. */
  blocked: QueuedWrite[]
  pending: number
  refresh: () => void
}

/**
 * The queue, as the UI reads it.
 *
 * Subscribes rather than polls: every mutation that touches the queue announces, so the
 * banner and the sync panel update without a timer running on a phone in someone's pocket.
 */
export function useSyncQueue(): SyncQueue {
  const [entries, setEntries] = useState<QueuedWrite[]>([])

  const refresh = useCallback(() => {
    if (!queueIsAvailable()) return
    void listQueue().then(setEntries)
  }, [])

  useEffect(() => {
    refresh()
    return subscribeToQueue(refresh)
  }, [refresh])

  return {
    entries,
    blocked: entries.filter((entry) => entry.error !== undefined),
    pending: entries.length,
    refresh,
  }
}
