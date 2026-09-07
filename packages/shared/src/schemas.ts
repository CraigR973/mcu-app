import { z } from 'zod'

// Shared response schemas land with their endpoints. Health is the only Batch 1
// application endpoint; domain schemas arrive with the read surface in Batch 5.
export const healthResponseSchema = z.object({
  status: z.literal('ok'),
  commitSha: z.string().min(1),
})

// ---------------------------------------------------------------------------
// Auth (Batch 3)
//
// Schemas ship with their endpoint. A schema added later never gets added
// (`DECISIONS.md` #6), so every auth response the web app reads is parsed here.
// ---------------------------------------------------------------------------

export const userRoleSchema = z.enum(['admin', 'viewer'])

export const tokenPairSchema = z.object({
  accessToken: z.string().min(1),
  refreshToken: z.string().min(1),
  tokenType: z.literal('bearer'),
  expiresIn: z.number().int().positive(),
})

export const profileResponseSchema = z.object({
  id: z.string().uuid(),
  displayName: z.string().min(1),
  role: userRoleSchema,
  // False for a profile seeded with `pin_hash = NULL` — no credential yet, which is
  // not the same as a blank one.
  hasPin: z.boolean(),
})

export type UserRole = z.infer<typeof userRoleSchema>
export type TokenPair = z.infer<typeof tokenPairSchema>
export type ProfileResponse = z.infer<typeof profileResponseSchema>
