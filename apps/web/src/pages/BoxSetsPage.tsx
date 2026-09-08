import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Boxes, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { BoxSet } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/context/auth'
import { completionLabel, createBoxSet, fetchBoxSets } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

function CompletionBar({ set }: { set: BoxSet }) {
  if (set.expectedCount === null) {
    // Unmeasured, not incomplete. A bar at 0% would be a red mark against a set whose
    // size simply nobody recorded.
    return <p className="text-xs text-muted-foreground">{completionLabel(set)} · size not recorded</p>
  }
  const pct = Math.min(100, Math.round((set.ownedCount / set.expectedCount) * 100))
  return (
    <div className="space-y-1">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn('h-full rounded-full', set.isComplete ? 'bg-primary' : 'bg-amber-500')}
          style={{ width: `${String(pct)}%` }}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        {completionLabel(set)}
        {set.isComplete ? ' · complete' : ''}
      </p>
    </div>
  )
}

function NewSetForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [label, setLabel] = useState('')
  const [expected, setExpected] = useState('')

  const create = useMutation({
    mutationFn: () =>
      createBoxSet({
        name: name.trim(),
        label: label.trim() || null,
        // Left null rather than defaulted: "how many discs came in this box" is a fact
        // about the box, and guessing it would make every completion figure a guess.
        expectedCount: expected.trim() === '' ? null : Number(expected),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['box-sets'] })
      onDone()
    },
  })

  return (
    <div className="space-y-3 rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap gap-2">
        <Input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Columbia Noir Vol 4"
          aria-label="Box set name"
          className="max-w-xs"
        />
        <Input
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          placeholder="Indicator"
          aria-label="Publisher"
          className="max-w-[10rem]"
        />
        <Input
          value={expected}
          onChange={(event) => setExpected(event.target.value.replace(/\D/g, ''))}
          placeholder="Discs in the box"
          aria-label="Expected count"
          inputMode="numeric"
          className="max-w-[10rem]"
        />
      </div>
      {create.isError ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(create.error, 'Could not create the box set.')}
        </p>
      ) : null}
      <div className="flex gap-2">
        <Button
          type="button"
          size="sm"
          disabled={create.isPending || name.trim().length === 0}
          onClick={() => create.mutate()}
        >
          Create
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </div>
  )
}

/**
 * §11.4's box set grid — "browsing box sets shows all with status".
 *
 * Unpaginated, matching the endpoint. The ceiling is the number of physical boxes on
 * the shelves, which is a couple of dozen against 1,857 discs; a "next page" control
 * here would hide sets for no benefit.
 */
export default function BoxSetsPage() {
  const { profile } = useAuth()
  const [creating, setCreating] = useState(false)

  const boxSetsQuery = useQuery({ queryKey: ['box-sets'], queryFn: fetchBoxSets })
  const items = boxSetsQuery.data?.items ?? []
  const state = listState(boxSetsQuery, items.length === 0)

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4 md:p-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Box sets</h1>
          <p className="text-sm text-muted-foreground">
            Physical boxes and the discs in them, with how much of each set is on the
            shelf.
          </p>
        </div>
        {profile?.role === 'admin' && !creating ? (
          <Button type="button" size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" />
            New
          </Button>
        ) : null}
      </div>

      {creating ? <NewSetForm onDone={() => setCreating(false)} /> : null}

      {state === 'loading' ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : state === 'offline' ? (
        <p className="text-sm text-muted-foreground">
          Waiting for the network — the box sets could not be loaded yet.
        </p>
      ) : state === 'error' ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(boxSetsQuery.error, 'Could not load the box sets.')}
        </p>
      ) : state === 'empty' ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <Boxes className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">
            No box sets yet.
            {profile?.role === 'admin'
              ? ' Create one, then add its discs from the set’s own page.'
              : ''}
          </p>
        </div>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((set) => (
            <li key={set.id} className="rounded-lg border border-border bg-card p-3">
              <Link
                to={`/box-sets/${set.id}`}
                className="font-medium text-foreground hover:underline"
              >
                {set.name}
              </Link>
              <p className="mb-2 text-xs text-muted-foreground">
                {[set.label, set.seriesName].filter(Boolean).join(' · ') || ' '}
              </p>
              <CompletionBar set={set} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
