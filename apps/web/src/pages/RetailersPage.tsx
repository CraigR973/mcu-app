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
import type { DealsRun, RetailerRow } from '@mcu/shared'

import { ScraperTester } from '@/components/ScraperTester'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/context/auth'
import {
  addRetailer,
  applyBuiltInScrapers,
  fetchBuiltInScrapers,
  fetchRetailers,
  removeRetailer,
  formatLabel,
  fetchScrapeRuns,
  runDailyScrape,
  runDealsScrape,
  runScrapers,
  scrapeRunVerdict,
  seedRetailers,
  updateRetailer,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn, formatDateTime } from '@/lib/utils'

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
            {' '}{result.failed} failed
            {result.notStocked > 0 ? `, ${String(result.notStocked)} not stocked` : ''}
            {result.skipped > 0 ? `, ${String(result.skipped)} skipped` : ''},{' '}
            {result.written} price rows saved.
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
                    outcome.skipped || outcome.notStocked
                      ? 'border-border text-muted-foreground'
                      : outcome.ok
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
                    : outcome.notStocked
                      ? 'Not stocked here — the shop answered, it just has not got it.'
                      : (outcome.error ?? outcome.reasons.join('; ')) ||
                        'no usable result'}
                  {outcome.substitutedFormat ? (
                    <span className="mt-0.5 block text-warning">
                      Not the format wanted — priced the{' '}
                      {formatLabel(outcome.substitutedFormat)}.
                    </span>
                  ) : null}
                  {outcome.editionMatched === false ? (
                    <span className="mt-0.5 block text-warning">
                      Not the edition wanted — priced a different one.
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </section>
  )
}

/** One shop's line in a sale-page check: what it found and kept, or why it kept nothing. */
function SalePageOutcome({ outcome }: { outcome: DealsRun['outcomes'][number] }) {
  const counts = [
    `${String(outcome.found)} found`,
    `${String(outcome.kept)} kept`,
    outcome.skippedOwned > 0 ? `${String(outcome.skippedOwned)} already owned` : null,
    outcome.notDiscounted > 0 ? `${String(outcome.notDiscounted)} not discounted` : null,
    outcome.rejected > 0 ? `${String(outcome.rejected)} rejected` : null,
  ].filter(Boolean)
  // A refused page carries its reasons twice, joined into `error` as well; show them once.
  const reasons = outcome.ok
    ? outcome.rejectedReasons
    : outcome.pageReasons.length > 0
      ? outcome.pageReasons
      : [outcome.error ?? 'no usable result']

  return (
    <li
      className={cn(
        'rounded-md border px-2 py-1.5 break-words',
        outcome.kept > 0 ? 'border-primary/30' : 'border-border',
      )}
    >
      <p className="font-medium text-foreground">{outcome.retailer}</p>
      {outcome.ok || outcome.found > 0 ? (
        <p className="text-muted-foreground">{counts.join(' · ')}</p>
      ) : null}
      {reasons.length > 0 ? (
        <ul className="mt-0.5 space-y-0.5 text-muted-foreground">
          {reasons.map((reason, index) => (
            <li key={`${String(index)}-${reason}`} className="flex items-start gap-1">
              <TriangleAlert className="mt-0.5 h-3 w-3 shrink-0 text-warning" aria-hidden />
              <span className="min-w-0">{reason}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  )
}

/**
 * §5.9's run from the phone — Batch 22b, owner item 1e.
 *
 * **Two taps, and the first saves nothing.** "Check sale pages" is the endpoint's dry run:
 * it asks each enabled shop for its sale page and reports what it would save. "Save deals"
 * appears only once a check has come back, and it asks the shops again rather than saving
 * the check, so what is saved is what the pages show at that moment.
 *
 * The three figures are §5.9's own (deals, shops with deals, deals skipped as already
 * owned), so the acceptance is read off the screen rather than inferred. Admin-only, like
 * the page and the endpoint.
 */
function SalePagesPanel() {
  const { profile } = useAuth()
  const queryClient = useQueryClient()
  const save = useMutation({
    mutationFn: () => runDealsScrape(false),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['deals'] })
      void queryClient.invalidateQueries({ queryKey: ['nav-sections'] })
    },
  })
  const check = useMutation({
    mutationFn: () => runDealsScrape(true),
    onMutate: () => save.reset(),
  })

  if (profile?.role !== 'admin') return null

  const result = save.data ?? check.data
  const busy = check.isPending || save.isPending
  const figures = result
    ? [
        { label: result.dryRun ? 'deals to save' : 'deals saved', value: result.written },
        { label: 'shops with deals', value: result.retailersWithDeals },
        { label: 'already owned, skipped', value: result.skippedOwned },
      ]
    : []

  return (
    <section
      aria-labelledby="sale-pages-title"
      className="space-y-3 rounded-lg border border-border bg-card p-4"
    >
      <div>
        <h2 id="sale-pages-title" className="text-sm font-semibold text-foreground">
          Sale pages
        </h2>
        <p className="text-xs text-muted-foreground">
          Reads each enabled shop’s sale page for discounted discs. Checking asks the shops
          but saves nothing.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={() => check.mutate()}
        >
          {check.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          Check sale pages
        </Button>
        {check.data && !save.isSuccess ? (
          <Button
            type="button"
            size="sm"
            disabled={busy}
            onClick={() => {
              if (window.confirm('Check the sale pages again and save the deals that pass?')) {
                save.mutate()
              }
            }}
          >
            {save.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save deals
          </Button>
        ) : null}
      </div>

      {check.isPending ? (
        <p className="text-xs text-muted-foreground">
          Asking each shop for its sale page… A shop that asks the app to wait can add up to a
          minute and a half.
        </p>
      ) : null}
      {check.isError ? (
        <p className="text-xs text-destructive">
          {queryErrorMessage(check.error, 'The sale pages could not be checked.')}
        </p>
      ) : null}
      {save.isError ? (
        <p className="text-xs text-destructive">
          {queryErrorMessage(save.error, 'The deals could not be saved.')}
        </p>
      ) : null}

      {result ? (
        <div className="space-y-2 text-xs">
          <p className="font-medium text-foreground">
            {result.dryRun ? 'Checked. Nothing is saved yet.' : 'Saved.'}
          </p>
          <dl className="grid grid-cols-3 gap-2">
            {figures.map((figure) => (
              <div
                key={figure.label}
                className="flex min-w-0 flex-col-reverse rounded-md border border-border px-2 py-1.5"
              >
                <dt className="text-xs leading-tight text-muted-foreground">
                  {figure.label}
                </dt>
                <dd className="text-lg font-semibold tabular-nums text-foreground">
                  {figure.value}
                </dd>
              </div>
            ))}
          </dl>
          {result.outcomes.length === 0 ? (
            <p className="text-muted-foreground">
              No shop was asked. Enable a retailer that has a sale page.
            </p>
          ) : (
            <ul className="space-y-1">
              {result.outcomes.map((outcome) => (
                <SalePageOutcome key={outcome.retailer} outcome={outcome} />
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
        <p className="text-xs text-muted-foreground">
          {retailer.scrapeFrequency} ·{' '}
          {/* Honest about what a seeded row actually is: a name and a URL, not a working
              scraper. The selectors are Batch 19's, and a plausible wrong one persists a
              plausible wrong price rather than erroring. */}
          {retailer.isConfigured ? (
            'selectors configured'
          ) : (
            <span className="text-warning">no selectors yet — Batch 19</span>
          )}
          {retailer.consecutiveFailures > 0
            ? ` · ${String(retailer.consecutiveFailures)} recent failures`
            : ''}
          {/* Batch X11: refused seven scheduled checks in a row, so asked once a week. */}
          {retailer.askedWeekly
            ? ` · asked weekly (refused ${String(retailer.refusedNights)} checks in a row)`
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
 * will be, it has to — and `text-primary` and `text-warning` are the same colour to the
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
                className="flex items-center gap-1 rounded-md border border-primary/40 px-2 py-0.5 text-xs text-primary"
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
                className="flex items-start gap-1.5 text-xs text-muted-foreground"
              >
                <Ban className="mt-0.5 h-3 w-3 shrink-0 text-warning" aria-hidden />
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

/**
 * §5.5's nightly job, and the record of what it has been doing.
 *
 * **The verdict line is the acceptance criterion rendered.** `DECISIONS.md` #112 corrected
 * it after a live run disproved the original: 7 wants × 5 shops predicted 35 rows and the
 * right answer was 6, because a boutique label does not stock a blockbuster and saying so
 * is not a failure (#107). So the comparison is against the pairs that were genuinely
 * answerable — attempted minus not-stocked — and the point of it is catching a *silent
 * mass failure*: if the scrapers break, that number stays high while `written` collapses.
 */
function NightlyPanel() {
  const queryClient = useQueryClient()
  const runsQuery = useQuery({ queryKey: ['scrape-runs'], queryFn: () => fetchScrapeRuns(10) })

  const runNow = useMutation({
    mutationFn: () => runDailyScrape(false),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['scrape-runs'] })
      void queryClient.invalidateQueries({ queryKey: ['wanted'] })
    },
  })

  const runs = runsQuery.data?.items ?? []

  return (
    <section className="rounded-lg border border-border p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-semibold text-foreground">The nightly run</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Prices every active want at every enabled shop, alerts on anything at or below
            its limit, then rolls up anything older than 90 days.{' '}
            <strong>Nothing schedules this from inside the app</strong> — a timer in one
            container becomes two runs the moment there are two containers, so the schedule
            is a Railway cron.
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          disabled={runNow.isPending}
          onClick={() => runNow.mutate()}
        >
          {runNow.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          Run it now
        </Button>
      </div>

      {runNow.isError ? (
        <p className="mt-2 text-sm text-destructive">
          {queryErrorMessage(runNow.error, 'The run could not be started.')}
        </p>
      ) : null}

      {runs.length === 0 ? (
        <p className="mt-3 text-xs text-muted-foreground">
          {runsQuery.isPending ? 'Loading…' : 'It has never run.'}
        </p>
      ) : (
        <ul className="mt-3 divide-y divide-border">
          {runs.map((run) => {
            const verdict = scrapeRunVerdict(run)
            return (
              <li key={run.id} className="py-2 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-foreground">
                    {formatDateTime(run.startedAt)}
                  </span>
                  <span className="rounded bg-muted px-1.5 py-0.5 text-muted-foreground">
                    {run.trigger}
                  </span>
                  {run.dryRun ? (
                    <span className="rounded bg-muted px-1.5 py-0.5 text-muted-foreground">
                      dry run
                    </span>
                  ) : null}
                  <span className={cn(verdict.ok ? 'text-success' : 'text-destructive')}>
                    {verdict.label}
                  </span>
                </div>
                <p className="mt-1 text-muted-foreground">
                  {run.notStocked} not stocked · {run.skipped} skipped · {run.failed} failed
                  {/* Shown separately from `failed` on purpose: an empty results page is a
                      shop saying nothing, and counting it as breakage is what #125 fixed. */}
                  {(run.noResults ?? 0) > 0 ? ` · ${run.noResults} no results` : ''}
                  {run.alertsQueued > 0 ? ` · ${run.alertsQueued} alerts` : ''}
                  {run.finishedAt === null ? ' · did not finish' : ''}
                </p>
                {run.failures.length > 0 ? (
                  <ul className="mt-1 space-y-0.5 text-muted-foreground">
                    {run.failures.slice(0, 3).map((failure, index) => (
                      <li key={index} className="truncate">
                        <TriangleAlert className="mr-1 inline h-3 w-3 text-warning" />
                        {failure.retailer}: {failure.reason}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {run.disabledRetailers.length > 0 ? (
                  <p className="mt-1 text-destructive">
                    <Ban className="mr-1 inline h-3 w-3" />
                    Auto-disabled: {run.disabledRetailers.join(', ')}
                  </p>
                ) : null}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

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

      {/* First, so it is in reach on a phone without scrolling past the built-ins. */}
      <SalePagesPanel />

      <BuiltInPanel />

      <RunPanel />

      <NightlyPanel />

      {items.length > 0 && retailersQuery.data?.configuredCount === 0 ? (
        <p className="flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/5 p-3 text-xs text-muted-foreground">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
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
