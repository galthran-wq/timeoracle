export interface CategoryBreakdownItem {
  category: string
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
  longest_focus_minutes: number
  context_switches: number
  session_count: number
  top_app: string | null
  top_category: string | null
  category_breakdown: CategoryBreakdownItem[] | null
  app_breakdown: AppBreakdownItem[] | null
  deep_work_minutes: number
  shallow_work_minutes: number
  reactive_minutes: number
  avg_focus_score: number | null
  fragmentation_index: number | null
  switches_per_hour: number | null
  focus_sessions_25min: number
  focus_sessions_90min: number
  productivity_score: number | null
  overall_productivity_score: number | null
  work_minutes: number
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
