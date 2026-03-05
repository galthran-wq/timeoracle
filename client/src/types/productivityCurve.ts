export interface ProductivityPoint {
  interval_start: string
  focus_score: number | null
  depth: string | null
  category: string | null
  color: string | null
  is_work: boolean
  productivity_score: number | null
}

export interface ProductivityCurveResponse {
  date: string
  points: ProductivityPoint[]
  day_score: number | null
  overall_score: number | null
  work_minutes: number
}

export interface AggregatedBucket {
  bucket_start: string
  avg_productivity_score: number | null
  avg_performance_score: number | null
  point_count: number
  work_point_count: number
  dominant_category: string | null
  dominant_color: string | null
}

export interface AggregatedCurveResponse {
  start: string
  end: string
  bucket_minutes: number
  buckets: AggregatedBucket[]
  overall_score: number | null
  performance_score: number | null
}
