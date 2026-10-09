import { describe, expect, it } from 'vitest'
import i18n from '@/shared/config/i18n'
import { getLoginSchema, getRegisterSchema, loginSchema, registerSchema } from './schemas'

describe('Auth Validation Schemas with i18n', () => {
  it('validates login schema with default Vietnamese messages', () => {
    const result = loginSchema.safeParse({ email: '', password: '' })
    expect(result.success).toBe(false)
    if (!result.success) {
      const emailErr = result.error.issues.find((i) => i.path[0] === 'email')
      const passErr = result.error.issues.find((i) => i.path[0] === 'password')
      expect(emailErr?.message).toBe('Vui lòng nhập email.')
      expect(passErr?.message).toBe('Vui lòng nhập mật khẩu.')
    }
  })

  it('validates login schema with localized English messages', async () => {
    await i18n.changeLanguage('en')
    const t = (k: string) => i18n.t(k as any, { ns: 'auth' })
    const schema = getLoginSchema(t)

    const result = schema.safeParse({ email: 'invalid-email', password: '' })
    expect(result.success).toBe(false)
    if (!result.success) {
      const emailErr = result.error.issues.find((i) => i.path[0] === 'email')
      const passErr = result.error.issues.find((i) => i.path[0] === 'password')
      expect(emailErr?.message).toBe('Invalid email format.')
      expect(passErr?.message).toBe('Password is required.')
    }
  })

  it('validates register schema with default Vietnamese messages', () => {
    const result = registerSchema.safeParse({
      email: '',
      username: 'a',
      password: '123',
      confirm_password: '456',
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      const issues = result.error.issues.map((i) => i.message)
      expect(issues).toContain('Vui lòng nhập email.')
      expect(issues).toContain('Tên đăng nhập cần ít nhất 2 ký tự.')
      expect(issues).toContain('Mật khẩu cần ít nhất 8 ký tự.')
      expect(issues).toContain('Mật khẩu xác nhận không trùng khớp.')
    }
  })

  it('validates register schema with localized English messages', async () => {
    await i18n.changeLanguage('en')
    const t = (k: string) => i18n.t(k as any, { ns: 'auth' })
    const schema = getRegisterSchema(t)

    const result = schema.safeParse({
      email: 'user@example.com',
      username: 'user',
      password: 'validPassword123',
      confirm_password: 'differentPassword123',
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      const mismatchErr = result.error.issues.find((i) => i.path[0] === 'confirm_password')
      expect(mismatchErr?.message).toBe('Password confirmation does not match.')
    }
  })
})
