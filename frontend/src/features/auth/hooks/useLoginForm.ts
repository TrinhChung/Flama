import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { BACKEND_ORIGIN } from '@/config/env'
import { bootstrapQueryKey } from '@/shared/api/bootstrap'
import type { FrontendBootstrap } from '@/shared/types/api'
import { login } from '../api'
import { loginSchema, type LoginFormValues } from '../schemas'

export function useLoginForm() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const next = searchParams.get('next') || ''
  const [showPassword, setShowPassword] = useState(false)

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
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
      toast.success('Đăng nhập thành công.')
      if (next.startsWith('/') && !next.startsWith('//')) {
        navigate(next, { replace: true })
      } else if (next.startsWith('http://') || next.startsWith('https://')) {
        try {
          const parsed = new URL(next, window.location.origin)
          if (
            parsed.origin === window.location.origin ||
            (BACKEND_ORIGIN && parsed.origin === BACKEND_ORIGIN)
          ) {
            window.location.href = next
            return
          }
        } catch {
          // ignore
        }
        navigate('/dashboard', { replace: true })
      } else if (result.redirect_to.startsWith('/app/')) {
        navigate(result.redirect_to.slice('/app'.length), { replace: true })
      } else {
        navigate('/dashboard', { replace: true })
      }
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
