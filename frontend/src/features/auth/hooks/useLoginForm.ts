import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { bootstrapQueryKey } from '@/shared/api/bootstrap'
import type { FrontendBootstrap } from '@/shared/types/api'
import { login } from '../api'
import { getLoginSchema, type LoginFormValues } from '../schemas'
import { performRedirect, resolveRedirectTarget } from '../utils/redirect'

export function useLoginForm() {
  const { t } = useTranslation('auth')
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const next = searchParams.get('next') || ''
  const [showPassword, setShowPassword] = useState(false)

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(getLoginSchema((k) => t(k as any))),
    defaultValues: { email: '', password: '' },
  })

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: (result) => {
      queryClient.setQueryData<FrontendBootstrap>(
        bootstrapQueryKey,
        (current) => (current ? { ...current, user: result.user, messages: [] } : current),
      )
      void queryClient.invalidateQueries({ queryKey: bootstrapQueryKey })
      toast.success(t('login.success_toast'))

      const target = resolveRedirectTarget(next, result.redirect_to)
      performRedirect(target, navigate)
    },
  })

  const toggleShowPassword = () => setShowPassword((prev) => !prev)

  const onSubmit = form.handleSubmit((values) => {
    mutation.mutate({ ...values, next })
  })

  return {
    form,
    showPassword,
    toggleShowPassword,
    isPending: mutation.isPending,
    error: mutation.error,
    onSubmit,
  }
}
