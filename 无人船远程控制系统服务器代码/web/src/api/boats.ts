import { apiClient } from './client'
import type { Boat, BoatStatus } from '../types'

// 获取我的船列表 (支持搜索和区域筛选)
export async function listBoats(params?: {
  search?: string
  region_id?: number
}): Promise<Boat[]> {
  const { data } = await apiClient.get('/api/boats', { params })
  return data
}

// 添加船
export async function createBoat(params: {
  name: string
  mavlink_sys_id?: number
  iccid: string
  description?: string
  home_lat?: number
  home_lon?: number
}): Promise<Boat> {
  const { data } = await apiClient.post('/api/boats', params)
  return data
}

// 获取船详情
export async function getBoat(boatId: number): Promise<Boat> {
  const { data } = await apiClient.get(`/api/boats/${boatId}`)
  return data
}

// 更新船
export async function updateBoat(boatId: number, params: Partial<Boat>): Promise<Boat> {
  const { data } = await apiClient.put(`/api/boats/${boatId}`, params)
  return data
}

// 删除船
export async function deleteBoat(boatId: number): Promise<void> {
  await apiClient.delete(`/api/boats/${boatId}`)
}

// 获取船实时状态
export async function getBoatStatus(boatId: number): Promise<BoatStatus> {
  const { data } = await apiClient.get(`/api/boats/${boatId}/status`)
  return data
}
