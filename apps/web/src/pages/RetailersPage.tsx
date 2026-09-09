import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Ban,
  Check,
  Loader2,
  Play,
  Plus,
  Save,
  Sprout,
  Store,
  Trash2,
  TriangleAlert,
} from 'lucide-react'
import type { RetailerRow } from '@mcu/shared'

import { ScraperTester } from '@/components/ScraperTester'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  addRetailer,
  applyBuiltInScrapers,
  fetchBuiltInScrapers,
  fetchRetailers,
  removeRetailer,
  runScrapers,
  seedRetailers,
  updateRetailer,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

/**
 * A scraped price, rendered as money in the currency it was **read in**.
 *
 * Never converted — `DECISIONS.md` #79 refuses a result whose currency is not the one the
 * retailer is configured for rather than translating it, so showing the bare number here
 * would drop the one fact that makes it checkable.
 */
function money(amount: string, currency: string | null) {
  if (!currency) return amount
  try {
    return new Intl.NumberFormat('en-GB', { style: 'currency', currency }).format(
      Number(amount),
    )
  } catch {
    // An unknown or malformed code must not blank the report.
    return `${amount} ${currency}`
  }
}

function RunPanel() {
  const queryClient = useQueryClient()
  const run = useMutation({
    mutationFn: (dryRun: boolean) => runScrapers(dryRun),
    onSuccess: (result) => {
      if (!result.dryRun) {
        void queryClient.invalidateQueries({ queryKey: ['retailers'] })
        void queryClient.invalidateQueries({ queryKey: ['wanted'] })
      }
    },
  })

  const result = run.data
  return (
    <section className="space-y-3 rounded-lg border border-border bg-card p-4">
      <div>
        <h2 className="text-sm font-semibold text-foreground">Price-check run</h2>
        <p className="text-xs text-muted-foreground">
          Checks every enabled retailer for every active wanted film. Preview makes the
          same live retailer requests but does not save prices.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={run.isPending}
          onClick={() => run.mutate(true)}
        >
          {run.isPending && run.variables ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          Preview live run
        </Button>
        <Button
          type="button"
          size="sm"
          disabled={run.isPending}
          onClick={() => {
            if (window.confirm('Run enabled retailers now and save valid prices?')) {
              run.mutate(false)
            }
          }}
        >
          {run.isPending && run.variables === false ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          Run and save prices
        </Button>
      </div>

      {run.isError ? (
        <p className="text-xs text-destructive">
          {queryErrorMessage(run.error, 'The price-check run failed.')}
        </p>
      ) : null}
      {result ? (
        <div className="space-y-2 text-xs">
          <p className="font-medium text-foreground">
            {result.dryRun ? 'Preview complete' : 'Run complete'}: {result.succeeded} passed,
            {' '}{result.failed} failed, {result.written} price rows saved.
          </p>
          {result.outcomes.length === 0 ? (
            <p className="text-muted-foreground">
              Nothing was checked. Add an active wanted film and enable at least one
              verified retailer.
            </p>
          ) : (
            <ul className="space-y-1">
              {result.outcomes.map((outcome, index) => (
                <li
                  key={`${outcome.retailer}-${outcome.wantedTitle}-${String(index)}`}
                  className={cn(
                    'rounded-md border px-2 py-1.5',
                    outcome.ok
                      ? 'border-primary/30 text-foreground'
                      : 'border-destructive/30 text-muted-foreground',
                  )}
                >
                  {outcome.retailer} · {outcome.wantedTitle} ·{' '}
                  {outcome.ok
                    ? `${
                        outcome.price
                          ? money(outcome.price, outcome.currency)
                          : 'price found'
                      }${result.dryRun ? '' : ' saved'}`
                    : (outcome.error ?? outcome.reasons.join('; ')) || 'no usable result'}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </section>
  )
}

function Row({ retailer }: { retailer: RetailerRow }) {
  const queryClient = useQueryClient()
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ['retailers'] })

  const toggle = useMutation({
    mutationFn: () =>
      updateRetailer(retailer.id, {
        name: retailer.name,
        baseUrl: retailer.baseUrl,
        dealsUrl: retailer.dealsUrl,
        searchUrlTemplate: retailer.searchUrlTemplate,
        scraperType: retailer.scraperType,
        scraperConfig: retailer.scraperConfig,
        scrapeFrequency: retailer.scrapeFrequency,
        enabled: !retailer.enabled,
        currency: retailer.currency,
        region: retailer.region,
        notes: retailer.notes,
      }),
    onSuccess: refresh,
  })
  const remove = useMutation({
    mutationFn: () => removeRetailer(retailer.id),
    onSuccess: refresh,
  })

  return (
    <li
      className={cn(
        'flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-3',
        retailer.enabled ? '' : 'opacity-60',
      )}
    >
      <Store className="h-5 w-5 shrink-0 text-muted-foreground" />
      <div className="min-w-0 flex-1">
        <p className="font-medium text-foreground">{retailer.name}</p>
        <p className="truncate text-xs text-muted-foreground">{retailer.baseUrl}</p>
        <p className="text-[11px] text-muted-foreground">
          {retailer.scrapeFrequency} ·{' '}
          {/* Honest about what a seeded row actually is: a name and a URL, not a working
              scraper. The selectors are Batch 19's, and a plausible wrong one persists a
              plausible wrong price rather than erroring. */}
          {retailer.isConfigured ? (
            'selectors configured'
          ) : (
            <span className="text-amber-500">no selectors yet — Batch 19</span>
          )}
          {retailer.consecutiveFailures > 0
            ? ` · ${String(retailer.consecutiveFailures)} recent failures`
            : ''}
        </p>
      </div>
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={toggle.isPending}
        onClick={() => toggle.mutate()}
      >
        {toggle.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        {retailer.enabled ? 'Disable' : 'Enable'}
      </Button>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        aria-label={`Remove ${retailer.name}`}
        disabled={remove.isPending}
        onClick={() => remove.mutate()}
      >
        <Trash2 className="h-4 w-4" />
      </Button>
      {/* §5.4. A person validates a retailer here *before* enabling it, because the
          failure this batch is about fetches fine and returns the wrong number. */}
      <ScraperTester retailer={retailer} />
    </li>
  )
}

/**
 * §5.3's built-in configurations, and the honest state of each.
 *
 * A built-in reports verified only after a permitted live check. Applying them is a
 * separate, deliberate button from Batch 18's seeding: a seeded retailer is a name and a
 * URL, while a selector is a guess until someone has watched it work.
 *
 * **The two states are split into two lists, not two chip colours.** When every built-in
 * was unverified the colour carried no load; now that some are supported and some never
 * will be, it has to — and `text-primary` and `text-amber-500` are the same colour to the
 * eye in this theme. The unverified ones also show their *reason* rather than hiding it in
 * a `title` tooltip: the reason is what tells the reader not to bother testing them.
 */
function BuiltInPanel() {
  const queryClient = useQueryClient()
  const builtInsQuery = useQuery({
    queryKey: ['built-in-scrapers'],
    queryFn: fetchBuiltInScrapers,
  })
  const apply = useMutation({
    mutationFn: applyBuiltInScrapers,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['retailers'] })
      void queryClient.invalidateQueries({ queryKey: ['built-in-scrapers'] })
    },
  })

  const data = builtInsQuery.data
  if (!data) return null

  const verified = data.items.filter((entry) => entry.verified)
  const unverified = data.items.filter((entry) => !entry.verified)

  return (
    <div className="space-y-3 rounded-lg border border-border bg-muted/30 p-3">
      <p className="text-xs font-semibold text-foreground">
        Built-in selectors ({data.items.length})
      </p>

      {verified.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          None of these has been run against a live page yet — every one is a guess until
          someone watches it work. Use “Test” on a retailer before enabling it.
        </p>
      ) : (
        <div className="space-y-1.5">
          <p className="text-xs text-muted-foreground">
            {verified.length} checked against live markup. “Test” one before enabling it —
            a shop can change its layout at any time.
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {verified.map((entry) => (
              <li
                key={entry.name}
                className="flex items-center gap-1 rounded-md border border-primary/40 px-2 py-0.5 text-[11px] text-primary"
                title={entry.note ?? undefined}
              >
                <Check className="h-3 w-3" aria-hidden />
                {entry.name}
              </li>
            ))}
          </ul>
        </div>
      )}

      {unverified.length > 0 ? (
        <div className="space-y-1.5">
          <p className="text-xs text-muted-foreground">
            {unverified.length} cannot be checked from here. Don’t test these — the reason
            won’t change on a retry.
          </p>
          <ul className="space-y-1">
            {unverified.map((entry) => (
              <li
                key={entry.name}
                className="flex items-start gap-1.5 text-[11px] text-muted-foreground"
              >
                <Ban className="mt-0.5 h-3 w-3 shrink-0 text-amber-500" aria-hidden />
                <span>
                  <span className="font-medium text-foreground">{entry.name}</span>
                  {entry.note ? ` — ${entry.note}` : ' — unverified'}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={apply.isPending}
        onClick={() => apply.mutate()}
      >
        {apply.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        Apply these selectors to the matching retailers
      </Button>
    </div>
  )
}

function NewRetailerForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [dealsUrl, setDealsUrl] = useState('')

  const create = useMutation({
    mutationFn: () =>
      addRetailer({
        name: name.trim(),
        baseUrl: baseUrl.trim(),
        dealsUrl: dealsUrl.trim() || null,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['retailers'] })
      onDone()
    },
  })

  return (
    <div className="space-y-3 rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap gap-2">
        <Input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Shop name"
          aria-label="Retailer name"
          className="max-w-[12rem]"
        />
        <Input
          value={baseUrl}
          onChange={(event) => setBaseUrl(event.target.value)}
          placeholder="https://…"
          aria-label="Base URL"
          className="max-w-xs"
        />
        <Input
          value={dealsUrl}
          onChange={(event) => setDealsUrl(event.target.value)}
          placeholder="https://…/sale (optional)"
          aria-label="Deals URL"
          className="max-w-xs"
        />
      </div>
      {create.isError ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(create.error, 'Could not add that retailer.')}
        </p>
      ) : null}
      <div className="flex gap-2">
        <Button
          type="button"
          size="sm"
          disabled={
            create.isPending || name.trim().length === 0 || !/^https?:\/\//i.test(baseUrl.trim())
          }
          onClick={() => create.mutate()}
        >
          Add
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </div>
  )
}

/**
 * §5.2's retailer management.
 *
 * **Seeded retailers arrive with no selectors, and the page says so.** §5.2 asks for
 * "seeded default retailers" and §3.16 names six; what a seeded row actually contains is a
 * name and a URL. Inventing CSS selectors nobody has run against a live page would be
 * worse than leaving them empty — the ledger's own risk note for Batch 19 is that a wrong
 * selector *"does not error — it selects the wrong node and persists a plausible wrong
 * number"*, and that number then feeds price alerts.
 */
export default function RetailersPage() {
  const queryClient = useQueryClient()
  const [creating, setCreating] = useState(false)

  const retailersQuery = useQuery({ queryKey: ['retailers'], queryFn: fetchRetailers })
  const items = retailersQuery.data?.items ?? []
  const state = listState(retailersQuery, items.length === 0)

  const seed = useMutation({
    mutationFn: seedRetailers,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['retailers'] }),
  })

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Retailers</h1>
          <p className="text-sm text-muted-foreground">
            Shops to watch for prices.{' '}
            {retailersQuery.data
              ? `${retailersQuery.data.configuredCount} of ${retailersQuery.data.total} have selectors.`
              : ''}
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={seed.isPending}
            onClick={() => seed.mutate()}
          >
            {seed.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sprout className="h-4 w-4" />
            )}
            Add missing defaults
          </Button>
          {!creating ? (
            <Button type="button" size="sm" onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" />
              New
            </Button>
          ) : null}
        </div>
      </div>

      {creating ? <NewRetailerForm onDone={() => setCreating(false)} /> : null}

      <BuiltInPanel />

      <RunPanel />

      {items.length > 0 && retailersQuery.data?.configuredCount === 0 ? (
        <p className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/5 p-3 text-xs text-muted-foreground">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
          <span>
            None of these have CSS selectors yet, so nothing is being scraped. The scraper
            framework is Batch 19 — a retailer configured with a guessed selector would not
            error, it would persist a plausible wrong price.
          </span>
        </p>
      ) : null}

      {state === 'loading' ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : state === 'offline' ? (
        <p className="text-sm text-muted-foreground">
          Waiting for the network — the retailers could not be loaded yet.
        </p>
      ) : state === 'error' ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(retailersQuery.error, 'Could not load the retailers.')}
        </p>
      ) : state === 'empty' ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <Store className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">No retailers yet.</p>
          <p className="text-xs text-muted-foreground">
            Use “Add missing defaults” above, or create one manually.
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {items.map((retailer) => (
            <Row key={retailer.id} retailer={retailer} />
          ))}
        </ul>
      )}

      {seed.isSuccess ? (
        <p className="text-xs text-muted-foreground">
          Added {seed.data.created} of the defaults.
        </p>
      ) : null}
    </div>
  )
}
