import { appApi } from '../../app/api'
import type { FrontendUser } from '../../shared/types/api'

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

export function login(payload: LoginPayload) {
  return appApi.login(payload) as Promise<{
    user: FrontendUser
    redirect_to: string
  }>
}

export function register(payload: RegisterPayload) {
  return appApi.register(payload)
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
  return appApi.forgotPassword(payload) as Promise<{
    success: boolean
    message: string
  }>
}

export function resetPassword(payload: ResetPasswordPayload) {
  return appApi.resetPassword(payload) as Promise<{
    success: boolean
    message: string
  }>
}

