import { useId, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { HandHeart, Loader2, Undo2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { fetchLoans, lendDisc, loanDueLabel, returnLoan } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

interface Props {
  collectionItemId: string
}

/**
 * Lend this specific disc, or mark it returned — §12.5's "mark as lent / returned".
 *
 * **On the copy, not on the film.** A loan is about one physical object: owning *Heat* on
 * 4K and on DVD means two discs, and only one of them left the house. `loans` points at
 * `collection_item_id` for the same reason.
 */
export function LendButton({ collectionItemId }: Props) {
  const queryClient = useQueryClient()
  const borrowerId = useId()
  const dueId = useId()
  const [open, setOpen] = useState(false)
  const [borrower, setBorrower] = useState('')
  const [due, setDue] = useState('')

  // Every loan, so this control knows whether *this* disc is already out. `openOnly`
  // keeps it to the ones that matter and the list is short by nature.
  const loansQuery = useQuery({ queryKey: ['loans', true], queryFn: () => fetchLoans(true) })
  const loans = loansQuery.data?.items ?? []
  const state = listState(loansQuery, loans.length === 0)
  const active = loans.find(
    (loan) => loan.collectionItemId === collectionItemId,
  )

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ['loans'] })
    void queryClient.invalidateQueries({ queryKey: ['activity'] })
  }

  const lend = useMutation({
    mutationFn: () =>
      lendDisc({
        collectionItemId,
        borrowerName: borrower.trim(),
        dueDate: due || null,
      }),
    onSuccess: () => {
      setOpen(false)
      setBorrower('')
      setDue('')
      refresh()
    },
  })

  const giveBack = useMutation({
    mutationFn: () => returnLoan(active?.id ?? ''),
    onSuccess: refresh,
  })

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
    return (
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">
          With <span className="text-foreground">{active.borrowerName}</span> ·{' '}
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
          Mark returned
        </Button>
        {giveBack.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {queryErrorMessage(giveBack.error, 'Could not mark this disc as returned.')}
          </p>
        ) : null}
      </div>
    )
  }

  if (!open) {
    return (
      <Button
        type="button"
        size="sm"
        variant="ghost"
        onClick={() => {
          lend.reset()
          setOpen(true)
        }}
      >
        <HandHeart className="h-3.5 w-3.5" />
        Lend
      </Button>
    )
  }

  return (
    <form
      className="space-y-3"
      aria-busy={lend.isPending}
      onSubmit={(event) => {
        event.preventDefault()
        if (borrower.trim()) lend.mutate()
      }}
    >
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
          disabled={lend.isPending || borrower.trim().length === 0}
        >
          {lend.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
          Lend it
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          disabled={lend.isPending}
          onClick={() => setOpen(false)}
        >
          Cancel
        </Button>
      </div>
    </form>
  )
}
