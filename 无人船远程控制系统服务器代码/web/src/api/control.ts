import { apiClient } from './client'
import type { ControlCommand, CommandResponse } from '../types'

// 发送通用控制指令
export async function sendCommand(boatId: number, command: ControlCommand): Promise<CommandResponse> {
  const { data } = await apiClient.post(`/api/boats/${boatId}/control`, command)
  return data
}

// 一键返航
export async function returnToLaunch(boatId: number): Promise<CommandResponse> {
  const { data } = await apiClient.post(`/api/boats/${boatId}/control/rtl`)
  return data
}

// 开始AUTO模式
export async function startAuto(boatId: number): Promise<CommandResponse> {
  const { data } = await apiClient.post(`/api/boats/${boatId}/control/start_auto`)
  return data
}

// 紧急停车
export async function emergencyStop(boatId: number): Promise<CommandResponse> {
  const { data } = await apiClient.post(`/api/boats/${boatId}/control/stop`)
  return data
}

// 开启投料
export async function feedOn(boatId: number): Promise<CommandResponse> {
  const { data } = await apiClient.post(`/api/boats/${boatId}/control/feed/on`)
  return data
}

// 关闭投料
export async function feedOff(boatId: number): Promise<CommandResponse> {
  const { data } = await apiClient.post(`/api/boats/${boatId}/control/feed/off`)
  return data
}
