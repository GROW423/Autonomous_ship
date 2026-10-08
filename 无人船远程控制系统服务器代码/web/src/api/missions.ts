import { apiClient } from './client'
import type { Mission, Waypoint } from '../types'

// 获取船的任务列表
export async function listMissions(boatId: number): Promise<Mission[]> {
  const { data } = await apiClient.get(`/api/boats/${boatId}/missions`)
  return data
}

// 创建任务
export async function createMission(boatId: number, params: {
  name: string
  description?: string
  waypoints: Waypoint[]
}): Promise<Mission> {
  const { data } = await apiClient.post(`/api/boats/${boatId}/missions`, params)
  return data
}

// 获取任务详情
export async function getMission(boatId: number, missionId: number): Promise<Mission> {
  const { data } = await apiClient.get(`/api/boats/${boatId}/missions/${missionId}`)
  return data
}

// 更新任务
export async function updateMission(boatId: number, missionId: number, params: {
  name?: string
  description?: string
  waypoints?: Waypoint[]
}): Promise<Mission> {
  const { data } = await apiClient.put(`/api/boats/${boatId}/missions/${missionId}`, params)
  return data
}

// 删除任务
export async function deleteMission(boatId: number, missionId: number): Promise<void> {
  await apiClient.delete(`/api/boats/${boatId}/missions/${missionId}`)
}

// 上传任务到船
export async function uploadMission(boatId: number, missionId: number): Promise<{ success: boolean; message: string }> {
  const { data } = await apiClient.post(`/api/boats/${boatId}/missions/${missionId}/upload`)
  return data
}

// 执行任务
export async function executeMission(boatId: number, missionId: number): Promise<{ success: boolean; message: string }> {
  const { data } = await apiClient.post(`/api/boats/${boatId}/missions/${missionId}/execute`)
  return data
}
