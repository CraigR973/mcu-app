import { z } from 'zod'

// Shared response schemas land with their endpoints. Health is the only Batch 1
// application endpoint; domain schemas arrive with the read surface in Batch 5.
export const healthResponseSchema = z.object({
  status: z.literal('ok'),
})
