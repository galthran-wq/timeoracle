import { get, post } from './client'
import type { DaySummary, DaySummaryTrendsResponse } from '@/types/daySummary'

export function getDaySummary(date: string): Promise<DaySummary> {
  return get<DaySummary>(`/api/day-summaries/${date}`)
}

export function getDaySummaryTrends(start: string, end: string): Promise<DaySummaryTrendsResponse> {
  return get<DaySummaryTrendsResponse>('/api/day-summaries', { start, end })
}

export function generateDaySummary(date: string): Promise<DaySummary> {
  return post<DaySummary>(`/api/day-summaries/${date}/generate`)
}
