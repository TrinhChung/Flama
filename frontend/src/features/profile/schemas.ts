import { z } from 'zod'

export const PASSWORD_MIN_LENGTH = 8
export const PASSWORD_MAX_LENGTH = 255

export const changePasswordSchema = z
  .object({
    current_password: z
      .string()
      .min(1, 'Vui lòng nhập mật khẩu hiện tại.'),
    new_password: z
      .string()
      .min(1, 'Vui lòng nhập mật khẩu mới.')
      .min(
        PASSWORD_MIN_LENGTH,
        `Mật khẩu mới phải có ít nhất ${PASSWORD_MIN_LENGTH} ký tự.`,
      )
      .max(
        PASSWORD_MAX_LENGTH,
        `Mật khẩu mới không được vượt quá ${PASSWORD_MAX_LENGTH} ký tự.`,
      ),
    confirm_password: z
      .string()
      .min(1, 'Vui lòng xác nhận mật khẩu mới.'),
  })
  .refine(
    (data) =>
      !data.current_password ||
      !data.new_password ||
      data.new_password !== data.current_password,
    {
      message: 'Mật khẩu mới không được trùng với mật khẩu hiện tại.',
      path: ['new_password'],
    },
  )
  .refine(
    (data) =>
      !data.new_password ||
      !data.confirm_password ||
      data.new_password === data.confirm_password,
    {
      message: 'Mật khẩu xác nhận không khớp với mật khẩu mới.',
      path: ['confirm_password'],
    },
  )

export type ChangePasswordFormValues = z.infer<typeof changePasswordSchema>

export type PasswordFieldErrors = {
  current_password?: string
  new_password?: string
  confirm_password?: string
}

export function validateChangePasswordForm(values: ChangePasswordFormValues): {
  success: boolean
  errors: PasswordFieldErrors
} {
  const result = changePasswordSchema.safeParse(values)
  if (result.success) {
    return { success: true, errors: {} }
  }

  const errors: PasswordFieldErrors = {}
  for (const issue of result.error.issues) {
    const field = issue.path[0] as keyof PasswordFieldErrors
    if (field && !errors[field]) {
      errors[field] = issue.message
    }
  }

  return { success: false, errors }
}

export function mapApiErrorToFieldErrors(error: unknown): {
  fieldErrors: PasswordFieldErrors
  unscopedMessage: string | null
} {
  if (error && typeof error === 'object') {
    const maybeField = (error as { field?: string }).field
    const maybeMessage =
      (error as { message?: string }).message || 'Đã có lỗi xảy ra.'

    if (
      maybeField === 'current_password' ||
      maybeField === 'new_password' ||
      maybeField === 'confirm_password'
    ) {
      return {
        fieldErrors: {
          [maybeField]: maybeMessage,
        },
        unscopedMessage: null,
      }
    }

    return {
      fieldErrors: {},
      unscopedMessage: maybeMessage,
    }
  }

  return {
    fieldErrors: {},
    unscopedMessage: 'Không thể kết nối đến máy chủ.',
  }
}
