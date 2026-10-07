import { z } from 'zod'

export type AuthTranslator = (key: string) => string

export function getLoginSchema(t?: AuthTranslator) {
  return z.object({
    email: z
      .string()
      .trim()
      .min(1, t ? t('validation.email_required') : 'Vui lòng nhập email.')
      .email(t ? t('validation.email_invalid') : 'Email không đúng định dạng.'),
    password: z.string().min(1, t ? t('validation.password_required') : 'Vui lòng nhập mật khẩu.'),
  })
}

export const loginSchema = getLoginSchema()
export type LoginFormValues = z.infer<typeof loginSchema>

export function getRegisterSchema(t?: AuthTranslator) {
  return z
    .object({
      email: z
        .string()
        .trim()
        .min(1, t ? t('validation.email_required') : 'Vui lòng nhập email.')
        .email(t ? t('validation.email_invalid') : 'Email không đúng định dạng.'),
      username: z
        .string()
        .trim()
        .min(2, t ? t('validation.username_min') : 'Tên đăng nhập cần ít nhất 2 ký tự.')
        .max(150, t ? t('validation.username_max') : 'Tên đăng nhập quá dài.'),
      password: z
        .string()
        .min(8, t ? t('validation.password_min') : 'Mật khẩu cần ít nhất 8 ký tự.')
        .max(255, t ? t('validation.password_max') : 'Mật khẩu quá dài.'),
      confirm_password: z
        .string()
        .min(1, t ? t('validation.confirm_required') : 'Vui lòng xác nhận mật khẩu.'),
    })
    .refine((values) => values.password === values.confirm_password, {
      message: t ? t('validation.passwords_mismatch') : 'Mật khẩu xác nhận không trùng khớp.',
      path: ['confirm_password'],
    })
}

export const registerSchema = getRegisterSchema()
export type RegisterFormValues = z.infer<typeof registerSchema>
