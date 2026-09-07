import { describe, expect, it } from 'vitest'

import { healthResponseSchema } from './schemas'

describe('healthResponseSchema', () => {
  it('parses the health response', () => {
    expect(healthResponseSchema.parse({ status: 'ok', commitSha: 'abc1234' })).toEqual({
      status: 'ok',
      commitSha: 'abc1234',
    })
  })

  it('rejects wire-shape drift', () => {
    expect(() => healthResponseSchema.parse({ status: 'healthy', commitSha: 'abc1234' })).toThrow()
    expect(() => healthResponseSchema.parse({ status: 'ok' })).toThrow()
  })
})
