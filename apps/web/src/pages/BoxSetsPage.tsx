import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Boxes, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { BoxSet } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
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
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label={`${set.name} completion`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
      >
        <div
          className={cn('h-full rounded-full', set.isComplete ? 'bg-primary' : 'bg-warning')}
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
    <form
      className="archive-panel space-y-3 p-4 sm:p-5"
      onSubmit={(event) => {
        event.preventDefault()
        create.mutate()
      }}
    >
      <div className="flex flex-wrap gap-2">
        <Input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Columbia Noir Vol 4"
          aria-label="Box set name"
          className="w-full sm:max-w-xs"
        />
        <Input
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          placeholder="Indicator"
          aria-label="Publisher"
          className="w-full sm:max-w-[10rem]"
        />
        <Input
          value={expected}
          onChange={(event) => setExpected(event.target.value.replace(/\D/g, ''))}
          placeholder="Discs in the box"
          aria-label="Expected count"
          inputMode="numeric"
          className="w-full sm:max-w-[10rem]"
        />
      </div>
      {create.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {queryErrorMessage(create.error, 'Could not create the box set.')}
        </p>
      ) : null}
      <div className="flex gap-2">
        <Button
          type="submit"
          disabled={create.isPending || name.trim().length === 0}
        >
          Create
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
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
    <div className="page-shell-narrow space-y-5">
      <PageHeader
        eyebrow="Physical archive"
        title="Box sets"
        description="Physical boxes and the discs in them, with how much of each set is on the shelf."
        actions={profile?.role === 'admin' && !creating ? (
          <Button type="button" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" />
            New box set
          </Button>
        ) : null}
      />

      {creating ? <NewSetForm onDone={() => setCreating(false)} /> : null}

      {state === 'loading' ? (
        <StatePanel tone="loading" title="Loading box sets" />
      ) : state === 'offline' ? (
        <StatePanel
          tone="offline"
          title="Box sets need the network"
          description="Reconnect to load the physical boxes in the archive."
        />
      ) : state === 'error' ? (
        <StatePanel
          tone="error"
          title="Box sets unavailable"
          description={queryErrorMessage(boxSetsQuery.error, 'Could not load the box sets.')}
        />
      ) : state === 'empty' ? (
        <StatePanel
          tone="empty"
          icon={Boxes}
          title="No box sets yet"
          description={profile?.role === 'admin'
            ? 'Create one, then add its discs from the set’s own page.'
            : 'No physical boxes have been catalogued yet.'}
        />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((set) => (
            <li key={set.id} className="archive-panel overflow-hidden">
              <Link
                to={`/box-sets/${set.id}`}
                className="block min-h-11 p-4 text-foreground transition-colors hover:bg-muted/35"
              >
                <span className="font-display text-lg font-semibold">{set.name}</span>
                <span className="mb-3 block text-xs text-muted-foreground">
                  {[set.label, set.seriesName].filter(Boolean).join(' · ') || 'Publisher not recorded'}
                </span>
                <CompletionBar set={set} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
