import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import type { EbayAccount } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'
import { finishEbayConnect } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

type Outcome =
  | { kind: 'working' }
  | { kind: 'connected'; account: EbayAccount }
  | { kind: 'failed'; message: string }

/**
 * Where eBay sends a person back after they agree — Batch T8b (`DECISIONS.md` #227, #245).
 *
 * The RuName's "Auth accepted URL". eBay puts a one-time `code` and the `state` on the
 * address; this page, which already holds the person's session, hands both to the API,
 * which checks the state is one this person started and swaps the code for their tokens.
 *
 * **Once only, and then off the address bar.** React runs effects twice in development, so
 * a ref keeps it to one request (a second would find the state spent). The code is removed
 * from the address as soon as it is read, through the router so its own history entry stays
 * whole, and a reload or a shared link carries nothing.
 */
export default function EbayConnectedPage() {
  const [params, setParams] = useSearchParams()
  const queryClient = useQueryClient()
  const sent = useRef(false)
  const [outcome, setOutcome] = useState<Outcome>({ kind: 'working' })

  useEffect(() => {
    if (sent.current) return
    sent.current = true
    const code = params.get('code')
    const state = params.get('state')
    setParams({}, { replace: true })
    if (!code || !state) {
      setOutcome({ kind: 'failed', message: 'eBay did not send a sign-in code back. Press Connect eBay again.' })
      return
    }
    finishEbayConnect(code, state)
      .then((account) => {
        setOutcome({ kind: 'connected', account })
        void queryClient.invalidateQueries({ queryKey: ['ebay-account'] })
      })
      .catch((error: unknown) => {
        setOutcome({ kind: 'failed', message: queryErrorMessage(error, 'eBay could not be connected.') })
      })
  }, [params, setParams, queryClient])

  return (
    <div className="page-shell-narrow space-y-6">
      <PageHeader eyebrow="Settings" title="Connect eBay" />
      {outcome.kind === 'working' ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Finishing your eBay sign-in…
        </p>
      ) : null}
      {outcome.kind === 'connected' ? (
        <div className="space-y-4">
          <p className="flex items-start gap-2 text-sm text-foreground">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden />
            <span>
              eBay is connected
              {outcome.account.accountName ? (
                <>
                  {' '}as <span className="font-semibold">{outcome.account.accountName}</span>
                </>
              ) : null}
              .
            </span>
          </p>
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm">
              <Link to="/ebay">Your eBay lists</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link to="/settings?tab=ebay">Back to Settings</Link>
            </Button>
          </div>
        </div>
      ) : null}
      {outcome.kind === 'failed' ? (
        <div className="space-y-4">
          <p role="alert" className="flex items-start gap-2 text-sm text-destructive">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <span>{outcome.message}</span>
          </p>
          <Button asChild size="sm" variant="outline">
            <Link to="/settings?tab=ebay">Back to Settings</Link>
          </Button>
        </div>
      ) : null}
    </div>
  )
}
