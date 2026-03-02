export interface IntegrationStatus {
  provider: string
  is_connected: boolean
  is_enabled: boolean
  external_user_id: string | null
  display_name: string | null
  connected_at: string | null
}

export interface IntegrationListResponse {
  integrations: IntegrationStatus[]
}

export interface TelegramConnectResponse {
  deep_link: string
  token: string
  expires_in_seconds: number
}

export interface TelegramDisconnectResponse {
  success: boolean
  message: string
}
