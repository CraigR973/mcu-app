import { describe, expect, it } from 'vitest'

import { personPath } from './people'

describe('personPath (AE9, #355)', () => {
  it('opens another person’s page, and You for the reader', () => {
    expect(personPath('p-mark', 'p-craig')).toBe('/people/p-mark')
    expect(personPath('p-craig', 'p-craig')).toBe('/you')
    expect(personPath('p-mark', undefined)).toBe('/people/p-mark')
  })
})
