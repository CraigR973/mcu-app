import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import MaybeOwnedNotice from './MaybeOwnedNotice'

describe('MaybeOwnedNotice — Batch X10', () => {
  it('names the unidentified owned film and opens it', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <MaybeOwnedNotice film={{ movieId: '3f2504e0-4f89-11d3-9a0c-0305e82c3302', title: 'Invasion of the Body Snatchers' }} />
      </MemoryRouter>,
    )

    expect(html).toContain('You may already own this')
    expect(html).toContain('Invasion of the Body Snatchers')
    expect(html).toContain('href="/movies/3f2504e0-4f89-11d3-9a0c-0305e82c3302"')
  })
})
