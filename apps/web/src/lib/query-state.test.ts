import type { UseQueryResult } from '@tanstack/react-query'
import { describe, expect, it } from 'vitest'

import { listState, queryErrorMessage } from './query-state'

/** Only the four fields `listState` reads. Cast once, here, rather than in each case. */
function query(partial: {
  data?: unknown
  isError?: boolean
  isPending?: boolean
  fetchStatus?: 'fetching' | 'paused' | 'idle'
}): UseQueryResult<unknown> {
  return {
    data: partial.data,
    error: partial.isError ? new Error('boom') : null,
    isError: partial.isError ?? false,
    isPending: partial.isPending ?? false,
    fetchStatus: partial.fetchStatus ?? 'idle',
  } as UseQueryResult<unknown>
}

describe('listState', () => {
  it('reports a paused query as offline, not as empty', () => {
    // The defect this exists for, seen on the trash page in Batch 7: TanStack Query
    // pauses the retry when it thinks the app is offline, so `isError` stays false and
    // `data` stays undefined — and a naive check renders "nothing here" for ever.
    expect(listState(query({ isPending: true, fetchStatus: 'paused' }), true)).toBe('offline')
  })

  it('still reports an error when one arrived while paused', () => {
    expect(
      listState(query({ isError: true, fetchStatus: 'paused' }), true),
    ).toBe('error')
  })

  it('keeps showing cached rows when a refetch pauses', () => {
    expect(listState(query({ data: { items: [1] }, fetchStatus: 'paused' }), false)).toBe('ready')
  })

  it('reports loading only while genuinely fetching for the first time', () => {
    expect(listState(query({ isPending: true, fetchStatus: 'fetching' }), true)).toBe('loading')
  })

  it('reports empty only once data actually arrived', () => {
    expect(listState(query({ data: { items: [] } }), true)).toBe('empty')
    expect(listState(query({ data: { items: [1] } }), false)).toBe('ready')
  })

  it('treats succeeded-but-undefined as failure rather than as empty', () => {
    expect(listState(query({ data: undefined }), true)).toBe('error')
  })
})

describe('queryErrorMessage', () => {
  it('prefers the thrown message and falls back otherwise', () => {
    expect(queryErrorMessage(new Error('HTTP 500'), 'fallback')).toBe('HTTP 500')
    expect(queryErrorMessage('a string', 'fallback')).toBe('fallback')
  })
})
