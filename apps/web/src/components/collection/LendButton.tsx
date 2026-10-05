import { useId, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { HandHeart, HandHelping, Loader2, Undo2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/context/auth'
import { fetchLoans, lendDisc, loanDueLabel, returnLoan } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

interface Props {
  collectionItemId: string
}

type Mode = 'idle' | 'lend' | 'borrow'

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
  const [mode, setMode] = useState<Mode>('idle')
  const [borrower, setBorrower] = useState('')
  const [due, setDue] = useState('')

  // Every open loan, so this control knows whether *this* disc is already out. `openOnly`
  // keeps it to the ones that matter, and the list is short by nature.
  const loansQuery = useQuery({ queryKey: ['loans', true], queryFn: () => fetchLoans(true) })
  const loans = loansQuery.data?.items ?? []
  const state = listState(loansQuery, loans.length === 0)
  const active = loans.find((loan) => loan.collectionItemId === collectionItemId)

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ['loans'] })
    void queryClient.invalidateQueries({ queryKey: ['activity'] })
  }

  const lend = useMutation({
    mutationFn: () => {
      const dueDate = due || null
      if (mode === 'borrow' && profile) return lendDisc({ collectionItemId, borrowerProfileId: profile.id, dueDate })
      return lendDisc({ collectionItemId, borrowerName: borrower.trim(), dueDate })
    },
    onSuccess: () => {
      setMode('idle')
      setBorrower('')
      setDue('')
      refresh()
    },
  })

  const giveBack = useMutation({
    mutationFn: () => returnLoan(active?.id ?? ''),
    onSuccess: refresh,
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

  if (active) {
    const yours = active.borrowerProfileId !== null && active.borrowerProfileId === profile?.id
    return (
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">
          {yours ? (
            <span className="text-foreground">With you</span>
          ) : (
            <>
              With <span className="text-foreground">{active.borrowerName}</span>
            </>
          )}{' '}
          ·{' '}
          <span className={active.isOverdue ? 'font-medium text-destructive' : ''}>
            {loanDueLabel(active)}
          </span>
        </p>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={giveBack.isPending}
          onClick={() => giveBack.mutate()}
        >
          {giveBack.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Undo2 className="h-3.5 w-3.5" />
          )}
          Returned
        </Button>
        {giveBack.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {queryErrorMessage(giveBack.error, 'Could not mark this disc as returned.')}
          </p>
        ) : null}
      </div>
    )
  }

  if (mode === 'idle') {
    return (
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
      </div>
    )
  }

  const borrowing = mode === 'borrow'
  return (
    <form
      className="space-y-3"
      aria-busy={lend.isPending}
      aria-label={borrowing ? 'Borrow this disc' : 'Lend this disc'}
      onSubmit={(event) => {
        event.preventDefault()
        if (borrowing || borrower.trim()) lend.mutate()
      }}
    >
      {borrowing ? (
        <p className="text-sm text-muted-foreground">You are taking this disc home.</p>
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
          {borrowing ? 'I’m borrowing it' : 'Lend it'}
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
