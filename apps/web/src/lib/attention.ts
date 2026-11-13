import type { Attention } from '@mcu/shared'

import type { NeedsYouRowData } from './needs-you'
import { formatDayMonth } from './utils'

export type AttentionDestination = { to: string; label: string } | { advice: string }

/** AA2: every health-check key has one repair destination, or honest owner guidance. */
export function attentionDestination(key: string, currentPersonId?: string): AttentionDestination {
  if (key === 'job:cron-specs') return { to: '/specs', label: 'Open Disc specs' }
  if (key === 'job:cron-values') return { to: '/valuation', label: 'Open Collection value' }
  if (key === 'job:cron-scrape') return { to: '/retailers', label: 'Open Retailers' }
  if (key.startsWith('job:') || key === 'check:stale') {
    return { advice: 'Ask Craig to check this scheduled job in Railway.' }
  }
  if (key === 'ebay:listings') return { to: '/settings?tab=ebay', label: 'Open eBay settings' }
  if (key.endsWith(':notifications')) {
    if (currentPersonId && key === `person:${currentPersonId}:notifications`) {
      return { to: '/settings?tab=notifications', label: 'Open your device settings' }
    }
    return { advice: 'Ask this person to open Settings → Notifications on their own phone.' }
  }
  if (key === 'specs:halted') return { to: '/specs', label: 'Open Disc specs' }
  if (key.endsWith(':lockout')) return { advice: 'Ask Craig to review the PIN lock; Settings cannot clear it.' }
  if (key === 'identify:year-doubt') return { to: '/identify#identify-doubts-heading', label: 'Open films in doubt' }
  if (key.startsWith('identify:')) return { to: '/identify', label: 'Open Identify films' }
  if (key === 'deals:freshness') return { to: '/retailers', label: 'Open Retailers' }
  if (key === 'assistant:failures') return { to: '/settings?tab=assistant', label: 'Open Assistant settings' }
  if (key === 'api:readiness') return { advice: 'Ask Craig to complete the server set-up.' }
  if (key === 'database:size') return { advice: 'Ask Craig to review the database size.' }
  return { advice: 'Ask Craig to review this check.' }
}

/**
 * Craig's "Needs attention" as rows of his Needs you — AF1 (#372), superseding Batch X2's row of
 * its own on Home.
 *
 * A problem the daily check found is a row labelled App, in the API's order, opening where its
 * line in Needs attention opened, or saying what to do where there is nowhere to open. A line
 * sent with "Tell Craig" is a row from its sender, in their words, with Clear. Only Craig reads
 * these: the attention read is his alone, and Mark's Needs you never asks for it.
 */
export function attentionRows(attention: Attention, readerId?: string): NeedsYouRowData[] {
  return attention.items.map((item): NeedsYouRowData => {
    if (item.noteId) {
      return {
        key: item.key,
        kind: 'note',
        title: item.body ?? item.message,
        detail: item.since ? `Tell Craig · ${formatDayMonth(item.since)}` : 'Tell Craig',
        to: null,
        poster: null,
        film: '',
        label: item.fromName ?? 'Someone',
        own: false,
        ownerId: item.fromProfileId,
        noteId: item.noteId,
      }
    }
    const destination = attentionDestination(item.key, readerId)
    // A message that already says since when ("… (since 9 Oct).") needs no second date.
    const since = item.since && !item.message.includes('since ') ? `Since ${formatDayMonth(item.since)}` : null
    const next = 'advice' in destination ? destination.advice : destination.label
    return {
      key: item.key,
      kind: 'app',
      title: item.message,
      detail: since ? `${since} · ${next}` : next,
      to: 'to' in destination ? destination.to : null,
      poster: null,
      film: '',
      label: 'App',
      own: true,
      ownerId: null,
    }
  })
}
