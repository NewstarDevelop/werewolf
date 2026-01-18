/**
 * Zod validation schemas for environment variable management
 */

import { z } from 'zod';

export const envVarSchema = z.object({
  name: z
    .string()
    .min(1, 'Variable name is required')
    .regex(
      /^[A-Z_][A-Z0-9_]*$/,
      'Must be uppercase with underscores (e.g., API_KEY, DATABASE_URL)'
    ),
  value: z.string().default(''),
});

export type EnvVarFormData = z.infer<typeof envVarSchema>;
