import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BellRing, ExternalLink, Pencil, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import {
  EBAY_TARGETS_KEY,
  changeTargetPrice,
  createListingTarget,
  fetchEbayTargets,
  formatLabel,
  removeTarget,
  type EbayTarget,
  type EbayWatchRun,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { formatShortDate } from '@/lib/utils'

/**
 * eBay price alerts — Batch T8a (`DECISIONS.md` #203, #216).
 *
 * **Each person's own.** An alert is someone's standing request to hear about a price, and
 * the push goes to them alone, so this page lists only the signed-in person's.
 *
 * **It never implies a check that has not happened.** The schedule is a Railway job that
 * starts when Craig applies the config, so until the first pass the page says nothing is
 * being checked, rather than showing alerts as if they were watched.
 */

const TARGET_PATTERN = /^\d{1,5}(\.\d{1,2})?$/

function money(amount: string): string {
  return `£${Number(amount).toFixed(2)}`
}

const TIME = new Intl.DateTimeFormat('en-GB', {
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'Europe/London',
})

/** "26 Sep 2026, 11:20", in UK time. */
export function when(iso: string): string {
  return `${formatShortDate(iso)}, ${TIME.format(new Date(iso))}`
}

/** A price the form will send: pounds, with at most two places, above nothing. */
export function validTarget(value: string): boolean {
  const trimmed = value.trim()
  return TARGET_PATTERN.test(trimmed) && Number(trimmed) > 0
}

function Schedule({ run }: { run: EbayWatchRun | null }) {
  if (!run) {
    return (
      <p className="text-sm text-muted-foreground">
        Alerts are checked every two hours once the schedule is switched on. It is not on yet,
        so nothing is being checked.
      </p>
    )
  }
  const stopped = run.status === 'stopped' || run.status === 'abandoned'
  // Batch X2 (UX48-02): what the last check read. "Last check 19:20" alone stood above 45
  // passes in a row that read nothing.
  const read =
    run.listingsSeen > 0
      ? `read ${String(run.listingsSeen)} new listings`
      : run.emptyInARow > 1
        ? `read 0 new listings, ${String(run.emptyInARow)} checks in a row`
        : 'read 0 new listings'
  return (
    <p className={run.emptyInARow > 2 ? 'text-sm text-warning' : 'text-sm text-muted-foreground'}>
      Checked every two hours. Last check {when(run.startedAt)} · {read}
      {stopped ? ', and it stopped early.' : '.'}
    </p>
  )
}

function WatchListing() {
  const queryClient = useQueryClient()
  const [address, setAddress] = useState('')
  const [target, setTarget] = useState('')
  const [done, setDone] = useState<EbayTarget | null>(null)

  const create = useMutation({
    mutationFn: () => createListingTarget(address.trim(), target.trim()),
    onSuccess: (made) => {
      setDone(made)
      setAddress('')
      setTarget('')
      void queryClient.invalidateQueries({ queryKey: EBAY_TARGETS_KEY })
    },
  })

  const ready = address.trim().length > 0 && validTarget(target)

  function submit(event: FormEvent) {
    event.preventDefault()
    if (ready) create.mutate()
  }

  return (
    <form className="archive-panel space-y-3 p-4" onSubmit={submit} aria-labelledby="watch-listing-heading">
      <h2 id="watch-listing-heading" className="metadata-label">Watch an eBay listing</h2>
      <p className="text-sm text-muted-foreground">
        Copy the listing&rsquo;s address from eBay and say what you would pay, postage included.
        For an auction, you are told when the bidding is under your price, to set it as your
        maximum bid.
      </p>
      <label className="block space-y-1 text-sm">
        <span className="text-foreground">Listing address</span>
        <Input
          value={address}
          onChange={(event) => setAddress(event.target.value)}
          inputMode="url"
          autoComplete="off"
          placeholder="https://www.ebay.co.uk/itm/…"
        />
      </label>
      <label className="block space-y-1 text-sm">
        <span className="text-foreground">Your price (£)</span>
        <Input
          value={target}
          onChange={(event) => setTarget(event.target.value)}
          inputMode="decimal"
          placeholder="8.00"
          className="max-w-32"
        />
      </label>
      <Button type="submit" disabled={!ready || create.isPending}>
        <BellRing aria-hidden /> Watch this listing
      </Button>
      {create.isError ? (
        <p role="alert" className="text-sm text-destructive-text">
          {queryErrorMessage(create.error, 'The listing could not be watched.')}
        </p>
      ) : null}
      {done && !create.isError ? (
        <p role="status" className="text-sm text-foreground">
          {done.status === 'met'
            ? `It is already at or under your price: ${done.title}.`
            : `Watching ${done.title}.`}
        </p>
      ) : null}
    </form>
  )
}

function statusBadge(target: EbayTarget) {
  if (target.status === 'met') return <Badge tone="success">Target met</Badge>
  if (target.status === 'ended') return <Badge tone="neutral">Ended</Badge>
  return <Badge tone="info">Watching</Badge>
}

/** What the last check found, in words. */
export function currentLine(target: EbayTarget): string {
  if (!target.lastCheckedAt) return 'Not checked yet.'
  if (!target.currentPrice) {
    return target.kind === 'search' ? 'No UK Buy It Now copy found at the last check.' : 'No price at the last check.'
  }
  const postage = target.currentPostage && Number(target.currentPostage) > 0
    ? ` + ${money(target.currentPostage)} postage`
    : ', free postage'
  if (target.kind === 'search') return `Cheapest UK copy: ${money(target.currentPrice)}${postage}.`
  if (target.isAuction) return `Bidding at ${money(target.currentPrice)}.`
  return `Buy It Now: ${money(target.currentPrice)}${postage}.`
}

function TargetCard({ target }: { target: EbayTarget }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [price, setPrice] = useState(target.targetPrice)

  const refresh = () => void queryClient.invalidateQueries({ queryKey: EBAY_TARGETS_KEY })
  const change = useMutation({
    mutationFn: () => changeTargetPrice(target.id, price.trim()),
    onSuccess: () => {
      setEditing(false)
      refresh()
    },
  })
  const remove = useMutation({ mutationFn: () => removeTarget(target.id), onSuccess: refresh })

  const link = target.currentUrl ?? target.url
  const heading =
    target.kind === 'search' && target.formatCode
      ? `Any ${formatLabel(target.formatCode) ?? target.formatCode} of ${target.title}`
      : target.title

  return (
    <li className="archive-panel space-y-2 p-4">
      <div className="flex items-start justify-between gap-3">
        <h3 className="min-w-0 break-words font-display text-base font-semibold text-foreground">
          {target.kind === 'search' && target.movieId ? (
            <Link to={`/movies/${target.movieId}`} className="hover:underline">{heading}</Link>
          ) : (
            heading
          )}
        </h3>
        {statusBadge(target)}
      </div>

      {editing ? (
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            if (validTarget(price)) change.mutate()
          }}
        >
          <label className="flex items-center gap-2 text-sm">
            <span>Your price (£)</span>
            <Input
              value={price}
              onChange={(event) => setPrice(event.target.value)}
              inputMode="decimal"
              className="w-24"
              aria-label="Your price in pounds"
            />
          </label>
          <Button type="submit" size="sm" disabled={!validTarget(price) || change.isPending}>Save</Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
        </form>
      ) : (
        <p className="flex flex-wrap items-center gap-2 text-sm text-foreground">
          Your price: <span className="font-semibold">{money(target.targetPrice)}</span>
          <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(true)}>
            <Pencil aria-hidden /> Change
          </Button>
        </p>
      )}

      <p className="text-sm text-muted-foreground">{currentLine(target)}</p>
      {target.endsAt && target.status === 'watching' ? (
        <p className="text-xs text-muted-foreground">Ends {when(target.endsAt)}.</p>
      ) : null}
      {target.lastError ? (
        <p className="text-xs text-destructive-text">The last check failed: {target.lastError}</p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2 pt-1">
        {link ? (
          <Button asChild size="sm" variant="outline">
            <a href={link} target="_blank" rel="noopener noreferrer">
              Open on eBay <ExternalLink aria-hidden />
            </a>
          </Button>
        ) : null}
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => remove.mutate()}
          disabled={remove.isPending}
        >
          <Trash2 aria-hidden /> Remove
        </Button>
        {target.lastCheckedAt ? (
          <span className="text-xs text-muted-foreground">Checked {when(target.lastCheckedAt)}</span>
        ) : null}
      </div>
      {change.isError || remove.isError ? (
        <p role="alert" className="text-sm text-destructive-text">
          {queryErrorMessage(change.error ?? remove.error, 'That did not work. Try again.')}
        </p>
      ) : null}
    </li>
  )
}

export default function PriceAlertsPage() {
  const targetsQuery = useQuery({ queryKey: EBAY_TARGETS_KEY, queryFn: () => fetchEbayTargets() })
  const items = targetsQuery.data?.items ?? []
  const state = listState(targetsQuery, items.length === 0)

  return (
    <div className="page-shell-narrow space-y-6">
      <PageHeader
        eyebrow="eBay"
        title="Price alerts"
        description="Hear when a listing, or any UK copy of a film, reaches the price you would pay."
      />
      {targetsQuery.data ? <Schedule run={targetsQuery.data.lastRun} /> : null}

      <WatchListing />

      <section className="space-y-3" aria-labelledby="price-alerts-heading">
        <h2 id="price-alerts-heading" className="section-heading">Your alerts</h2>
        {state === 'loading' ? <StatePanel compact tone="loading" title="Loading your alerts" /> : null}
        {state === 'error' ? (
          <StatePanel
            compact
            tone="error"
            title="Your alerts are unavailable"
            description={queryErrorMessage(targetsQuery.error, 'Could not load your alerts.')}
          />
        ) : null}
        {state === 'empty' ? (
          <p className="text-sm text-muted-foreground">
            None yet. Watch a listing above, or open a film and set an alert on its 4K or Blu-ray.
          </p>
        ) : null}
        {items.length > 0 ? (
          <ul className="space-y-3">
            {items.map((target) => <TargetCard key={target.id} target={target} />)}
          </ul>
        ) : null}
      </section>
    </div>
  )
}
