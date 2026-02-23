import { get, post, patch, del } from './client'
import type {
  TimelineEntry,
  TimelineEntryCreate,
  TimelineEntryUpdate,
  TimelineEntryListResponse,
} from '@/types/timeline'

export function listEntries(params: {
  date: string
  range?: 'day' | 'week'
  category?: string
  limit?: number
  offset?: number
}): Promise<TimelineEntryListResponse> {
  const query: Record<string, string> = { date: params.date }
  if (params.range) query.range = params.range
  if (params.category) query.category = params.category
  if (params.limit !== undefined) query.limit = String(params.limit)
  if (params.offset !== undefined) query.offset = String(params.offset)
  return get<TimelineEntryListResponse>('/api/timeline', query)
}

export function createEntry(data: TimelineEntryCreate): Promise<TimelineEntry> {
  return post<TimelineEntry>('/api/timeline', data)
}

export function updateEntry(id: string, data: TimelineEntryUpdate): Promise<TimelineEntry> {
  return patch<TimelineEntry>(`/api/timeline/${id}`, data)
}

export function deleteEntry(id: string): Promise<void> {
  return del(`/api/timeline/${id}`)
}
