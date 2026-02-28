import { get } from './client'
import type {
  ActivityEventListResponse,
  ActivityEventType,
  ActivitySessionListResponse,
  ActivityStatus,
} from '@/types/activity'

export function listEvents(params: {
  start: string
  end: string
  limit?: number
  offset?: number
  event_type?: ActivityEventType
  app_name?: string
}): Promise<ActivityEventListResponse> {
  const query: Record<string, string> = {
    start: params.start,
    end: params.end,
  }
  if (params.limit !== undefined) query.limit = String(params.limit)
  if (params.offset !== undefined) query.offset = String(params.offset)
  if (params.event_type) query.event_type = params.event_type
  if (params.app_name) query.app_name = params.app_name
  return get<ActivityEventListResponse>('/api/activity/events', query)
}

export function getStatus(): Promise<ActivityStatus> {
  return get<ActivityStatus>('/api/activity/status')
}

export function listSessions(params: {
  date: string
  range?: 'day' | 'week'
  limit?: number
  offset?: number
}): Promise<ActivitySessionListResponse> {
  const query: Record<string, string> = {
    date: params.date,
  }
  if (params.range) query.range = params.range
  if (params.limit !== undefined) query.limit = String(params.limit)
  if (params.offset !== undefined) query.offset = String(params.offset)
  return get<ActivitySessionListResponse>('/api/activity/sessions', query)
}
