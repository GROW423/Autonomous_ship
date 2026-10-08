import { apiClient } from './client'
import type { TelemetryRecord } from '../types'

// 获取遥测历史
export async function getTelemetryHistory(
  boatId: number,
  params?: {
    start?: string
    end?: string
    limit?: number
  },
): Promise<TelemetryRecord[]> {
  const { data } = await apiClient.get(`/api/boats/${boatId}/telemetry/history`, { params })
  return data
}

// 获取最近一条遥测
export async function getLatestTelemetry(boatId: number): Promise<TelemetryRecord> {
  const { data } = await apiClient.get(`/api/boats/${boatId}/telemetry/latest`)
  return data
}

// 获取统计摘要
export async function getTelemetrySummary(
  boatId: number,
  hours: number = 24,
): Promise<{
  period_hours: number
  records: number
  total_distance_km: number
  avg_speed: number
  max_speed: number
  active_minutes: number
}> {
  const { data } = await apiClient.get(`/api/boats/${boatId}/telemetry/summary`, {
    params: { hours },
  })
  return data
}
