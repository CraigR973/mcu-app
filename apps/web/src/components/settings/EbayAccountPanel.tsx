import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link2, Loader2, ShoppingBag, Unlink } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { StatePanel } from '@/components/ui/state-panel'
import { disconnectEbay, fetchEbayAccount, startEbayConnect } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'
import { formatShortDate } from '@/lib/utils'

/**
 * Connect eBay — Batch T8b (`DECISIONS.md` #216, #227, #245).
 *
 * **Each person connects their own eBay**, here in their own Settings, and only they see
 * what it reads. Pressing Connect asks the API for eBay's consent page and goes there; eBay
 * asks who is signing in even if the browser is already signed in, then sends the person
 * back to `/settings/ebay/connected`. No eBay password ever reaches this app: eBay's own
 * page takes it. Disconnecting deletes the app's copy of the sign-in; removing the app's
 * access on eBay itself is in eBay's account settings.
 */
export function EbayAccountPanel() {
  const queryClient = useQueryClient()
  const account = useQuery({ queryKey: ['ebay-account'], queryFn: fetchEbayAccount })

  const connect = useMutation({
    mutationFn: startEbayConnect,
    onSuccess: (authorizeUrl) => {
      window.location.assign(authorizeUrl)
    },
  })

  const disconnect = useMutation({
    mutationFn: disconnectEbay,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['ebay-account'] })
      void queryClient.removeQueries({ queryKey: ['ebay-watching'] })
      void queryClient.removeQueries({ queryKey: ['ebay-selling'] })
    },
  })

  if (account.isPending) {
    return <StatePanel compact tone="loading" title="Loading your eBay connection" />
  }
  if (account.isError) {
    return (
      <StatePanel
        compact
        tone="error"
        title="Your eBay connection is unavailable"
        description={queryErrorMessage(account.error, 'Could not read your eBay connection.')}
      />
    )
  }

  const status = account.data
  return (
    <section className="space-y-4" aria-labelledby="ebay-account-heading">
      <div className="space-y-1">
        <h2 id="ebay-account-heading" className="section-heading">
          eBay
        </h2>
        <p className="text-sm leading-6 text-muted-foreground">
          Connect your own eBay to see your watch list, your saved searches and what you are
          selling here, and to set price alerts on them. You sign in on eBay&rsquo;s page; this
          app never sees your eBay password.{' '}
          <Link to="/privacy" className="font-medium text-primary underline-offset-2 hover:underline">
            What the app keeps
          </Link>
        </p>
      </div>

      {status.note ? <p className="text-sm text-warning">{status.note}</p> : null}

      {!status.configured ? (
        <p className="text-sm text-muted-foreground">
          Connecting eBay is not set up on this server yet ({status.missing.join(', ')}).
        </p>
      ) : status.connected ? (
        <div className="space-y-3 rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-foreground">
            Connected
            {status.accountName ? (
              <>
                {' '}as <span className="font-semibold">{status.accountName}</span>
              </>
            ) : null}
            {status.connectedAt ? (
              <span className="text-muted-foreground">, since {formatShortDate(status.connectedAt)}</span>
            ) : null}
            .
          </p>
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm">
              <Link to="/ebay">
                <ShoppingBag className="h-4 w-4" aria-hidden />
                Your eBay lists
              </Link>
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={disconnect.isPending}
              onClick={() => {
                if (window.confirm('Disconnect eBay? The app deletes its copy of your sign-in.')) {
                  disconnect.mutate()
                }
              }}
            >
              {disconnect.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              ) : (
                <Unlink className="h-4 w-4" aria-hidden />
              )}
              Disconnect
            </Button>
          </div>
          {disconnect.isError ? (
            <p role="alert" className="text-sm text-destructive">
              {queryErrorMessage(disconnect.error, 'Could not disconnect eBay.')}
            </p>
          ) : null}
        </div>
      ) : (
        <div className="space-y-2">
          <Button type="button" disabled={connect.isPending} onClick={() => connect.mutate()}>
            {connect.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Link2 className="h-4 w-4" aria-hidden />
            )}
            Connect eBay
          </Button>
          {connect.isError ? (
            <p role="alert" className="text-sm text-destructive">
              {queryErrorMessage(connect.error, 'Could not start connecting eBay.')}
            </p>
          ) : null}
        </div>
      )}
    </section>
  )
}
