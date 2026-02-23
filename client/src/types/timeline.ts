export interface TimelineEntry {
  id: string
  user_id: string
  date: string
  start_time: string
  end_time: string
  label: string
  description: string | null
  category: string | null
  color: string | null
  source: string
  source_summary: string | null
  confidence: number | null
  edited_by_user: boolean
  created_at: string
  updated_at: string
}

export interface TimelineEntryCreate {
  date: string
  start_time: string
  end_time: string
  label: string
  description?: string | null
  category?: string | null
  color?: string | null
}

export interface TimelineEntryUpdate {
  date?: string
  start_time?: string
  end_time?: string
  label?: string
  description?: string | null
  category?: string | null
  color?: string | null
}

export interface TimelineEntryListResponse {
  entries: TimelineEntry[]
  total_count: number
  limit: number
  offset: number
}
