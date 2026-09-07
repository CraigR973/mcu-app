import { describe, expect, it } from 'vitest'

import { healthResponseSchema } from './schemas'

describe('healthResponseSchema', () => {
  it('parses the health response', () => {
    expect(healthResponseSchema.parse({ status: 'ok' })).toEqual({ status: 'ok' })
  })

  it('rejects wire-shape drift', () => {
    expect(() => healthResponseSchema.parse({ status: 'healthy' })).toThrow()
  })
})
