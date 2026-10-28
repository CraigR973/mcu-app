import { onlineManager } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createQueryClient } from './query-client'

/**
 * The setting that makes the whole offline story possible.
 *
 * TanStack Query's default `networkMode: 'online'` **pauses** queries and mutations when
 * it believes the app is offline. Both pauses are silent and both look like a hang:
 *
 * - a paused query never issues its fetch, so the service worker is never asked and
 *   cached collection data is never served;
 * - a paused mutation never runs `mutationFn`, so the offline write queue — which lives
 *   inside it — is never reached, and an edit made offline is simply lost behind a
 *   spinner that cannot stop.
 *
 * Neither is catchable by testing the queue directly, because a direct call never goes
 * through react-query at all. That is exactly how this shipped and how it was found: by
 * driving the built app with the network down.
 */

afterEach(() => {
  onlineManager.setOnline(true)
})

describe('the app query client', () => {
  it('runs a mutation while offline instead of pausing it', async () => {
    onlineManager.setOnline(false)
    const client = createQueryClient()
    const mutationFn = vi.fn().mockResolvedValue('done')

    const result = await client
      .getMutationCache()
      .build(client, { mutationFn })
      .execute(undefined)

    // With the default network mode this never resolves — `mutationFn` is not called at
    // all, and the mutation sits pending until the connection returns.
    expect(mutationFn).toHaveBeenCalledTimes(1)
    expect(result).toBe('done')
  })

  it('runs a query while offline, so the service worker can answer it', async () => {
    onlineManager.setOnline(false)
    const client = createQueryClient()
    const queryFn = vi.fn().mockResolvedValue(['a film'])

    const data = await client.fetchQuery({ queryKey: ['movies'], queryFn })

    expect(queryFn).toHaveBeenCalledTimes(1)
    expect(data).toEqual(['a film'])
  })

  it('leaves retrying a write to the queue, which knows what actually happened', () => {
    // A react-query retry cannot tell "never sent" from "sent, no answer", so it would
    // re-send writes that may already have landed — creating a second disc, or reverting
    // a newer edit.
    const client = createQueryClient()
    expect(client.getDefaultOptions().mutations?.retry).toBe(0)
    expect(client.getDefaultOptions().mutations?.networkMode).toBe('always')
    expect(client.getDefaultOptions().queries?.networkMode).toBe('always')
  })
})


it('refreshes attention after a successful resolution, but never treats a refused write as resolved', async () => {
  const client = createQueryClient()
  client.setQueryData(['attention'], { items: ['a waiting proposal'] })
  client.setQueryData(['movies'], ['existing film'])
  client.setQueryData(['stats'], { watchedMovies: 2, ownedWatchedMovies: 1 })
  const refused = client.getMutationCache().build(client, {
    mutationFn: async () => { throw new Error('refused') },
  })
  await expect(refused.execute(undefined)).rejects.toThrow('refused')
  expect(client.getQueryState(['attention'])?.isInvalidated).toBe(false)
  expect(client.getQueryState(['stats'])?.isInvalidated).toBe(false)
  const resolved = client.getMutationCache().build(client, { mutationFn: async () => 'kept' })
  await resolved.execute(undefined)
  expect(client.getQueryState(['attention'])?.isInvalidated).toBe(true)
  expect(client.getQueryState(['movies'])?.isInvalidated).toBe(false)
  expect(client.getQueryState(['stats'])?.isInvalidated).toBe(true)
  client.clear()
})
