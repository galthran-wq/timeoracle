import { post, get } from './client'
import type { LoginRequest, TokenResponse, User } from '@/types/auth'

export function login(data: LoginRequest): Promise<TokenResponse> {
  return post<TokenResponse>('/api/users/login', data)
}

export function getMe(): Promise<User> {
  return get<User>('/api/users/me')
}
