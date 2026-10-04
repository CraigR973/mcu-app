import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { BellPlus, ExternalLink, Loader2, Search } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { EbayListing, EbaySavedSearch } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import {
  ApiError,
  createListingTarget,
  createSearchTarget,
  fetchEbaySelling,
  fetchEbayWatching,
  fetchSearch,
  fetchWanted,
} from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'
import { readSavedSearch, wordsNameFilm, type AlertFormat } from '@/lib/saved-search'
import { cn, formatShortDate } from '@/lib/utils'

type Tab = 'watching' | 'selling'

const ALERT_FORMATS: { value: AlertFormat; label: string }[] = [
  { value: '4k_uhd', label: '4K UHD' },
  { value: 'blu_ray', label: 'Blu-ray' },
  { value: 'dvd', label: 'DVD' },
]

const PRICE = /^\d{1,6}(\.\d{1,2})?$/

function money(price: string | null, currency: string | null): string {
  if (price === null) return 'No price'
  return currency === 'GBP' || currency === null ? `£${price}` : `${price} ${currency}`
}

/** A listing's price line: price and postage, and whether it is an auction. */
function priceLine(item: EbayListing): string {
  let price = money(item.price, item.currency)
  if (item.price !== null && item.postage !== null && item.postage !== '0.00') {
    price += ` + ${money(item.postage, item.currency)} postage`
  }
  const parts = [price]
  if (item.postage === '0.00') parts.push('free postage')
  if (item.isAuction) parts.push(item.bidCount ? `${String(item.bidCount)} bids` : 'auction, no bids')
  if (item.endsAt) parts.push(`ends ${formatShortDate(item.endsAt)}`)
  return parts.join(' · ')
}

/** A price alert on one watched listing: T8a's listing alert, from the listing's own page. */
function ListingAlert({ item }: { item: EbayListing }) {
  const [open, setOpen] = useState(false)
  const [price, setPrice] = useState('')
  const save = useMutation({ mutationFn: () => createListingTarget(item.url, price) })

  if (save.isSuccess) {
    return <p className="text-xs font-medium text-success">Alert set: under £{price}.</p>
  }
  if (!open) {
    return (
      <Button type="button" size="sm" variant="outline" onClick={() => setOpen(true)}>
        <BellPlus className="h-4 w-4" aria-hidden />
        Alert me
      </Button>
    )
  }
  return (
    <form
      className="flex flex-wrap items-center gap-2"
      onSubmit={(event) => {
        event.preventDefault()
        if (PRICE.test(price)) save.mutate()
      }}
    >
      <Input
        autoFocus
        value={price}
        onChange={(event) => setPrice(event.target.value)}
        inputMode="decimal"
        placeholder="Under £"
        aria-label={`Alert me when ${item.title} is under this price`}
        className="w-28"
      />
      <Button type="submit" size="sm" disabled={!PRICE.test(price) || save.isPending}>
        {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : 'Save'}
      </Button>
      <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>
        Cancel
      </Button>
      {save.isError ? (
        <p role="alert" className="w-full text-xs text-destructive">
          {queryErrorMessage(save.error, 'Could not set that alert.')}
        </p>
      ) : null}
    </form>
  )
}

/** A film a saved search could be for: on Wanted, or in the collection. */
interface FilmChoice {
  id: string
  title: string
  year: number | null
  wanted: boolean
  /** The format the want asks for, when it is one an alert can watch. */
  wantedFormat: AlertFormat | null
}

function alertFormat(code: string | null): AlertFormat | null {
  return ALERT_FORMATS.find((entry) => entry.value === code)?.value ?? null
}

/**
 * A saved search becomes one of T8a's film alerts once its owner picks the film and format
 * (`DECISIONS.md` #245): T8a's matcher judges a listing against a film, not free text.
 *
 * **The film is looked for on Wanted as well as in the collection.** A search on eBay is
 * mostly for a film not owned yet, and the catalogue search finds owned films only. The
 * search's format words choose the format and are left out of the words that find the film
 * (`lib/saved-search.ts`); the person can change both.
 */
function SavedSearchAlert({ search }: { search: EbaySavedSearch }) {
  const [read] = useState(() => readSavedSearch(search.keywords ?? search.name))
  const [open, setOpen] = useState(false)
  const [words, setWords] = useState(read.words)
  const [asked, setAsked] = useState<string | null>(null)
  const [film, setFilm] = useState<FilmChoice | null>(null)
  const [format, setFormat] = useState<AlertFormat>(read.format ?? 'blu_ray')
  const [price, setPrice] = useState('')

  const owned = useQuery({
    queryKey: ['ebay-saved-search-films', asked],
    queryFn: () => fetchSearch(asked ?? '', 8),
    enabled: asked !== null && asked.length >= 2,
  })
  const wanted = useQuery({ queryKey: ['wanted', true], queryFn: () => fetchWanted(true), enabled: open })
  const save = useMutation({
    mutationFn: () => {
      if (!film) throw new Error('Pick the film first.')
      return createSearchTarget(film.id, format, price)
    },
  })

  const choices: FilmChoice[] = []
  if (asked !== null) {
    for (const want of wanted.data?.items ?? []) {
      if (wordsNameFilm(asked, want.movieTitle) && !choices.some((choice) => choice.id === want.movieId)) {
        choices.push({
          id: want.movieId,
          title: want.movieTitle,
          year: want.year,
          wanted: true,
          wantedFormat: alertFormat(want.preferredFormat),
        })
      }
    }
    for (const item of owned.data?.items ?? []) {
      if (!choices.some((choice) => choice.id === item.id)) {
        choices.push({ id: item.id, title: item.title, year: item.year, wanted: false, wantedFormat: null })
      }
    }
  }
  const looking = owned.isFetching || wanted.isFetching

  function ask(next: string) {
    setFilm(null)
    setAsked(next.trim())
  }

  if (save.isSuccess && film) {
    return (
      <p className="text-xs font-medium text-success">
        Alert set: {film.title}, {ALERT_FORMATS.find((entry) => entry.value === format)?.label}, under £
        {price}.
      </p>
    )
  }
  if (!open) {
    return (
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={() => {
          setOpen(true)
          ask(words)
        }}
      >
        <BellPlus className="h-4 w-4" aria-hidden />
        Make an alert
      </Button>
    )
  }
  return (
    <div className="space-y-3 rounded-md border border-border p-3">
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          ask(words)
        }}
      >
        <Input
          value={words}
          onChange={(event) => setWords(event.target.value)}
          aria-label="Which film is this search for?"
          placeholder="Which film?"
        />
        <Button type="submit" size="sm" variant="outline">
          <Search className="h-4 w-4" aria-hidden />
          Find
        </Button>
      </form>
      {looking ? <p className="text-xs text-muted-foreground">Looking on Wanted and in the collection…</p> : null}
      {asked !== null && !looking && choices.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          No film on Wanted or in the collection matches. Change the words and press Find, or
          add the film to Wanted first.
        </p>
      ) : null}
      {choices.length > 0 ? (
        <fieldset className="space-y-1.5">
          <legend className="text-xs font-medium text-foreground">The film</legend>
          {choices.map((choice) => (
            <label key={choice.id} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name={`film-${search.name}`}
                checked={film?.id === choice.id}
                onChange={() => {
                  setFilm(choice)
                  if (read.format === null && choice.wantedFormat !== null) setFormat(choice.wantedFormat)
                }}
              />
              <span>
                {choice.title}
                {choice.year ? <span className="text-muted-foreground"> ({choice.year})</span> : null}
                {choice.wanted ? <span className="text-xs text-muted-foreground"> · on Wanted</span> : null}
              </span>
            </label>
          ))}
        </fieldset>
      ) : null}
      {film ? (
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            if (PRICE.test(price)) save.mutate()
          }}
        >
          <label className="text-xs text-muted-foreground">
            <span className="sr-only">Format</span>
            <select
              value={format}
              onChange={(event) => setFormat(alertFormat(event.target.value) ?? 'blu_ray')}
              className="select-control"
            >
              {ALERT_FORMATS.map((entry) => (
                <option key={entry.value} value={entry.value}>
                  {entry.label}
                </option>
              ))}
            </select>
          </label>
          <Input
            value={price}
            onChange={(event) => setPrice(event.target.value)}
            inputMode="decimal"
            placeholder="Under £"
            aria-label={`Alert me when ${film.title} is under this price`}
            className="w-28"
          />
          <Button type="submit" size="sm" disabled={!PRICE.test(price) || save.isPending}>
            {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : 'Save'}
          </Button>
        </form>
      ) : null}
      {save.isError ? (
        <p role="alert" className="text-xs text-destructive">
          {queryErrorMessage(save.error, 'Could not set that alert.')}
        </p>
      ) : null}
      <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>
        Cancel
      </Button>
    </div>
  )
}

function ListingRow({ item, children }: { item: EbayListing; children?: React.ReactNode }) {
  return (
    <li className="archive-panel p-3">
      <div className="min-w-0 space-y-1.5">
        <a
          href={item.url}
          target="_blank"
          rel="noreferrer"
          className="line-clamp-2 text-sm font-medium text-foreground hover:underline"
        >
          {item.title}
        </a>
        <p className="text-xs text-muted-foreground">{priceLine(item)}</p>
        {children}
      </div>
    </li>
  )
}

/** The API answers 409 when this person has no usable eBay connection; its words say why. */
function notConnected(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409
}

function NotConnectedPanel({ error }: { error: unknown }) {
  return (
    <StatePanel
      tone="empty"
      title="eBay is not connected"
      description={queryErrorMessage(error, 'Connect eBay in Settings to see your eBay lists here.')}
      action={
        <Button asChild size="sm">
          <Link to="/settings?tab=ebay">Go to Settings</Link>
        </Button>
      }
    />
  )
}

function Watching() {
  const query = useQuery({ queryKey: ['ebay-watching'], queryFn: fetchEbayWatching, retry: false })
  if (query.isPending) return <StatePanel compact tone="loading" title="Asking eBay for your watch list" />
  if (query.isError) {
    return notConnected(query.error) ? (
      <NotConnectedPanel error={query.error} />
    ) : (
      <StatePanel
        compact
        tone="error"
        title="Your watch list could not be read"
        description={queryErrorMessage(query.error, 'eBay did not answer.')}
      />
    )
  }
  const { items, savedSearches, totalItems } = query.data
  return (
    <div className="space-y-6">
      <section className="space-y-2" aria-labelledby="ebay-watching-heading">
        <h2 id="ebay-watching-heading" className="text-sm font-semibold text-foreground">
          Watching{totalItems > items.length ? ` (${String(items.length)} of ${String(totalItems)})` : ''}
        </h2>
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">You are not watching anything on eBay.</p>
        ) : (
          <ul className="space-y-2">
            {items.map((item) => (
              <ListingRow key={item.itemId} item={item}>
                <ListingAlert item={item} />
              </ListingRow>
            ))}
          </ul>
        )}
      </section>
      <section className="space-y-2" aria-labelledby="ebay-searches-heading">
        <h2 id="ebay-searches-heading" className="text-sm font-semibold text-foreground">
          Saved searches
        </h2>
        {savedSearches.length === 0 ? (
          <p className="text-sm text-muted-foreground">You have no saved searches on eBay.</p>
        ) : (
          <ul className="space-y-2">
            {savedSearches.map((search) => (
              <li key={search.name} className="archive-panel space-y-2 p-3">
                <p className="text-sm font-medium text-foreground">
                  {search.url ? (
                    <a href={search.url} target="_blank" rel="noreferrer" className="hover:underline">
                      {search.name} <ExternalLink className="inline h-3 w-3" aria-hidden />
                    </a>
                  ) : (
                    search.name
                  )}
                </p>
                {search.keywords && search.keywords !== search.name ? (
                  <p className="text-xs text-muted-foreground">{search.keywords}</p>
                ) : null}
                <SavedSearchAlert search={search} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function Selling() {
  const query = useQuery({ queryKey: ['ebay-selling'], queryFn: fetchEbaySelling, retry: false })
  if (query.isPending) return <StatePanel compact tone="loading" title="Asking eBay what you are selling" />
  if (query.isError) {
    return notConnected(query.error) ? (
      <NotConnectedPanel error={query.error} />
    ) : (
      <StatePanel
        compact
        tone="error"
        title="Your selling list could not be read"
        description={queryErrorMessage(query.error, 'eBay did not answer.')}
      />
    )
  }
  const { active, sold, totalActive, totalSold } = query.data
  return (
    <div className="space-y-6">
      <section className="space-y-2" aria-labelledby="ebay-active-heading">
        <h2 id="ebay-active-heading" className="text-sm font-semibold text-foreground">
          For sale{totalActive > active.length ? ` (${String(active.length)} of ${String(totalActive)})` : ''}
        </h2>
        {active.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing is for sale on your eBay.</p>
        ) : (
          <ul className="space-y-2">
            {active.map((item) => (
              <ListingRow key={item.itemId} item={item} />
            ))}
          </ul>
        )}
      </section>
      <section className="space-y-2" aria-labelledby="ebay-sold-heading">
        <h2 id="ebay-sold-heading" className="text-sm font-semibold text-foreground">
          Sold in the last 60 days{totalSold > sold.length ? ` (${String(sold.length)} of ${String(totalSold)})` : ''}
        </h2>
        {sold.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing sold in the last 60 days.</p>
        ) : (
          <ul className="space-y-2">
            {sold.map((entry) => (
              <li key={`${entry.itemId}-${entry.soldAt ?? ''}`} className="archive-panel space-y-1 p-3">
                <a
                  href={entry.url}
                  target="_blank"
                  rel="noreferrer"
                  className="line-clamp-2 text-sm font-medium text-foreground hover:underline"
                >
                  {entry.title}
                </a>
                <p className="text-xs text-muted-foreground">
                  {money(entry.price, entry.currency)}
                  {entry.soldAt ? ` · sold ${formatShortDate(entry.soldAt)}` : ''}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

/**
 * Your eBay — Batch T8b (`DECISIONS.md` #216, #245): the signed-in person's own watch list,
 * saved searches and selling list, read from eBay when the page opens. Nobody else's: the
 * API reads only the connection of whoever is signed in.
 */
export default function YourEbayPage() {
  const [tab, setTab] = useState<Tab>('watching')
  return (
    <div className="page-shell-narrow space-y-6">
      <PageHeader
        eyebrow="Your account"
        title="Your eBay"
        description="Your watch list, saved searches and selling list, read from eBay now. Set a price alert on anything you watch."
      />
      <div role="tablist" aria-label="Your eBay lists" className="flex gap-1 border-b border-border">
        {(
          [
            ['watching', 'Watching'],
            ['selling', 'Selling'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            id={`ebay-tab-${key}`}
            aria-selected={tab === key}
            aria-controls={`ebay-panel-${key}`}
            onClick={() => setTab(key)}
            className={cn(
              'touch-target -mb-px min-h-11 shrink-0 border-b-2 px-4 text-sm font-semibold transition-colors',
              tab === key ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`ebay-panel-${tab}`} aria-labelledby={`ebay-tab-${tab}`} tabIndex={0}>
        {tab === 'watching' ? <Watching /> : <Selling />}
      </div>
    </div>
  )
}
