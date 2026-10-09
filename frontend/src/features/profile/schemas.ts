import { z } from 'zod'

export const PASSWORD_MIN_LENGTH = 8
export const PASSWORD_MAX_LENGTH = 255

export type ProfileValidationKey =
  | 'validation.current_password_required'
  | 'validation.new_password_required'
  | 'validation.new_password_min'
  | 'validation.new_password_max'
  | 'validation.confirm_password_required'
  | 'validation.new_password_same_as_current'
  | 'validation.passwords_mismatch'
  | 'validation.unknown_error'
  | 'validation.network_error'

export type ProfileTranslator = (key: ProfileValidationKey, options?: any) => string

export function getChangePasswordSchema(t?: ProfileTranslator) {
  return z
    .object({
      current_password: z
        .string()
        .min(1, t ? t('validation.current_password_required') : 'Vui lòng nhập mật khẩu hiện tại.'),
      new_password: z
        .string()
        .min(1, t ? t('validation.new_password_required') : 'Vui lòng nhập mật khẩu mới.')
        .min(
          PASSWORD_MIN_LENGTH,
          t
            ? t('validation.new_password_min', { min: PASSWORD_MIN_LENGTH })
            : `Mật khẩu mới phải có ít nhất ${PASSWORD_MIN_LENGTH} ký tự.`,
        )
        .max(
          PASSWORD_MAX_LENGTH,
          t
            ? t('validation.new_password_max', { max: PASSWORD_MAX_LENGTH })
            : `Mật khẩu mới không được vượt quá ${PASSWORD_MAX_LENGTH} ký tự.`,
        ),
      confirm_password: z
        .string()
        .min(1, t ? t('validation.confirm_password_required') : 'Vui lòng xác nhận mật khẩu mới.'),
    })
    .refine(
      (data) =>
        !data.current_password ||
        !data.new_password ||
        data.new_password !== data.current_password,
      {
        message: t
          ? t('validation.new_password_same_as_current')
          : 'Mật khẩu mới không được trùng với mật khẩu hiện tại.',
        path: ['new_password'],
      },
    )
    .refine(
      (data) =>
        !data.new_password ||
        !data.confirm_password ||
        data.new_password === data.confirm_password,
      {
        message: t
          ? t('validation.passwords_mismatch')
          : 'Mật khẩu xác nhận không khớp với mật khẩu mới.',
        path: ['confirm_password'],
      },
    )
}

export const changePasswordSchema = getChangePasswordSchema()

export type ChangePasswordFormValues = z.infer<typeof changePasswordSchema>

export type PasswordFieldErrors = {
  current_password?: string
  new_password?: string
  confirm_password?: string
}

export function validateChangePasswordForm(
  values: ChangePasswordFormValues,
  t?: ProfileTranslator,
): {
  success: boolean
  errors: PasswordFieldErrors
} {
  const schema = t ? getChangePasswordSchema(t) : changePasswordSchema
  const result = schema.safeParse(values)
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

export function mapApiErrorToFieldErrors(
  error: unknown,
  t?: ProfileTranslator,
): {
  fieldErrors: PasswordFieldErrors
  unscopedMessage: string | null
} {
  const fallbackMessage = t ? t('validation.unknown_error') : 'Đã có lỗi xảy ra.'
  const networkMessage = t ? t('validation.network_error') : 'Không thể kết nối đến máy chủ.'

  if (error && typeof error === 'object') {
    const maybeField = (error as { field?: string }).field
    const maybeMessage =
      (error as { message?: string }).message || fallbackMessage

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
    unscopedMessage: networkMessage,
  }
}
