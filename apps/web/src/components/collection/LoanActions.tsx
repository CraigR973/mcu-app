import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { Loan } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { fetchFacets, loanState, returnLoan, transitionLoan } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

/** The physical actions are shared by Loans and each film's copy card. */
export function LoanActions({ loan }: { loan: Loan }) {
  const client = useQueryClient()
  const state = loanState(loan)
  const [puttingBack, setPuttingBack] = useState(false)
  const [changing, setChanging] = useState(false)
  const [section, setSection] = useState(loan.section ?? '')
  const [shelf, setShelf] = useState(loan.shelf ?? '')
  const facets = useQuery({ queryKey: ['facets'], queryFn: fetchFacets, enabled: puttingBack && changing })
  const choices = facets.data?.allSections ?? facets.data?.sections.map((entry) => entry.section) ?? []
  const sections = [...new Set([section, ...choices].filter(Boolean))]
  const save = useMutation({
    mutationFn: () => state === 'out' ? returnLoan(loan.id) : transitionLoan(loan.id,
      state === 'asked_for' ? { state: 'out' } : changing ? { state: 'shelved', section, shelf: shelf || null } : { state: 'shelved' }),
    onSuccess: () => {
      setPuttingBack(false)
      for (const key of ['loans', 'activity', 'movie-copies', 'movie', 'movies', 'facets', 'item-history']) {
        void client.invalidateQueries({ queryKey: [key] })
      }
    },
  })
  if (loan.isCurrent === false || state === 'shelved') return null
  return (
    <div className="space-y-2" aria-busy={save.isPending}>
      {state === 'back' && puttingBack ? (
        <form aria-label={`Put back ${loan.movieTitle}`} className="space-y-3" onSubmit={(event) => { event.preventDefault(); save.mutate() }}>
          <p className="text-sm">Home position: {loan.locationLabel}</p>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={changing} onChange={(event) => setChanging(event.target.checked)} disabled={save.isPending} />
            Change shelf
          </label>
          {changing ? <>
            <label className="block text-sm">Section
              <select className="mt-1 min-h-11 w-full rounded-md border border-input bg-background px-3" value={section} required disabled={save.isPending} onChange={(event) => { setSection(event.target.value); setShelf('') }}>
                <option value="">Choose a section</option>
                {sections.map((name) => <option key={name}>{name}</option>)}
              </select>
            </label>
            <label className="block text-sm">Shelf or side (optional)
              <Input value={shelf} maxLength={50} disabled={save.isPending} placeholder={section === 'Lounge' ? 'Left or Right' : 'e.g. 2nd'} onChange={(event) => setShelf(event.target.value)} />
            </label>
            {facets.isError ? <p role="alert" className="text-sm text-destructive">Could not load places. Try again.</p> : null}
          </> : null}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" size="sm" disabled={save.isPending || (changing && !section)}>Confirm shelved</Button>
            <Button type="button" size="sm" variant="ghost" disabled={save.isPending} onClick={() => setPuttingBack(false)}>Cancel</Button>
          </div>
        </form>
      ) : <Button type="button" size="sm" variant="outline" disabled={save.isPending} onClick={() => { if (state === 'back') setPuttingBack(true); else save.mutate() }}>
        {state === 'asked_for' ? 'Taken' : state === 'out' ? 'Returned' : 'Put back'}
      </Button>}
      {save.isError ? <p role="alert" className="text-sm text-destructive">{queryErrorMessage(save.error, 'Could not update this loan. Reload its current state and try again.')}</p> : null}
    </div>
  )
}
