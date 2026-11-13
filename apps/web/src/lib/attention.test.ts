import { describe, expect, it } from 'vitest'
import type { Attention } from '@mcu/shared'

import { attentionDestination, attentionRows } from './attention'

const NOTE = '3f2504e0-4f89-41d3-9a0c-0305e82c3401'
const MARK = '3f2504e0-4f89-41d3-9a0c-0305e82c3402'

function problem(key: string, message: string, since: string | null = '2026-10-13T08:00:00Z') {
  return { key, message, since, noteId: null, fromProfileId: null, fromName: null, body: null }
}

describe('attentionDestination — AA2', () => {
  it('maps every health-check family to a repair screen or owner instruction', () => {
    expect(attentionDestination('job:reminders')).toHaveProperty('advice')
    expect(attentionDestination('ebay:listings')).toMatchObject({ to: '/settings?tab=ebay' })
    expect(attentionDestination('person:1:notifications', '1')).toMatchObject({ to: '/settings?tab=notifications' })
    expect(attentionDestination('person:2:notifications', '1')).toHaveProperty('advice')
    expect(attentionDestination('person:1:notifications')).toHaveProperty('advice')
    expect(attentionDestination('specs:halted')).toMatchObject({ to: '/specs' })
    expect(attentionDestination('api:readiness')).toHaveProperty('advice')
    expect(attentionDestination('database:size')).toHaveProperty('advice')
    expect(attentionDestination('person:1:lockout')).toHaveProperty('advice')
    expect(attentionDestination('identify:waiting')).toMatchObject({ to: '/identify' })
    expect(attentionDestination('deals:freshness')).toMatchObject({ to: '/retailers' })
    expect(attentionDestination('assistant:failures')).toMatchObject({ to: '/settings?tab=assistant' })
    expect(attentionDestination('check:stale')).toHaveProperty('advice')
    expect(attentionDestination('job:cron-specs')).toMatchObject({ to: '/specs' })
    expect(attentionDestination('job:cron-values')).toMatchObject({ to: '/valuation' })
    expect(attentionDestination('job:cron-scrape')).toMatchObject({ to: '/retailers' })
    expect(attentionDestination('identify:year-doubt')).toMatchObject({ to: '/identify#identify-doubts-heading' })
  })
})

describe('attentionRows — AF1 (#372): Needs attention as rows of Craig’s Needs you', () => {
  it('makes each problem an App row that opens where its line did, with when it began', () => {
    const attention: Attention = {
      checkedAt: '2026-11-13T08:00:00Z',
      items: [
        problem('identify:year-doubt', '1 identified film has a disc page or review for another year.', '2026-11-06T08:00:00Z'),
        problem('ebay:listings', 'No eBay listings read in the last 6 scans (since 9 Oct).'),
      ],
    }
    const [doubt, ebay] = attentionRows(attention, 'p-craig')
    expect(doubt).toMatchObject({
      kind: 'app',
      label: 'App',
      own: true,
      ownerId: null,
      title: '1 identified film has a disc page or review for another year.',
      detail: 'Since 6 Nov · Open films in doubt',
      to: '/identify#identify-doubts-heading',
    })
    // A message that already says since when gets no second date.
    expect(ebay.detail).toBe('Open eBay settings')
  })

  it('gives a problem with nowhere to open no link, and says what to do instead', () => {
    const [stale, otherPhone] = attentionRows({
      checkedAt: null,
      items: [
        problem('check:stale', "The daily check hasn't run since 11 Oct.", null),
        problem('person:p-mark:notifications', 'Mark has no phone getting notifications.'),
      ],
    }, 'p-craig')
    expect(stale).toMatchObject({ to: null, detail: 'Ask Craig to check this scheduled job in Railway.' })
    expect(otherPhone.to).toBeNull()
    expect(otherPhone.detail).toBe('Since 13 Oct · Ask this person to open Settings → Notifications on their own phone.')
  })

  it('makes a line sent to Craig a row from its sender, in their words, to clear', () => {
    const [line] = attentionRows({
      checkedAt: null,
      items: [{
        key: `note:${NOTE}`, message: 'Mark says: the Alien disc is in the Lounge', since: '2026-10-18T10:00:00Z',
        noteId: NOTE, fromProfileId: MARK, fromName: 'Mark', body: 'the Alien disc is in the Lounge',
      }],
    })
    expect(line).toMatchObject({
      kind: 'note', label: 'Mark', own: false, ownerId: MARK, noteId: NOTE, to: null,
      title: 'the Alien disc is in the Lounge', detail: 'Tell Craig · 18 Oct',
    })
  })

  it('still reads a line from an API before AF1, which sent no sender', () => {
    const [line] = attentionRows({
      checkedAt: null,
      items: [{ key: `note:${NOTE}`, message: 'Mark says: hello', since: null, noteId: NOTE, fromProfileId: null, fromName: null, body: null }],
    })
    expect(line).toMatchObject({ title: 'Mark says: hello', label: 'Someone', ownerId: null, detail: 'Tell Craig' })
  })
})
