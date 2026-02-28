export interface SessionConfig {
  merge_gap_seconds: number
  min_session_seconds: number
  noise_threshold_seconds: number
}

export type SessionConfigUpdate = Partial<SessionConfig>
