import { useState } from 'react'
import { Download, FileJson, FileSpreadsheet, Loader2, Printer } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'
import { downloadExport, openPrintableCollection } from '@/lib/api'

/**
 * §13.3 and §13.4's export links — Batch S3 moved them here from the foot of Stats.
 *
 * **It is a maintenance action, not a reading one.** Stats became a *section* of the
 * merged Home when snag 5 was fixed, and a row of download buttons at the bottom of a
 * page somebody opens to look at charts was already an odd fit; inside a longer merged
 * page it would have been buried. Admin is where the other four things of this kind live.
 */
export default function ExportPage() {
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function run(name: string, action: () => Promise<void>) {
    setBusy(name)
    setError(null)
    try {
      await action()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The export failed.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="page-shell-narrow space-y-6">
      <PageHeader
        eyebrow="Portable archive"
        title="Export"
        description="One row per disc, in whichever format travels best."
      />

      <section className="archive-panel space-y-4 p-5">
        <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
          One row per disc. The printable view opens in a new tab — use your
          browser&rsquo;s Print dialog and &ldquo;Save as PDF&rdquo;.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={busy !== null}
            onClick={() => void run('csv', () => downloadExport('csv'))}
          >
            {busy === 'csv' ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <FileSpreadsheet className="h-4 w-4" />
            )}
            CSV
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={busy !== null}
            onClick={() => void run('json', () => downloadExport('json'))}
          >
            {busy === 'json' ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <FileJson className="h-4 w-4" />
            )}
            JSON
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={busy !== null}
            onClick={() => void run('html', () => downloadExport('html'))}
          >
            {busy === 'html' ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Download className="h-4 w-4" aria-hidden />
            )}
            HTML
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={busy !== null}
            onClick={() => void run('print', openPrintableCollection)}
          >
            {busy === 'print' ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Printer className="h-4 w-4" />
            )}
            Printable view
          </Button>
        </div>
        {error ? (
          <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}
      </section>
    </div>
  )
}
