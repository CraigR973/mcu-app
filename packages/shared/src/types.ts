import { z } from 'zod'

import { healthResponseSchema } from './schemas'

export type HealthResponse = z.infer<typeof healthResponseSchema>
