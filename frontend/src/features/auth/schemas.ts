import { z } from 'zod'

export const loginSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, 'Vui lòng nhập email.')
    .email('Email không đúng định dạng.'),
  password: z.string().min(1, 'Vui lòng nhập mật khẩu.'),
})

export type LoginFormValues = z.infer<typeof loginSchema>

export const registerSchema = z
  .object({
    email: z
      .string()
      .trim()
      .min(1, 'Vui lòng nhập email.')
      .email('Email không đúng định dạng.'),
    username: z
      .string()
      .trim()
      .min(2, 'Tên đăng nhập cần ít nhất 2 ký tự.')
      .max(150, 'Tên đăng nhập quá dài.'),
    password: z
      .string()
      .min(8, 'Mật khẩu cần ít nhất 8 ký tự.')
      .max(255, 'Mật khẩu quá dài.'),
    confirm_password: z.string().min(1, 'Vui lòng xác nhận mật khẩu.'),
  })
  .refine((values) => values.password === values.confirm_password, {
    message: 'Mật khẩu xác nhận không trùng khớp.',
    path: ['confirm_password'],
  })

export type RegisterFormValues = z.infer<typeof registerSchema>
