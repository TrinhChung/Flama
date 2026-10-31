import { apiJson, setCsrfToken } from '@/shared/api/client'
import { API_BASE_URL } from '@/shared/config/env'
import type { FrontendUser } from '@/shared/types/api'

export type LoginPayload = {
  email: string
  password: string
  next?: string
}

export type RegisterPayload = {
  email: string
  username: string
  password: string
  confirm_password: string
}

type SessionResponse = {
  authenticated: boolean
  user: FrontendUser | null
  csrf_token: string
}

type LoginResponse = SessionResponse & {
  next_url: string
}

type RegisterResponse = {
  created: boolean
  user: Pick<FrontendUser, 'id' | 'email' | 'username'>
}

export async function login(payload: LoginPayload): Promise<{ user: FrontendUser; redirect_to: string }> {
  const result = await apiJson<LoginResponse>(`${API_BASE_URL}/auth/login`, 'POST', payload)
  setCsrfToken(result.csrf_token)
  if (!result.user) {
    throw new Error('The server did not create an authenticated session.')
  }
  return {
    user: result.user,
    redirect_to: result.next_url || '/dashboard',
  }
}

/** Ends the session; the response carries the CSRF token of the new anonymous session. */
export async function logout(): Promise<{ redirect_to: string }> {
  const result = await apiJson<SessionResponse>(`${API_BASE_URL}/session`, 'DELETE')
  setCsrfToken(result.csrf_token)
  return { redirect_to: '/' }
}

export async function register(payload: RegisterPayload) {
  await apiJson<RegisterResponse>(`${API_BASE_URL}/auth/register`, 'POST', payload)
  return {
    message: 'Đăng ký thành công. Bạn có thể đăng nhập ngay.',
    redirect_to: '/login',
  }
}

export type ForgotPasswordPayload = {
  email: string
}

export type ResetPasswordPayload = {
  token: string
  new_password: string
  confirm_password?: string
}

export function forgotPassword(payload: ForgotPasswordPayload) {
  return apiJson<{ success: boolean; message: string }>(
    `${API_BASE_URL}/auth/forgot-password`,
    'POST',
    payload,
  )
}

export function resetPassword(payload: ResetPasswordPayload) {
  return apiJson<{ success: boolean; message: string }>(
    `${API_BASE_URL}/auth/reset-password`,
    'POST',
    payload,
  )
}

export function requestEmailVerification() {
  return apiJson<{
    success: boolean
    already_verified?: boolean
    message?: string
    expires_in_minutes?: number
  }>('/api/profile/verify-email/request', 'POST')
}

export function verifyEmail(codeOrToken: string) {
  return apiJson<{
    success: boolean
    message?: string
    email_verified?: boolean
    is_verified_student?: boolean
    student_status?: string
  }>('/api/profile/verify-email/confirm', 'POST', { code: codeOrToken })
}
