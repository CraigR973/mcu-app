import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Copy, Gift, Loader2, Plus, Trash2 } from 'lucide-react'
import type { GiftLink } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  createGiftLink,
  fetchGiftLinks,
  FORMATS,
  giftLinkUrl,
  revokeGiftLink,
  updateGiftLink,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

function Row({ link }: { link: GiftLink }) {
  const queryClient = useQueryClient()
  const [copied, setCopied] = useState(false)
  const url = giftLinkUrl(link.path)

  const refresh = () => void queryClient.invalidateQueries({ queryKey: ['gift-links'] })

  const toggle = useMutation({
    mutationFn: () =>
      updateGiftLink(link.id, {
        title: link.title,
        filterConfig: {
          maxPrice: link.filterConfig.maxPrice ?? null,
          formats: link.filterConfig.formats,
        },
        expiresAt: link.expiresAt,
        isActive: !link.isActive,
      }),
    onSuccess: refresh,
  })
  const revoke = useMutation({ mutationFn: () => revokeGiftLink(link.id), onSuccess: refresh })

  async function copy() {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <li
      className={cn(
        'space-y-2 rounded-lg border border-border bg-card p-3',
        link.isUsable ? '' : 'opacity-60',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium text-foreground">{link.title}</p>
          <p className="text-xs text-muted-foreground">
            {link.viewCount} view{link.viewCount === 1 ? '' : 's'}
            {link.lastViewedAt
              ? ` · last ${new Date(link.lastViewedAt).toLocaleDateString()}`
              : ''}
            {link.expiresAt
              ? ` · expires ${new Date(link.expiresAt).toLocaleDateString()}`
              : ''}
            {link.isUsable ? '' : ' · not working'}
          </p>
        </div>
        <div className="flex shrink-0 gap-1">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={toggle.isPending}
            onClick={() => toggle.mutate()}
          >
            {toggle.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {link.isActive ? 'Turn off' : 'Turn on'}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            aria-label={`Revoke ${link.title}`}
            disabled={revoke.isPending}
            onClick={() => revoke.mutate()}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded bg-muted px-2 py-1 text-[11px] text-foreground">
          {url}
        </code>
        <Button type="button" size="sm" variant="outline" onClick={() => void copy()}>
          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>

      <p className="text-[11px] text-muted-foreground">
        Shows:{' '}
        {[
          link.filterConfig.maxPrice ? `under £${link.filterConfig.maxPrice}` : null,
          link.filterConfig.formats.length > 0
            ? link.filterConfig.formats.join(', ')
            : null,
        ]
          .filter(Boolean)
          .join(' · ') || 'everything still wanted'}
      </p>
    </li>
  )
}

function NewLinkForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState('')
  const [maxPrice, setMaxPrice] = useState('')
  const [formats, setFormats] = useState<string[]>([])

  const create = useMutation({
    mutationFn: () =>
      createGiftLink({
        title: title.trim(),
        filterConfig: { maxPrice: maxPrice.trim() || null, formats },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gift-links'] })
      onDone()
    },
  })

  return (
    <div className="space-y-3 rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap gap-2">
        <Input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Mark's Christmas 2026"
          aria-label="List title"
          className="max-w-xs"
        />
        <Input
          value={maxPrice}
          onChange={(event) => setMaxPrice(event.target.value.replace(/[^\d.]/g, ''))}
          placeholder="Max price (optional)"
          aria-label="Max price"
          inputMode="decimal"
          className="max-w-[11rem]"
        />
      </div>
      <div className="flex flex-wrap gap-1">
        {FORMATS.map((format) => (
          <button
            key={format.value}
            type="button"
            onClick={() =>
              setFormats((current) =>
                current.includes(format.value)
                  ? current.filter((value) => value !== format.value)
                  : [...current, format.value],
              )
            }
            className={cn(
              'rounded-md px-2 py-0.5 text-xs transition-colors',
              formats.includes(format.value)
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:bg-muted',
            )}
          >
            {format.label}
          </button>
        ))}
      </div>
      {create.isError ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(create.error, 'Could not create a link.')}
        </p>
      ) : null}
      <div className="flex gap-2">
        <Button
          type="button"
          size="sm"
          disabled={create.isPending || title.trim().length === 0}
          onClick={() => create.mutate()}
        >
          Create link
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </div>
  )
}

/**
 * §12.1's gift link creator — §6.26's "shareable wanted list".
 *
 * **The link is a capability: anyone holding it can read the list.** So the page says what
 * it shows, tracks views, and offers "turn off" separately from "revoke" — §3.21's own
 * "can be deactivated without deleting". Turning a link back on restores the **same** URL,
 * which is the point: the one already sent to family keeps working rather than being
 * silently replaced.
 */
export default function GiftLinksPage() {
  const [creating, setCreating] = useState(false)

  const linksQuery = useQuery({ queryKey: ['gift-links'], queryFn: fetchGiftLinks })
  const items = linksQuery.data?.items ?? []
  const state = listState(linksQuery, items.length === 0)

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Gift links</h1>
          <p className="text-sm text-muted-foreground">
            A public page of your wanted list, for family buying presents. Anyone with the
            link can see it &mdash; it shows nothing else about your collection.
          </p>
        </div>
        {!creating ? (
          <Button type="button" size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" />
            New
          </Button>
        ) : null}
      </div>

      {creating ? <NewLinkForm onDone={() => setCreating(false)} /> : null}

      {state === 'loading' ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : state === 'offline' ? (
        <p className="text-sm text-muted-foreground">
          Waiting for the network — your gift links could not be loaded yet.
        </p>
      ) : state === 'error' ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(linksQuery.error, 'Could not load the gift links.')}
        </p>
      ) : state === 'empty' ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <Gift className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">No gift links yet.</p>
        </div>
      ) : (
        <ul className="space-y-2">
          {items.map((link) => (
            <Row key={link.id} link={link} />
          ))}
        </ul>
      )}
    </div>
  )
}
