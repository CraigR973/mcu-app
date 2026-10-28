import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'

import { reportIfOutOfDate } from './describe-error'

/**
 * The app's query client, built here rather than inline in `main.tsx` so the options a
 * test needs to assert on are the options the app actually runs with.
 *
 * `networkMode: 'always'` is the load-bearing setting and the reason this file exists —
 * see the comments below, and `DECISIONS.md` #47.
 */
export function createQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    // Batch X8: an answer this build cannot read raises the "newest version" banner, from
    // whichever screen met it first.
    queryCache: new QueryCache({ onError: reportIfOutOfDate }),
    mutationCache: new MutationCache({
      onError: reportIfOutOfDate,
      // AB1: every successful resolution/collection change makes Home re-read the
      // actionable state. Central ownership covers both Identify and film-page actions.
      onSuccess: () => { void client.invalidateQueries({ queryKey: ['attention'] }) },
    }),
    defaultOptions: {
      queries: {
        staleTime: 1000 * 60 * 5,
        retry: 1,
        // TanStack Query *pauses* work when it believes the app is offline. That default
        // suits an app with no offline story; it actively breaks this one, in two ways
        // that both look like a hang rather than an error.
        //
        // A paused **query** never issues its fetch — so the service worker, whose whole
        // job is to answer that fetch from cache, is never consulted. "Browse the
        // collection with the network off" cannot work while the request is not made.
        // It is also what made every list render its empty state indefinitely in Batch 7.
        networkMode: 'always',
      },
      mutations: {
        // A paused **mutation** never runs `mutationFn` — so the offline write queue,
        // which lives inside it, is never reached. An edit made offline sat behind a
        // spinner that could not stop and was never saved anywhere. Found by driving the
        // app with the network down; no unit test could have seen it, because a unit test
        // calls the queue directly and never goes through react-query at all.
        networkMode: 'always',
        // The queue owns retrying, and it distinguishes "never sent" from "sent, no
        // answer". A react-query retry cannot make that distinction and would re-send
        // writes that may already have landed.
        retry: 0,
      },
    },
  })
  return client
}
