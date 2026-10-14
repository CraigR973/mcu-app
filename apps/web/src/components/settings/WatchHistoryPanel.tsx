import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Clock, Loader2, RefreshCw } from 'lucide-react'
import type { SyncResponse } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { StatePanel } from '@/components/ui/state-panel'
import { fetchWatchHistoryStatus, setLetterboxdUsername, syncWatchHistory } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

/** "3 days ago", or the date once that stops being useful.
 *
 *  **Relative, because the question is about the gap.** The diary feed returns 50 entries
 *  and no more, and Mark cycles his in about eight weeks — so what a reader needs to judge
 *  is *how long it has been*, not what the calendar said. An absolute date makes them do
 *  the subtraction. */
export function sinceLabel(iso: string, now: number = Date.now()): string {
  const then = new Date(iso)
  const days = Math.floor((now - then.getTime()) / 86_400_000)
  if (Number.isNaN(days)) return 'at an unknown time'
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 56) return `${String(days)} days ago`
  return `on ${then.toLocaleDateString()}`
}

/**
 * Batch S5, snag 10a — the watch-history sync.
 *
 * **The last-run line is the feature, not the button.** `DECISIONS.md` #159: the public
 * diary feed carries only the most recent **50** viewings. Craig's reaches back to
 * January; Mark's only about eight weeks, because he watches far more. A sync running
 * less often than roughly monthly **loses his entries silently** — the feed simply stops
 * mentioning them, and nothing errors. So the interval is a correctness property, and a
 * panel that did not say when it last ran would hide the one thing worth knowing.
 *
 * **A button rather than a schedule**, because both Railway crons have been crashing on
 * every scheduled fire since 2026-09-10 (`OWNER-ACTIONS.md` item 1). #156 requires the
 * first version to work the way the scraper does; the sync record already carries a
 * `trigger` column that accepts `cron`, so adding one later needs no migration.
 */
export function WatchHistoryPanel() {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<string | null>(null)
  const [result, setResult] = useState<SyncResponse | null>(null)

  const status = useQuery({
    queryKey: ['watch-history-status'],
    queryFn: fetchWatchHistoryStatus,
  })

  const saveUsername = useMutation({
    mutationFn: (value: string) => setLetterboxdUsername(value.trim() || null),
    onSuccess: () => {
      setDraft(null)
      void queryClient.invalidateQueries({ queryKey: ['watch-history-status'] })
    },
  })

  const sync = useMutation({
    mutationFn: syncWatchHistory,
    onSuccess: (response) => {
      setResult(response)
      void queryClient.invalidateQueries({ queryKey: ['watch-history-status'] })
      // A sync writes watches, which several other surfaces read.
      void queryClient.invalidateQueries({ queryKey: ['stats'] })
      void queryClient.invalidateQueries({ queryKey: ['memories'] })
    },
  })

  if (status.isPending) {
    return <StatePanel compact tone="loading" title="Loading your watch history" />
  }
  if (status.isError) {
    return (
      <StatePanel
        compact
        tone="error"
        title="Watch history is unavailable"
        description={queryErrorMessage(status.error, 'Could not load the sync status.')}
      />
    )
  }

  const { letterboxdUsername, lastSync, watchCount } = status.data
  const editing = draft !== null || !letterboxdUsername

  return (
    <section className="archive-panel space-y-4 p-5" aria-labelledby="watch-history-heading">
      <div>
        <p className="page-kicker">Letterboxd</p>
        <h3 id="watch-history-heading" className="section-heading">Watch history</h3>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          Reads your <strong>public</strong> diary feed and logs what you have watched.
          No password, and nothing is posted back.
        </p>
      </div>

      {editing ? (
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            saveUsername.mutate(draft ?? '')
          }}
        >
          <label className="min-w-48 flex-1">
            <span className="field-label">Letterboxd username</span>
            <Input
              value={draft ?? letterboxdUsername ?? ''}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="e.g. CraigR973"
              autoComplete="off"
              aria-describedby="letterboxd-username-hint"
            />
          </label>
          <Button type="submit" disabled={saveUsername.isPending}>
            {saveUsername.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
            Save
          </Button>
          {letterboxdUsername ? (
            <Button type="button" variant="ghost" onClick={() => setDraft(null)}>
              Cancel
            </Button>
          ) : null}
          <p id="letterboxd-username-hint" className="field-hint w-full">
            Your diary has to be public for the feed to work. Nothing else is needed.
          </p>
        </form>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm text-foreground">
            Syncing <span className="font-semibold">{letterboxdUsername}</span>
          </span>
          <Button type="button" variant="ghost" size="sm" onClick={() => setDraft(letterboxdUsername)}>
            Change
          </Button>
        </div>
      )}

      {saveUsername.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {queryErrorMessage(saveUsername.error, 'That username could not be saved.')}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
        <Button
          type="button"
          disabled={!letterboxdUsername || sync.isPending}
          onClick={() => sync.mutate()}
        >
          {sync.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <RefreshCw className="h-4 w-4" aria-hidden />
          )}
          Sync now
        </Button>

        {/* The line this panel exists for. Batch X5 (UX48-04): the feed's window and the
            weekly sync are said, so nobody has to know them to trust the history. */}
        <p className="flex items-start gap-1.5 text-sm text-muted-foreground">
          <Clock className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>
            Letterboxd&rsquo;s feed holds your last 50 diary entries. The app syncs weekly;{' '}
            {lastSync ? (
              <>
                last synced <strong className="text-foreground">{sinceLabel(lastSync.startedAt)}</strong>
                {lastSync.error ? ', and it failed.' : ` · ${String(lastSync.written)} new.`}
              </>
            ) : (
              'not synced yet.'
            )}
          </span>
        </p>

        <span className="ml-auto text-sm tabular-nums text-muted-foreground">
          {watchCount.toLocaleString()} {watchCount === 1 ? 'watch' : 'watches'} logged
        </span>
      </div>

      {lastSync?.error ? (
        <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {lastSync.error}
        </p>
      ) : null}

      {sync.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {queryErrorMessage(sync.error, 'The sync could not be run.')}
        </p>
      ) : null}

      {result ? (
        <div className="space-y-2 rounded-md border border-border bg-surface-sunken/40 px-3 py-2.5 text-sm">
          <p className="text-foreground">
            Read {result.run.entries}, wrote <strong>{result.run.written}</strong>,{' '}
            {result.run.alreadyImported} already logged, {result.run.notInCollection} not in the
            collection.
          </p>

          {/* Not an error. 50 is Letterboxd's cap, so a full feed means the gap since the
              last sync may have swallowed entries — the interval is too long. */}
          {result.feedWasFull ? (
            <p className="flex items-start gap-2 text-warning">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <span>
                The feed came back full at 50 entries, so older viewings may already have
                dropped off it.
              </span>
            </p>
          ) : null}

          {result.ambiguities.length > 0 ? (
            <div className="text-muted-foreground">
              <p className="font-semibold text-foreground">
                {result.ambiguities.length} need you to choose — nothing was guessed:
              </p>
              <ul className="mt-1 space-y-0.5">
                {result.ambiguities.map((line) => (
                  <li key={line} className="text-xs">{line}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}
