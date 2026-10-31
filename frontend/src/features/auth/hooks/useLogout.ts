import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { bootstrapQueryKey, clearAccountQueries } from '@/shared/api/bootstrap'
import type { FrontendBootstrap } from '@/shared/types/api'
import { logout } from '../api'

export function useLogout() {
  const { t } = useTranslation('shell')
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  return useMutation({
    mutationFn: logout,
    onSuccess: () => {
      clearAccountQueries(queryClient)
      queryClient.setQueryData<FrontendBootstrap>(
        bootstrapQueryKey,
        (current) =>
          current ? { ...current, user: null, messages: [] } : current,
      )
      toast.success(t('status.logout_success'))
      navigate('/', { replace: true })
    },
    onError: (error: Error) => {
      toast.error(t('status.logout_failed'), { description: error.message })
    },
  })
}
