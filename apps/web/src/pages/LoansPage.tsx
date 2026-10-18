import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRightLeft, HandHeart, Loader2, Undo2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Loan } from '@mcu/shared'

import { LoanStarter } from '@/components/collection/LoanStarter'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import { useAuth } from '@/context/auth'
import { fetchLoans, formatLabel, loanDueLabel, posterUrl, returnLoan } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn, formatShortDate } from '@/lib/utils'

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
        'archive-panel grid grid-cols-[auto_minmax(0,1fr)] items-center gap-3 p-3 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:p-4',
        loan.isOverdue ? 'border-destructive/50' : 'border-border',
      )}
    >
      <img
        src={posterUrl(loan.posterPath, 'w92')}
        alt=""
        loading="lazy"
        className="h-[4.5rem] w-12 shrink-0 rounded-sm border border-border object-cover"
      />
      <div className="min-w-0 flex-1">
        <Link
          to={`/movies/${loan.movieId}`}
          className="line-clamp-2 font-semibold text-foreground hover:text-primary"
        >
          {loan.movieTitle}
        </Link>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">
          <span className="font-medium text-foreground">{loan.formats.map((f) => formatLabel(f)).join(' + ')}</span>
          {' · '}with{' '}
          <span className="text-foreground">
            {loan.borrowerProfileId !== null && loan.borrowerProfileId === profile?.id ? 'you' : loan.borrowerName}
          </span>{' '}
          since {formatShortDate(loan.lentDate)}
        </p>
        <p
          className={cn(
            'mt-0.5 text-xs',
            loan.isOverdue ? 'font-medium text-destructive' : 'text-muted-foreground',
          )}
        >
          {loanDueLabel(loan)}
        </p>
      </div>
      {/* Either person, since Batch W3 (#249). "Mark returned" read as a sentence about
          Mark, who is a person here, so it is "Returned". */}
      {loan.returnedDate === null ? (
        <Button
          type="button"
          variant="outline"
          className="col-span-2 w-full sm:col-span-1 sm:w-auto"
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
      {giveBack.isError ? (
        <p role="alert" className="col-span-2 text-sm text-destructive sm:col-start-2 sm:col-end-4">
          {queryErrorMessage(giveBack.error, 'Could not mark this disc as returned.')}
        </p>
      ) : null}
    </li>
  )
}

/**
 * §12.5's loans page.
 *
 * **Overdue loans now do trigger a push.** §12.5's second acceptance clause —
 * "overdue triggers a push" — went unmet from Batch 15 until Batch 11 built the
 * infrastructure it needed. `notify_overdue_loans` in `services/reminders.py` writes the
 * notification and `loans.reminder_sent` stops it repeating. The reminder is sent to
 * admins, since lending a disc is an admin action and getting it back is an admin problem.
 *
 * This page is still where an overdue loan is *shown* — red, and counted at the top —
 * because a notification arrives once and a page answers whenever you look.
 */
export default function LoansPage() {
  const [openOnly, setOpenOnly] = useState(true)
  const [starting, setStarting] = useState(false)

  const loansQuery = useQuery({
    queryKey: ['loans', openOnly],
    queryFn: () => fetchLoans(openOnly),
  })
  const loans = loansQuery.data?.items ?? []
  const state = listState(loansQuery, loans.length === 0)

  return (
    <div className="page-shell-narrow space-y-7">
      <PageHeader
        eyebrow="Circulation desk"
        title="Loans"
        description="Keep track of every disc that has left the house and who has it."
        meta={loansQuery.data && loansQuery.data.overdueCount > 0 ? (
          <span className="inline-flex items-center gap-1.5 font-semibold text-destructive">
            <span className="h-1.5 w-1.5 rounded-full bg-destructive" aria-hidden />
            {loansQuery.data.overdueCount} overdue
          </span>
        ) : undefined}
        actions={(
          <Button type="button" onClick={() => setStarting(true)} aria-expanded={starting}>
            <ArrowRightLeft className="h-4 w-4" aria-hidden />
            Lend or borrow
          </Button>
        )}
      />

      {/* Batch W3 (#249): start a loan here, by scan or by search, as well as from a film. */}
      {starting ? <LoanStarter onClose={() => setStarting(false)} /> : null}

      <div className="inline-flex rounded-lg border border-border bg-card p-1" aria-label="Loan history view">
        {[
          { value: true, label: 'Out now' },
          { value: false, label: 'All' },
        ].map((option) => (
          <button
            key={String(option.value)}
            type="button"
            onClick={() => setOpenOnly(option.value)}
            aria-pressed={openOnly === option.value}
            className={cn(
              'touch-target min-h-10 rounded-md px-4 py-2 text-sm font-semibold transition-colors',
              openOnly === option.value
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground',
            )}
          >
            {option.label}
          </button>
        ))}
      </div>

      {state === 'loading' ? (
        <StatePanel tone="loading" title="Checking the loan register" />
      ) : state === 'offline' ? (
        <StatePanel tone="offline" title="The loan register is not cached here" description="Reconnect to see which discs are away from home." />
      ) : state === 'error' ? (
        <StatePanel
          tone="error"
          title="The loan register is unavailable"
          description={queryErrorMessage(loansQuery.error, 'Could not load the loans.')}
        />
      ) : state === 'empty' ? (
        <StatePanel
          tone="empty"
          icon={HandHeart}
          title={openOnly ? 'Every disc is home' : 'No loans have been recorded'}
          description="Use Lend or borrow above, or a film's page, then choose the exact disc."
        />
      ) : (
        <ul className="space-y-3">
          {loans.map((loan) => (
            <Row key={loan.id} loan={loan} />
          ))}
        </ul>
      )}
    </div>
  )
}
