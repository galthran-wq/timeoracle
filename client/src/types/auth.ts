export interface User {
  id: string
  email: string | null
  is_verified: boolean
  is_superuser: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface LoginRequest {
  email: string
  password: string
}
