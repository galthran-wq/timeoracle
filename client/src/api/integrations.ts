import { get, post, del } from './client'
import type {
  IntegrationListResponse,
  TelegramConnectResponse,
  TelegramDisconnectResponse,
} from '@/types/integrations'

export function getIntegrations(): Promise<IntegrationListResponse> {
  return get<IntegrationListResponse>('/api/integrations/')
}

export function connectTelegram(): Promise<TelegramConnectResponse> {
  return post<TelegramConnectResponse>('/api/integrations/telegram/connect')
}

export function disconnectTelegram(): Promise<TelegramDisconnectResponse> {
  return del<TelegramDisconnectResponse>('/api/integrations/telegram/disconnect')
}
