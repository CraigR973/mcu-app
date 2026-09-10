import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bot, Loader2, Send, TriangleAlert } from 'lucide-react'

import { MicButton } from '@/components/MicButton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
 * **Batch 31 owns the real chat** — conversations, streaming, tools and the floating
 * button. What is here is deliberately the smallest thing that makes the plumbing visible:
 * ask one question, see the answer, and see exactly what it cost. That last part is not a
 * developer detail — the person reading the answer is the person paying for it, and a cap
 * you cannot watch approaching is a cap that surprises you.
 */
export default function AiSettingsPage() {
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

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <Bot className="h-6 w-6" aria-hidden />
          Assistant
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Questions about the collection, answered by Claude. Chat, conversations and tools
          arrive in the next batch — this is the plumbing and the limits.
        </p>
      </header>

      {status.data && !status.data.configured ? (
        <p className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden />
          <span>
            The assistant is not configured on the server — there is no API key set. Nothing
            else in the app is affected, and nothing here will work until it is.
          </span>
        </p>
      ) : null}

      <section className="rounded-lg border border-border p-4">
        <h2 className="font-semibold">Ask something</h2>
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
          <p className="mt-3 text-sm text-destructive">
            {queryErrorMessage(ask.error, 'The question could not be sent.')}
          </p>
        ) : null}

        {answer ? (
          <div className="mt-4 space-y-2">
            <p
              className={cn(
                'whitespace-pre-wrap rounded-md p-3 text-sm',
                capped || answer.error
                  ? 'bg-amber-500/10 text-amber-900 dark:text-amber-200'
                  : 'bg-muted',
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

      <section className="rounded-lg border border-border p-4">
        <h2 className="font-semibold">Today</h2>
        {usage.data ? (
          <>
            <p className="mt-2 text-sm">
              <strong>{usage.data.messages}</strong> of {usage.data.messageCap} messages ·{' '}
              {formatAiCost(usage.data.costUsd)} of ${usage.data.costCapUsd}
            </p>
            <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={cn(
                  'h-full rounded-full transition-all',
                  usage.data.blocked ? 'bg-destructive' : 'bg-emerald-600',
                )}
                style={{
                  width: `${Math.min(
                    100,
                    usage.data.messageCap === 0
                      ? 100
                      : (usage.data.messages / usage.data.messageCap) * 100,
                  )}%`,
                }}
              />
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              {usage.data.limitMessage ??
                `Resets at ${new Date(usage.data.resetsAt).toLocaleTimeString()}.`}
            </p>
          </>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">Loading…</p>
        )}
      </section>

      <section className="rounded-lg border border-border p-4">
        <h2 className="font-semibold">Your limits</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Two ceilings, because a message count alone does not bound spend — the same
          question costs more at the end of a long conversation than at the start. Set the
          message cap to 0 to turn the assistant off for yourself.
        </p>
        {settings.data ? (
          <div className="mt-3 flex flex-wrap items-end gap-4">
            <label className="text-sm">
              <span className="mb-1 block text-muted-foreground">Messages per day</span>
              <Input
                type="number"
                min={0}
                max={10000}
                className="w-32"
                defaultValue={settings.data.dailyMessageCap}
                onBlur={(event) =>
                  save.mutate({ dailyMessageCap: Number(event.target.value) })
                }
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-muted-foreground">Spend per day (USD)</span>
              <Input
                type="number"
                min={0}
                max={1000}
                step="0.5"
                className="w-32"
                defaultValue={settings.data.dailyCostCapUsd}
                onBlur={(event) =>
                  save.mutate({ dailyCostCapUsd: Number(event.target.value) })
                }
              />
            </label>
            {save.isPending ? (
              <Loader2 className="mb-2 h-4 w-4 animate-spin" aria-hidden />
            ) : null}
          </div>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">Loading…</p>
        )}
        {save.isError ? (
          <p className="mt-2 text-sm text-destructive">
            {queryErrorMessage(save.error, 'Could not save that limit.')}
          </p>
        ) : null}
      </section>
    </div>
  )
}
