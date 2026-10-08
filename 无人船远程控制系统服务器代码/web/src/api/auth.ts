import { apiClient } from './client'
import type { TokenResponse, User } from '../types'

// 登录 (OAuth2表单格式)
export async function login(username: string, password: string): Promise<TokenResponse> {
  const formData = new FormData()
  formData.append('username', username)
  formData.append('password', password)
  const { data } = await apiClient.post('/api/auth/login', formData)
  return data
}

// 注册
export async function register(params: {
  username: string
  password: string
  email?: string
  full_name?: string
}): Promise<User> {
  const { data } = await apiClient.post('/api/auth/register', params)
  return data
}

// 获取当前用户
export async function getMe(): Promise<User> {
  const { data } = await apiClient.get('/api/auth/me')
  return data
}
