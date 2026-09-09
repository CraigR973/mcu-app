import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { CircleCheck, CircleX, FlaskConical, Loader2 } from 'lucide-react'
import type { RetailerRow } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { FORMATS, testScraper } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

/**
 * §5.4's "test scraper" tool — *"runs selectors against live page, displays sample
 * results"*, so an admin can validate a retailer before enabling it.
 *
 * **A green tick here means "this looks like a price for this film", not "the page
 * loaded".** That distinction is the entire reason the tool exists: the failure this batch
 * is built around is a selector that fetches fine, parses fine, and returns the wrong
 * number. Every reason the check rejected a result is listed, because a scraper that has
 * started matching the wrong node is usually wrong in several ways at once.
 *
 * The request is made by the **server**, not the browser — a retailer would refuse a
 * cross-origin fetch, and the selectors have to run where the scraper will run. That is
 * also why `services/scraping/fetcher.py` refuses any URL that resolves somewhere
 * non-public.
 *
 * **The search template is sent verbatim and filled server-side.** This component used to
 * build the URL itself and knew only about `{query}`, so adding a `{format}` placeholder
 * silently sent Zavvi the literal text — matching *The Sheriff of Fractured Jaw (Dual
 * Format Edition)* for a search for *Jaws*. A tool that proves a scraper works has to
 * build its request the way the scraper does (`DECISIONS.md` #99).
 */
export function ScraperTester({ retailer }: { retailer: RetailerRow }) {
  const [title, setTitle] = useState('Heat')
  const [preferredFormat, setPreferredFormat] = useState('')
  const [open, setOpen] = useState(false)

  const test = useMutation({
    mutationFn: () =>
      testScraper({
        // The **template**, verbatim. The server substitutes `{query}` and `{format}`
        // with the same function the runner uses; doing it here is what sent Zavvi the
        // literal string `{format}` and priced a dual-format western as Jaws.
        url: retailer.searchUrlTemplate ?? retailer.baseUrl,
        scraperConfig: retailer.scraperConfig,
        expectedTitle: title.trim() || null,
        expectedCurrency: retailer.currency,
        preferredFormat: preferredFormat || null,
        expectedHost: retailer.baseUrl,
      }),
  })

  if (!open) {
    return (
      <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(true)}>
        <FlaskConical className="h-3.5 w-3.5" />
        Test
      </Button>
    )
  }

  return (
    <div className="w-full space-y-2 rounded-md border border-border bg-muted/30 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="A film to search for"
          aria-label="Test film title"
          className="h-8 max-w-[14rem] text-xs"
        />
        <select
          value={preferredFormat}
          onChange={(event) => setPreferredFormat(event.target.value)}
          aria-label="Test preferred format"
          className="h-8 rounded-md border border-input bg-background px-2 text-xs text-foreground"
        >
          <option value="">Any format</option>
          {FORMATS.map((format) => (
            <option key={format.value} value={format.value}>
              {format.label}
            </option>
          ))}
        </select>
        <Button
          type="button"
          size="sm"
          disabled={test.isPending || !retailer.searchUrlTemplate}
          onClick={() => test.mutate()}
        >
          {test.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Run selectors
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>
          Close
        </Button>
      </div>

      {!retailer.searchUrlTemplate ? (
        <p className="text-xs text-muted-foreground">
          This retailer has no search URL template, so there is nothing to search.
        </p>
      ) : null}

      {test.isError ? (
        <p className="text-xs text-destructive">
          {queryErrorMessage(test.error, 'The test could not be run.')}
        </p>
      ) : null}

      {test.data ? (
        <div className="space-y-1.5 text-xs">
          <p
            className={cn(
              'flex items-center gap-1.5 font-medium',
              test.data.ok ? 'text-primary' : 'text-destructive',
            )}
          >
            {test.data.ok ? (
              <CircleCheck className="h-4 w-4" />
            ) : (
              <CircleX className="h-4 w-4" />
            )}
            {test.data.ok
              ? 'Looks like a real price for this film'
              : 'Fetched, but this does not look like a price for this film'}
          </p>

          {test.data.error ? (
            <p className="text-destructive">{test.data.error}</p>
          ) : (
            <dl className="grid grid-cols-[7rem_1fr] gap-x-2 gap-y-0.5 text-muted-foreground">
              <dt>Title matched</dt>
              <dd className="text-foreground">{test.data.title ?? '—'}</dd>
              <dt>Price node read</dt>
              <dd className="text-foreground">{test.data.rawPriceText ?? '—'}</dd>
              <dt>Parsed as</dt>
              <dd className="text-foreground">
                {test.data.price ? `${test.data.price} ${test.data.currency ?? '?'}` : '—'}
              </dd>
              <dt>Listing link</dt>
              <dd className="truncate text-foreground">{test.data.listingUrl ?? '—'}</dd>
            </dl>
          )}

          {test.data.reasons.length > 0 ? (
            <ul className="list-disc space-y-0.5 pl-4 text-destructive">
              {test.data.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
