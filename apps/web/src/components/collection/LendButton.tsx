import { useId, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { HandHeart, HandHelping, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { LoanActions } from './LoanActions'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/context/auth'
import { fetchLoans, lendDisc, loanDueLabel, loanState, loanStateLabel } from '@/lib/api'
import { formatShortDate } from '@/lib/utils'
import { listState, queryErrorMessage } from '@/lib/query-state'

interface Props {
  collectionItemId: string
}

type Mode = 'idle' | 'lend' | 'borrow' | 'ask'

/**
 * Lend this specific disc, borrow it, or say it is back — §12.5's "mark as lent / returned",
 * and Batch W3's borrowing (`DECISIONS.md` #249).
 *
 * **On the copy, not on the film.** A loan is about one physical object: owning *Heat* on
 * 4K and on DVD means two discs, and only one of them left the house. `loans` points at
 * `collection_item_id` for the same reason.
 *
 * **Both people, since W3.** Mark lends the discs as much as Craig does, and Craig borrows
 * them: **Borrow** records the person as the borrower, by their profile, so the reminder can
 * say "You've had it". **Lend** names anyone else. "Mark returned" became **Returned**, since
 * Mark is a person here.
 */
export function LendButton({ collectionItemId }: Props) {
  const { profile } = useAuth()
  const queryClient = useQueryClient()
  const borrowerId = useId()
  const dueId = useId()
  const neededId = useId()
  const [mode, setMode] = useState<Mode>('idle')
  const [borrower, setBorrower] = useState('')
  const [due, setDue] = useState('')
  const [needed, setNeeded] = useState('')

  // Include returns, so a copy left on the table never appears to be shelved.
  const loansQuery = useQuery({ queryKey: ['loans', false], queryFn: () => fetchLoans(false) })
  const loans = loansQuery.data?.items ?? []
  const state = listState(loansQuery, loans.length === 0)
  const active = loans.find((loan) => loan.collectionItemId === collectionItemId && loan.isCurrent !== false)

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ['loans'] })
    void queryClient.invalidateQueries({ queryKey: ['activity'] })
  }

  const lend = useMutation({
    mutationFn: () => {
      const dueDate = due || null
      if (mode === 'ask' && profile) return lendDisc({ collectionItemId, borrowerProfileId: profile.id, state: 'asked_for', neededBy: needed, ...(due ? { dueDate: due } : {}) })
      if (mode === 'borrow' && profile) return lendDisc({ collectionItemId, borrowerProfileId: profile.id, dueDate })
      return lendDisc({ collectionItemId, borrowerName: borrower.trim(), dueDate })
    },
    onSuccess: () => {
      setMode('idle')
      setBorrower('')
      setDue('')
      setNeeded('')
      refresh()
    },
  })

  function open(next: Mode) {
    lend.reset()
    setMode(next)
  }

  if (state === 'loading') {
    return (
      <p role="status" className="inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Checking loan status…
      </p>
    )
  }

  if (state === 'offline') {
    return (
      <div className="space-y-2" role="status">
        <p className="text-sm text-muted-foreground">
          Loan status is waiting for the network.
        </p>
        <Button type="button" size="sm" variant="outline" onClick={() => void loansQuery.refetch()}>
          Try again
        </Button>
      </div>
    )
  }

  if (state === 'error') {
    return (
      <div className="space-y-2" role="alert">
        <p className="text-sm text-destructive">
          {queryErrorMessage(loansQuery.error, 'Could not check whether this disc is on loan.')}
        </p>
        <Button type="button" size="sm" variant="outline" onClick={() => void loansQuery.refetch()}>
          Try again
        </Button>
      </div>
    )
  }

  const status = active ? (
    <div className="space-y-2">
      <p className="text-sm font-medium">{loanStateLabel(active)}</p>
      {loanState(active) === 'out' ? (
        <p className="text-sm text-muted-foreground">
          {active.borrowerProfileId === profile?.id ? <span>With you</span> : <>With <span>{active.borrowerName}</span></>}
          {' · '}{loanDueLabel(active)}
        </p>
      ) : loanState(active) === 'asked_for' ? (
        <p className="text-sm text-muted-foreground">{active.borrowerName} · needed by {active.neededBy ? formatShortDate(active.neededBy) : 'not set'}</p>
      ) : <p className="text-sm text-muted-foreground">Home position: {active.locationLabel}</p>}
      <LoanActions loan={active} />
    </div>
  ) : null
  if (active && ['asked_for', 'out'].includes(loanState(active))) return status

  if (mode === 'idle') {
    return (
      <div className="space-y-3">
        {status}
        <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" variant="ghost" onClick={() => open('lend')}>
          <HandHeart className="h-3.5 w-3.5" />
          Lend
        </Button>
        {profile ? (
          <Button type="button" size="sm" variant="ghost" onClick={() => open('borrow')}>
            <HandHelping className="h-3.5 w-3.5" />
            Borrow
          </Button>
        ) : null}
        {profile ? <Button type="button" size="sm" variant="ghost" onClick={() => open('ask')}>Ask to borrow</Button> : null}
        </div>
      </div>
    )
  }

  const borrowing = mode === 'borrow' || mode === 'ask'
  const asking = mode === 'ask'
  return (
    <form
      className="space-y-3"
      aria-busy={lend.isPending}
      aria-label={asking ? 'Ask to borrow this disc' : borrowing ? 'Borrow this disc' : 'Lend this disc'}
      onSubmit={(event) => {
        event.preventDefault()
        if (borrowing || borrower.trim()) lend.mutate()
      }}
    >
      {borrowing ? (
        <p className="text-sm text-muted-foreground">{asking ? 'Ask for this copy. The other person gets a notification.' : 'You are taking this disc home.'}</p>
      ) : (
        <>
          <label htmlFor={borrowerId} className="block text-sm font-medium text-foreground">
            Borrower
          </label>
          <Input
            id={borrowerId}
            value={borrower}
            onChange={(event) => setBorrower(event.target.value)}
            placeholder="Who has it?"
            required
          />
        </>
      )}
      {asking ? <>
        <label htmlFor={neededId} className="block text-sm font-medium text-foreground">Needed by</label>
        <Input id={neededId} type="date" required value={needed} onChange={(event) => setNeeded(event.target.value)} />
      </> : null}
      <label htmlFor={dueId} className="block text-sm font-medium text-foreground">
        Due back <span className="font-normal text-muted-foreground">(optional)</span>
      </label>
      <Input
        id={dueId}
        type="date"
        value={due}
        onChange={(event) => setDue(event.target.value)}
      />
      {lend.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {queryErrorMessage(lend.error, 'Could not record the loan.')}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button
          type="submit"
          size="sm"
          disabled={lend.isPending || (!borrowing && borrower.trim().length === 0)}
        >
          {lend.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
          {asking ? 'Send request' : borrowing ? 'I’m borrowing it' : 'Lend it'}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          disabled={lend.isPending}
          onClick={() => setMode('idle')}
        >
          Cancel
        </Button>
      </div>
    </form>
  )
}
