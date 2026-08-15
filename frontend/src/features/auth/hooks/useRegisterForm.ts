import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { register } from '../api'
import { registerSchema, type RegisterFormValues } from '../schemas'

export function useRegisterForm() {
  const navigate = useNavigate()
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { email: '', username: '', password: '', confirm_password: '' },
    mode: 'onChange',
  })

  const mutation = useMutation({
    mutationFn: register,
    onSuccess: (result) => {
      toast.success(result.message)
      navigate('/login', { replace: true })
    },
  })

  const toggleShowPassword = () => setShowPassword((prev) => !prev)
  const toggleShowConfirmPassword = () => setShowConfirmPassword((prev) => !prev)

  const passwordValue = form.watch('password') || ''
  const confirmPasswordValue = form.watch('confirm_password') || ''
  const isMinLength = passwordValue.length >= 8
  const isMatching = confirmPasswordValue.length > 0 && passwordValue === confirmPasswordValue

  const onSubmit = form.handleSubmit((values) => {
    mutation.mutate(values)
  })

  return {
    form,
    showPassword,
    toggleShowPassword,
    showConfirmPassword,
    toggleShowConfirmPassword,
    isPending: mutation.isPending,
    error: mutation.error,
    passwordValue,
    confirmPasswordValue,
    isMinLength,
    isMatching,
    onSubmit,
  }
}
