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
}
