import { apiClient } from './client'
import type { User } from '../types'

// 获取所有用户 (仅总管理员)
export async function listUsers(params?: {
  search?: string
  role?: string
}): Promise<User[]> {
  const { data } = await apiClient.get('/api/users', { params })
  return data
}

// 创建用户 (仅总管理员)
export async function createUser(params: {
  username: string
  password: string
  email?: string
  full_name?: string
  phone?: string
  role: string
  region_id?: number
}): Promise<User> {
  const { data } = await apiClient.post('/api/users', params)
  return data
}

// 获取用户详情 (仅总管理员)
export async function getUser(userId: number): Promise<User> {
  const { data } = await apiClient.get(`/api/users/${userId}`)
  return data
}

// 更新用户 (仅总管理员)
export async function updateUser(userId: number, params: Partial<{
  email: string
  full_name: string
  phone: string
  role: string
  region_id: number
  is_active: boolean
}>): Promise<User> {
  const { data } = await apiClient.put(`/api/users/${userId}`, params)
  return data
}

// 重置密码 (仅总管理员)
export async function resetPassword(userId: number, newPassword: string): Promise<void> {
  await apiClient.post(`/api/users/${userId}/reset-password`, { new_password: newPassword })
}

// 删除用户 (仅总管理员, 软删除)
export async function deleteUser(userId: number): Promise<void> {
  await apiClient.delete(`/api/users/${userId}`)
}
