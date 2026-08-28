import { appApi } from '@/app/api'
import type {
  PrivateProfileResponse,
  PublicProfileResponse,
  SocialLink,
} from '../types/profile'

export const profileApi = {
  getProfile(): Promise<PrivateProfileResponse> {
    return appApi.get<PrivateProfileResponse>('/api/profile')
  },

  getPublicProfile(username: string): Promise<PublicProfileResponse> {
    return appApi.get<PublicProfileResponse>(`/api/profile/u/${encodeURIComponent(username)}`)
  },

  updateProfile(payload: {
    display_name?: string
    bio?: string
    social_links?: SocialLink[]
    timezone?: string
    email?: string
    current_password?: string
    new_password?: string
    confirm_password?: string
  }): Promise<PrivateProfileResponse> {
    return appApi.mutate<PrivateProfileResponse>('/api/profile', 'PATCH', payload)
  },

  async uploadAvatar(file: File): Promise<{ avatar_url: string }> {
    const formData = new FormData()
    formData.append('file', file)

    return appApi.mutateFormData<{ avatar_url: string }>(
      '/api/profile/avatar',
      'POST',
      formData,
    )
  },

  deleteAvatar(): Promise<{ avatar_url: null }> {
    return appApi.mutate<{ avatar_url: null }>('/api/profile/avatar', 'DELETE')
  },

  requestEmailVerification(): Promise<{ already_verified?: boolean; message?: string }> {
    return appApi.mutate<{ already_verified?: boolean; message?: string }>(
      '/api/profile/verify-email/request',
      'POST',
    )
  },

  verifyEmail(code: string): Promise<{ message?: string; is_verified_student?: boolean }> {
    return appApi.mutate<{ message?: string; is_verified_student?: boolean }>(
      '/api/profile/verify-email/confirm',
      'POST',
      { code },
    )
  },
}
