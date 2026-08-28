import { appApi } from '@/app/api'
import type {
  ProfileResponse,
  ProfileTransactionsResponse,
} from '../types/profile'

export const profileApi = {
  getProfile(): Promise<ProfileResponse> {
    return appApi.get<ProfileResponse>('/api/profile')
  },

  updateProfile(payload: {
    timezone?: string
    current_password?: string
    new_password?: string
    confirm_password?: string
  }): Promise<ProfileResponse> {
    return appApi.mutate<ProfileResponse>('/api/profile', 'PATCH', payload)
  },

  listTransactions(params?: {
    page?: number
    per_page?: number
    type?: string
  }): Promise<ProfileTransactionsResponse> {
    const searchParams = new URLSearchParams()
    if (params?.page) searchParams.set('page', String(params.page))
    if (params?.per_page) searchParams.set('per_page', String(params.per_page))
    if (params?.type) searchParams.set('type', params.type)

    const qs = searchParams.toString()
    return appApi.get<ProfileTransactionsResponse>(
      `/api/profile/transactions${qs ? `?${qs}` : ''}`
    )
  },

  requestEmailVerification(): Promise<{
    success: boolean
    already_verified: boolean
    message: string
    expires_in_minutes?: number
  }> {
    return appApi.mutate('/api/identity/email/request-verification', 'POST')
  },

  verifyEmail(code: string): Promise<{
    success: boolean
    message: string
    email_verified: boolean
    email_verified_at: string
    student_status: string
    is_verified_student: boolean
  }> {
    return appApi.mutate('/api/identity/email/verify', 'POST', { code })
  },

  getStudentStatus(): Promise<{
    email_verified: boolean
    email_verified_at: string | null
    email_verification_source: string | null
    student_status: string
    is_verified_student: boolean
    is_edu_email: boolean
    institution_domain: string | null
  }> {
    return appApi.get('/api/identity/student-status')
  },
}
