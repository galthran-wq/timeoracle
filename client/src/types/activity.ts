export type ActivityEventType = 'active_window' | 'idle_start' | 'idle_end'

export interface ActivityEvent {
  id: string
  user_id: string
  client_event_id: string
  timestamp: string
  event_type: ActivityEventType
  app_name: string
  window_title: string
  url: string | null
  metadata: Record<string, unknown> | null
  created_at: string
}

export interface ActivityEventListResponse {
  events: ActivityEvent[]
  total_count: number
  limit: number
  offset: number
}

export interface ActivityStatus {
  last_event_at: string | null
  events_today: number
}
