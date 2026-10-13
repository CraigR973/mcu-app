import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bot, Loader2, Send, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router-dom'

import { MicButton } from '@/components/MicButton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { StatePanel } from '@/components/ui/state-panel'
import {
  askAi,
  fetchAiSettings,
  fetchAiStatus,
  fetchAiUsage,
  formatAiCost,
  updateAiSettings,
} from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

/**
 * §9.7's caps, and the one-question box that proves §9.1 works.
 *
 * The full chat now lives at `/assistant`; this settings page keeps the one-question health
 * check alongside the personal caps. Cost remains visible because the person reading the
 * answer is also the person paying for it.
 */
/** The assistant's caps, usage and one-question health check, without page chrome —
 *  Batch S3 folded this page into `/settings` as one of two tabs. `/settings/ai` still
 *  resolves; it redirects. */
export function AiSettings() {
  const queryClient = useQueryClient()
  const [prompt, setPrompt] = useState('')

  const status = useQuery({ queryKey: ['ai-status'], queryFn: fetchAiStatus })
  const usage = useQuery({ queryKey: ['ai-usage'], queryFn: fetchAiUsage })
  const settings = useQuery({ queryKey: ['ai-settings'], queryFn: fetchAiSettings })

  const save = useMutation({
    mutationFn: (input: { dailyMessageCap?: number; dailyCostCapUsd?: number }) =>
      updateAiSettings(input),
    onSuccess: (updated) => {
      queryClient.setQueryData(['ai-settings'], updated)
      void queryClient.invalidateQueries({ queryKey: ['ai-usage'] })
    },
  })

  const ask = useMutation({
    mutationFn: (question: string) => askAi(question),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['ai-usage'] }),
  })

  const answer = ask.data
  const capped = answer?.stopReason === 'cap_reached'
  const usagePercent = usage.data
    ? Math.min(
        100,
        usage.data.messageCap === 0
          ? 100
          : (usage.data.messages / usage.data.messageCap) * 100,
      )
    : 0

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Button asChild size="sm" variant="outline">
          <Link to="/assistant">
            <Bot className="h-4 w-4" aria-hidden />
            Open chat
          </Link>
        </Button>
      </div>

      {status.data && !status.data.configured ? (
        <p role="alert" className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden />
          <span>
            The assistant is not configured on the server — there is no API key set. Nothing
            else in the app is affected, and nothing here will work until it is.
          </span>
        </p>
      ) : null}
      {status.isError ? (
        <StatePanel
          compact
          tone="error"
          title="Assistant status unavailable"
          description={queryErrorMessage(status.error, 'The server status could not be checked.')}
        />
      ) : null}

      <section className="archive-panel p-4 sm:p-5">
        <h2 className="section-heading">Ask something</h2>
        <form
          className="mt-3 flex flex-wrap gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            if (prompt.trim()) ask.mutate(prompt.trim())
          }}
        >
          <Input
            className="min-w-0 flex-1"
            value={prompt}
            maxLength={4000}
            placeholder="Which 4Ks have I not watched?"
            aria-label="Question for the assistant"
            onChange={(event) => setPrompt(event.target.value)}
          />
          <MicButton
            disabled={ask.isPending}
            onTranscript={(text) =>
              setPrompt((current) => (current ? `${current} ${text}` : text))
            }
          />
          <Button type="submit" disabled={ask.isPending || !prompt.trim()}>
            {ask.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Send className="mr-2 h-4 w-4" aria-hidden />
            )}
            Ask
          </Button>
        </form>

        {ask.isError ? (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {queryErrorMessage(ask.error, 'The question could not be sent.')}
          </p>
        ) : null}

        {answer ? (
          <div className="mt-4 space-y-2">
            <p
              className={cn(
                'whitespace-pre-wrap rounded-md p-3 text-sm',
                capped || answer.error
                  ? 'border border-warning/45 bg-warning/10 text-foreground'
                  : 'bg-muted text-foreground',
              )}
            >
              {answer.text}
            </p>
            {!capped ? (
              <p className="text-xs text-muted-foreground">
                {answer.model} · {answer.inputTokens.toLocaleString()} in ·{' '}
                {answer.outputTokens.toLocaleString()} out · {formatAiCost(answer.costUsd)} ·{' '}
                {answer.latencyMs} ms
              </p>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="archive-panel p-4 sm:p-5">
        <h2 className="section-heading">Today</h2>
        {usage.data ? (
          <>
            <p className="mt-2 text-sm">
              <strong>{usage.data.messages}</strong> of {usage.data.messageCap} messages ·{' '}
              {formatAiCost(usage.data.costUsd)} of ${usage.data.costCapUsd}
            </p>
            <div
              className="mt-2 h-2 w-full overflow-hidden rounded-full bg-muted"
              role="progressbar"
              aria-label="Daily assistant message usage"
              aria-valuemin={0}
              aria-valuemax={usage.data.messageCap}
              aria-valuenow={Math.min(usage.data.messages, usage.data.messageCap)}
              aria-valuetext={`${usage.data.messages} of ${usage.data.messageCap} messages used`}
            >
              <div
                className={cn(
                  'h-full rounded-full transition-all',
                  usage.data.blocked ? 'bg-destructive' : 'bg-success',
                )}
                style={{ width: `${usagePercent}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              {usage.data.limitMessage ??
                `Resets at ${new Date(usage.data.resetsAt).toLocaleTimeString()}.`}
            </p>
          </>
        ) : usage.isError ? (
          <StatePanel
            compact
            className="mt-3"
            tone="error"
            title="Usage unavailable"
            description={queryErrorMessage(usage.error, 'Today’s usage could not be loaded.')}
          />
        ) : (
          <StatePanel compact className="mt-3" tone="loading" title="Loading usage" />
        )}
      </section>

      <section className="archive-panel p-4 sm:p-5">
        <h2 className="section-heading">Your limits</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Two ceilings, because a message count alone does not bound spend — the same
          question costs more at the end of a long conversation than at the start. Up to 200
          messages and $10 a day. Set the message cap to 0 to turn the assistant off for
          yourself.
        </p>
        {settings.data ? (
          <div className="mt-3 flex flex-wrap items-end gap-4">
            <label className="text-sm">
              <span className="mb-1 block text-muted-foreground">Messages per day</span>
              <Input
                type="number"
                min={0}
                max={200}
                className="w-32"
                defaultValue={settings.data.dailyMessageCap}
                onBlur={(event) => {
                  // A cleared box is "no change", not zero (Batch X7).
                  if (event.target.value.trim() === '') return
                  save.mutate({ dailyMessageCap: Number(event.target.value) })
                }}
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-muted-foreground">Spend per day (USD)</span>
              <Input
                type="number"
                min={0.5}
                max={10}
                step="0.5"
                className="w-32"
                defaultValue={settings.data.dailyCostCapUsd}
                onBlur={(event) => {
                  // A cleared box used to save 0, which lifted the money ceiling
                  // (AI45-05). Blank is now "no change"; the server refuses 0.
                  if (event.target.value.trim() === '') return
                  save.mutate({ dailyCostCapUsd: Number(event.target.value) })
                }}
              />
            </label>
            {save.isPending ? (
              <Loader2 className="mb-2 h-4 w-4 animate-spin" aria-hidden />
            ) : null}
          </div>
        ) : settings.isError ? (
          <StatePanel
            compact
            className="mt-3"
            tone="error"
            title="Limits unavailable"
            description={queryErrorMessage(settings.error, 'Your limits could not be loaded.')}
          />
        ) : (
          <StatePanel compact className="mt-3" tone="loading" title="Loading limits" />
        )}
        {save.isError ? (
          <p role="alert" className="mt-2 text-sm text-destructive">
            {queryErrorMessage(save.error, 'Could not save that limit.')}
          </p>
        ) : null}
      </section>
    </div>
  )
}
