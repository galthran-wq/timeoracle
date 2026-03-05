import { get } from './client'
import type { ProductivityCurveResponse, AggregatedCurveResponse } from '@/types/productivityCurve'

export function getProductivityCurve(date: string): Promise<ProductivityCurveResponse> {
  return get<ProductivityCurveResponse>(`/api/productivity-curve/${date}`)
}

export function getProductivityCurveRange(
  start: string,
  end: string,
): Promise<ProductivityCurveResponse[]> {
  return get<ProductivityCurveResponse[]>('/api/productivity-curve', { start, end })
}

export function getAggregatedCurve(
  start: string,
  end: string,
  bucketMinutes: number,
): Promise<AggregatedCurveResponse> {
  return get<AggregatedCurveResponse>('/api/productivity-curve/aggregate', {
    start,
    end,
    bucket_minutes: bucketMinutes,
  })
}
