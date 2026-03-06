import type { CategoryConfig } from '@/constants/categories'

export interface SessionConfig {
  merge_gap_seconds: number
  min_session_seconds: number
  noise_threshold_seconds: number
  day_start_hour: number
  timezone: string
  categories?: Record<string, CategoryConfig>
  classification_rules?: string[]
  language?: string
}

export type SessionConfigUpdate = Partial<SessionConfig>
