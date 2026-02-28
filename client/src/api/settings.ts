import { get, patch } from './client'
import type { SessionConfig, SessionConfigUpdate } from '@/types/settings'

export function getSessionConfig(): Promise<SessionConfig> {
  return get<SessionConfig>('/api/users/me/session-config')
}

export function updateSessionConfig(data: SessionConfigUpdate): Promise<SessionConfig> {
  return patch<SessionConfig>('/api/users/me/session-config', data)
}
