export interface CategoryBreakdownItem {
  category: string
  type: string
  minutes: number
}

export interface AppBreakdownItem {
  app: string
  minutes: number
}

export interface DaySummary {
  id: string
  user_id: string
  date: string
  total_active_minutes: number
  productive_minutes: number
  neutral_minutes: number
  distraction_minutes: number
  uncategorized_minutes: number
  focus_score: number | null
  distraction_score: number | null
  longest_focus_minutes: number
  context_switches: number
  session_count: number
  top_app: string | null
  top_category: string | null
  category_breakdown: CategoryBreakdownItem[] | null
  app_breakdown: AppBreakdownItem[] | null
  narrative: string | null
  is_partial: boolean
  created_at: string
  updated_at: string
}

export interface DaySummaryTrendsResponse {
  summaries: DaySummary[]
  start: string
  end: string
}
