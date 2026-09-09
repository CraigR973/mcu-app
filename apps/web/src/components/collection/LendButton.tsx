import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { HandHeart, Loader2, Undo2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { fetchLoans, lendDisc, loanDueLabel, returnLoan } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

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
  const [open, setOpen] = useState(false)
  const [borrower, setBorrower] = useState('')
  const [due, setDue] = useState('')

  // Every loan, so this control knows whether *this* disc is already out. `openOnly`
  // keeps it to the ones that matter and the list is short by nature.
  const loansQuery = useQuery({ queryKey: ['loans', true], queryFn: () => fetchLoans(true) })
  const active = loansQuery.data?.items.find(
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

  if (active) {
    return (
      <div className="space-y-1">
        <p className="text-[11px] text-muted-foreground">
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
          Returned
        </Button>
      </div>
    )
  }

  if (!open) {
    return (
      <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(true)}>
        <HandHeart className="h-3.5 w-3.5" />
        Lend
      </Button>
    )
  }

  return (
    <div className="space-y-2">
      <Input
        value={borrower}
        onChange={(event) => setBorrower(event.target.value)}
        placeholder="Who has it?"
        aria-label="Borrower name"
        className="h-8 text-xs"
      />
      <Input
        type="date"
        value={due}
        onChange={(event) => setDue(event.target.value)}
        aria-label="Due back"
        className="h-8 text-xs"
      />
      {lend.isError ? (
        <p className="text-xs text-destructive">
          {queryErrorMessage(lend.error, 'Could not record the loan.')}
        </p>
      ) : null}
      <div className="flex gap-1">
        <Button
          type="button"
          size="sm"
          disabled={lend.isPending || borrower.trim().length === 0}
          onClick={() => lend.mutate()}
        >
          {lend.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
          Lend it
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
