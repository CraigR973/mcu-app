import type { UseQueryResult } from '@tanstack/react-query'

/**
 * What a list should render, given the state of the query behind it.
 *
 * **`isError` is not enough, and the gap is user-visible.** TanStack Query *pauses* a
 * retry when it believes the app is offline: the query sits at `status: 'pending'`,
 * `fetchStatus: 'paused'`, `isError: false`, with no data, and stays there. A page that
 * checks `isLoading` then `isError` then `items.length === 0` falls straight through to
 * its empty state and tells the person their trash is empty — when the truth is that it
 * never heard back from the server.
 *
 * Observed on the trash page during Batch 7: the API was unreachable, the query paused,
 * and "Nothing has been removed." rendered confidently and indefinitely. The distinction
 * matters most in exactly the situation Batch 8 is about.
 *
 * `MovieDetailPage` already avoids this by treating `isError || !data` as failure. This
 * states the rule once so every list can follow it.
 */
export type ListState = 'loading' | 'offline' | 'error' | 'empty' | 'ready'

export function listState<T>(query: UseQueryResult<T>, isEmpty: boolean): ListState {
  if (query.isError) return 'error'
  // Paused with nothing cached: the request has not failed, it has not been made.
  if (query.fetchStatus === 'paused' && query.data === undefined) return 'offline'
  if (query.isPending) return 'loading'
  // Succeeded-but-undefined should be impossible; treating it as failure rather than as
  // "empty" is the whole point of this function.
  if (query.data === undefined) return 'error'
  return isEmpty ? 'empty' : 'ready'
}

export function queryErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}
