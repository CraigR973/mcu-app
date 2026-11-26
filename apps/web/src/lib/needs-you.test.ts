import { describe, expect, it } from 'vitest'

import { needsYouRows } from './needs-you'

describe('needsYouRows: closed questions (AH2, #401)', () => {
  const base = { title: 'Check Shetland Series 5', question: 'Should this copy use the series?', assignedTo: 'mark', assigneeName: 'Mark' }

  it('leaves a closed question off, as it does a resolved one', () => {
    const rows = needsYouRows(
      {
        reviews: [
          { ...base, id: 'closed', status: 'closed' },
          { ...base, id: 'resolved', status: 'resolved' },
          { ...base, id: 'answered', status: 'answered' },
        ],
      },
      { id: 'craig', role: 'admin' },
    )

    expect(rows.map((row) => row.key)).toEqual(['review:answered'])
  })
})
