import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BellRing } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  EBAY_TARGETS_KEY,
  createSearchTarget,
  fetchEbayTargets,
  formatLabel,
} from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

type AlertFormat = '4k_uhd' | 'blu_ray' | 'dvd'

const FORMAT_CHOICES: Array<{ value: AlertFormat; label: string }> = [
  { value: '4k_uhd', label: '4K' },
  { value: 'blu_ray', label: 'Blu-ray' },
  { value: 'dvd', label: 'DVD' },
]

const PRICE = /^\d{1,5}(\.\d{1,2})?$/

/**
 * An eBay price alert on this film — Batch T8a.
 *
 * **For both people, on the film itself.** The copy card's "What is it worth?" is an admin
 * tool; an alert is anyone's, and it is about the film on a format, not about a copy. It
 * means any UK Buy It Now listing of the film on that format, checked every two hours once
 * the schedule is on, and the push goes to the person who set it.
 *
 * Only an identified film can have one: the search needs the film's real title.
 */
export default function PriceAlertPanel({ movieId, title }: { movieId: string; title: string }) {
  const queryClient = useQueryClient()
  const [format, setFormat] = useState<AlertFormat>('4k_uhd')
  const [price, setPrice] = useState('')

  const alerts = useQuery({
    queryKey: [...EBAY_TARGETS_KEY, movieId],
    queryFn: () => fetchEbayTargets(movieId),
  })
  const create = useMutation({
    mutationFn: () => createSearchTarget(movieId, format, price.trim()),
    onSuccess: () => {
      setPrice('')
      void queryClient.invalidateQueries({ queryKey: EBAY_TARGETS_KEY })
    },
  })

  const ready = PRICE.test(price.trim()) && Number(price) > 0
  const mine = (alerts.data?.items ?? []).filter((target) => target.kind === 'search')

  function submit(event: FormEvent) {
    event.preventDefault()
    if (ready) create.mutate()
  }

  return (
    <section className="archive-panel space-y-3 p-4" aria-labelledby="price-alert-heading">
      <h2 id="price-alert-heading" className="metadata-label">eBay price alert</h2>
      <p className="text-sm text-muted-foreground">
        Hear when any UK copy of {title} is listed at your price or less, postage included.
      </p>

      {mine.length > 0 ? (
        <ul className="space-y-1 text-sm">
          {mine.map((target) => (
            <li key={target.id} className="flex flex-wrap items-center gap-x-2">
              <span className="text-foreground">
                {formatLabel(target.formatCode) ?? target.formatCode} at £{Number(target.targetPrice).toFixed(2)}
              </span>
              <span className="text-xs text-muted-foreground">
                {target.status === 'watching' ? 'watching' : target.status}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      <form className="flex flex-wrap items-end gap-2" onSubmit={submit}>
        <label className="space-y-1 text-sm">
          <span className="block text-foreground">Format</span>
          <select
            value={format}
            onChange={(event) => setFormat(event.target.value as AlertFormat)}
            className="h-10 rounded-md border border-input bg-background px-2 text-sm"
          >
            {FORMAT_CHOICES.map((choice) => (
              <option key={choice.value} value={choice.value}>{choice.label}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span className="block text-foreground">Your price (£)</span>
          <Input
            value={price}
            onChange={(event) => setPrice(event.target.value)}
            inputMode="decimal"
            placeholder="10.00"
            className="w-24"
          />
        </label>
        <Button type="submit" size="sm" disabled={!ready || create.isPending}>
          <BellRing aria-hidden /> Alert me
        </Button>
      </form>

      {create.isError ? (
        <p role="alert" className="text-sm text-destructive-text">
          {queryErrorMessage(create.error, 'The alert could not be set.')}
        </p>
      ) : null}
      <p className="text-xs text-muted-foreground">
        All your alerts are on <Link to="/price-alerts" className="underline">Price alerts</Link>.
      </p>
    </section>
  )
}
