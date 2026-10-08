import { apiClient } from './client'
import type { Region } from '../types'

// 获取所有区域
export async function listRegions(): Promise<Region[]> {
  const { data } = await apiClient.get('/api/regions')
  return data
}

// 创建区域 (仅总管理员)
export async function createRegion(params: {
  name: string
  description?: string
}): Promise<Region> {
  const { data } = await apiClient.post('/api/regions', params)
  return data
}

// 更新区域 (仅总管理员)
export async function updateRegion(regionId: number, params: Partial<Region>): Promise<Region> {
  const { data } = await apiClient.put(`/api/regions/${regionId}`, params)
  return data
}

// 删除区域 (仅总管理员)
export async function deleteRegion(regionId: number): Promise<void> {
  await apiClient.delete(`/api/regions/${regionId}`)
}
