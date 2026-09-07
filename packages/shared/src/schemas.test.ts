import { describe, expect, it } from 'vitest'

import { healthResponseSchema, profileResponseSchema, tokenPairSchema } from './schemas'

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

describe('tokenPairSchema', () => {
  it('parses a token pair', () => {
    const pair = {
      accessToken: 'a.b.c',
      refreshToken: 'd.e.f',
      tokenType: 'bearer' as const,
      expiresIn: 86400,
    }
    expect(tokenPairSchema.parse(pair)).toEqual(pair)
  })

  it('rejects wire-shape drift', () => {
    expect(() =>
      tokenPairSchema.parse({ accessToken: 'a', refreshToken: 'b', tokenType: 'Bearer', expiresIn: 1 }),
    ).toThrow()
    expect(() =>
      tokenPairSchema.parse({ accessToken: '', refreshToken: 'b', tokenType: 'bearer', expiresIn: 1 }),
    ).toThrow()
  })
})

describe('profileResponseSchema', () => {
  it('parses a profile', () => {
    const profile = {
      id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
      displayName: 'Craig',
      role: 'admin' as const,
      hasPin: true,
    }
    expect(profileResponseSchema.parse(profile)).toEqual(profile)
  })

  it('rejects an unknown role', () => {
    expect(() =>
      profileResponseSchema.parse({
        id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
        displayName: 'Craig',
        role: 'superadmin',
        hasPin: true,
      }),
    ).toThrow()
  })

  it('requires hasPin — a profile with no credential must be distinguishable', () => {
    expect(() =>
      profileResponseSchema.parse({
        id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
        displayName: 'Craig',
        role: 'admin',
      }),
    ).toThrow()
  })
})
