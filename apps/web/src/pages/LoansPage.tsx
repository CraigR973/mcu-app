import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { HandHeart, Loader2, Undo2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Loan } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/context/auth'
import { fetchLoans, formatLabel, loanDueLabel, posterUrl, returnLoan } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

function Row({ loan }: { loan: Loan }) {
  const { profile } = useAuth()
  const queryClient = useQueryClient()

  const giveBack = useMutation({
    mutationFn: () => returnLoan(loan.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['loans'] })
      void queryClient.invalidateQueries({ queryKey: ['activity'] })
    },
  })

  return (
    <li
      className={cn(
        'flex items-center gap-3 rounded-lg border bg-card p-3',
        loan.isOverdue ? 'border-destructive/50' : 'border-border',
      )}
    >
      <img
        src={posterUrl(loan.posterPath, 'w92')}
        alt=""
        loading="lazy"
        className="h-16 w-11 shrink-0 rounded object-cover"
      />
      <div className="min-w-0 flex-1">
        <Link
          to={`/movies/${loan.movieId}`}
          className="font-medium text-foreground hover:underline"
        >
          {loan.movieTitle}
        </Link>
        <p className="text-xs text-muted-foreground">
          {loan.formats.map((f) => formatLabel(f)).join(' + ')} · with{' '}
          <span className="text-foreground">{loan.borrowerName}</span> since {loan.lentDate}
        </p>
        <p
          className={cn(
            'text-[11px]',
            loan.isOverdue ? 'font-medium text-destructive' : 'text-muted-foreground',
          )}
        >
          {loanDueLabel(loan)}
        </p>
      </div>
      {profile?.role === 'admin' && loan.returnedDate === null ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={giveBack.isPending}
          onClick={() => giveBack.mutate()}
        >
          {giveBack.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Undo2 className="h-4 w-4" />
          )}
          Returned
        </Button>
      ) : null}
    </li>
  )
}

/**
 * §12.5's loans page.
 *
 * **There are no reminder notifications, and that is the honest state.** §12.5 lists
 * "reminder notifications for overdue" and its acceptance says "overdue triggers a push".
 * Push does not exist — no VAPID key, no subscription store, no endpoint — and building
 * it is Batch 11, which stops for an owner credential checkpoint. An overdue loan is shown
 * here in red and counted at the top; a toggle promising a notification that never arrives
 * is the defect Batch 9 refused to ship twice (`DECISIONS.md` #50).
 */
export default function LoansPage() {
  const [openOnly, setOpenOnly] = useState(true)

  const loansQuery = useQuery({
    queryKey: ['loans', openOnly],
    queryFn: () => fetchLoans(openOnly),
  })
  const loans = loansQuery.data?.items ?? []
  const state = listState(loansQuery, loans.length === 0)

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Loans</h1>
        <p className="text-sm text-muted-foreground">
          Discs that have left the house.
          {loansQuery.data && loansQuery.data.overdueCount > 0 ? (
            <span className="ml-1 font-medium text-destructive">
              {loansQuery.data.overdueCount} overdue.
            </span>
          ) : null}
        </p>
      </div>

      <div className="flex gap-1">
        {[
          { value: true, label: 'Out now' },
          { value: false, label: 'All' },
        ].map((option) => (
          <button
            key={String(option.value)}
            type="button"
            onClick={() => setOpenOnly(option.value)}
            className={cn(
              'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
              openOnly === option.value
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:bg-muted',
            )}
          >
            {option.label}
          </button>
        ))}
      </div>

      {state === 'loading' ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : state === 'offline' ? (
        <p className="text-sm text-muted-foreground">
          Waiting for the network — the loans could not be loaded yet.
        </p>
      ) : state === 'error' ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(loansQuery.error, 'Could not load the loans.')}
        </p>
      ) : state === 'empty' ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <HandHeart className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">
            {openOnly ? 'Nothing is out on loan.' : 'Nothing has been lent yet.'}
          </p>
          <p className="max-w-sm text-xs text-muted-foreground">
            Lend a disc from its own page — open a film, then the copy you are handing over.
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {loans.map((loan) => (
            <Row key={loan.id} loan={loan} />
          ))}
        </ul>
      )}
    </div>
  )
}
