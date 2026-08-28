import { describe, expect, it } from 'vitest'
import { ApiError } from '@/shared/api/client'
import {
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  changePasswordSchema,
  mapApiErrorToFieldErrors,
  validateChangePasswordForm,
} from './schemas'

describe('changePasswordSchema and validateChangePasswordForm', () => {
  it('rejects empty fields with required messages', () => {
    const values = {
      current_password: '',
      new_password: '',
      confirm_password: '',
    }
    const result = validateChangePasswordForm(values)
    expect(result.success).toBe(false)
    expect(result.errors.current_password).toBe('Vui lòng nhập mật khẩu hiện tại.')
    expect(result.errors.new_password).toBe('Vui lòng nhập mật khẩu mới.')
    expect(result.errors.confirm_password).toBe('Vui lòng xác nhận mật khẩu mới.')
  })

  it('rejects new password shorter than 8 characters', () => {
    const values = {
      current_password: 'current-valid-pw',
      new_password: 'short',
      confirm_password: 'short',
    }
    const result = validateChangePasswordForm(values)
    expect(result.success).toBe(false)
    expect(result.errors.new_password).toBe(
      `Mật khẩu mới phải có ít nhất ${PASSWORD_MIN_LENGTH} ký tự.`,
    )
  })

  it('rejects new password exceeding 255 characters', () => {
    const values = {
      current_password: 'current-valid-pw',
      new_password: 'a'.repeat(256),
      confirm_password: 'a'.repeat(256),
    }
    const result = validateChangePasswordForm(values)
    expect(result.success).toBe(false)
    expect(result.errors.new_password).toBe(
      `Mật khẩu mới không được vượt quá ${PASSWORD_MAX_LENGTH} ký tự.`,
    )
  })

  it('rejects new password when it is identical to current password (password reuse)', () => {
    const values = {
      current_password: 'my-strong-password-123',
      new_password: 'my-strong-password-123',
      confirm_password: 'my-strong-password-123',
    }
    const result = validateChangePasswordForm(values)
    expect(result.success).toBe(false)
    expect(result.errors.new_password).toBe(
      'Mật khẩu mới không được trùng với mật khẩu hiện tại.',
    )
  })

  it('rejects when confirm_password does not match new_password', () => {
    const values = {
      current_password: 'current-password-123',
      new_password: 'new-password-456',
      confirm_password: 'different-password-789',
    }
    const result = validateChangePasswordForm(values)
    expect(result.success).toBe(false)
    expect(result.errors.confirm_password).toBe(
      'Mật khẩu xác nhận không khớp với mật khẩu mới.',
    )
  })

  it('accepts valid password change payload', () => {
    const values = {
      current_password: 'current-password-123',
      new_password: 'new-secure-password-456',
      confirm_password: 'new-secure-password-456',
    }
    const result = validateChangePasswordForm(values)
    expect(result.success).toBe(true)
    expect(result.errors).toEqual({})
  })

  it('validates bounds: exactly 8 and 255 characters are allowed', () => {
    const minPass = 'a'.repeat(8)
    const validMin = changePasswordSchema.safeParse({
      current_password: 'current-password',
      new_password: minPass,
      confirm_password: minPass,
    })
    expect(validMin.success).toBe(true)

    const maxPass = 'b'.repeat(255)
    const validMax = changePasswordSchema.safeParse({
      current_password: 'current-password',
      new_password: maxPass,
      confirm_password: maxPass,
    })
    expect(validMax.success).toBe(true)
  })
})

describe('mapApiErrorToFieldErrors', () => {
  it('maps backend current_password error to inline field error', () => {
    const error = new ApiError(
      'Current password is incorrect.',
      400,
      'INVALID_CURRENT_PASSWORD',
      'current_password',
    )
    const result = mapApiErrorToFieldErrors(error)
    expect(result.fieldErrors.current_password).toBe(
      'Current password is incorrect.',
    )
    expect(result.unscopedMessage).toBeNull()
  })

  it('maps backend new_password error to inline field error', () => {
    const error = new ApiError(
      'New password must be different from current password.',
      400,
      'PASSWORD_REUSED',
      'new_password',
    )
    const result = mapApiErrorToFieldErrors(error)
    expect(result.fieldErrors.new_password).toBe(
      'New password must be different from current password.',
    )
    expect(result.unscopedMessage).toBeNull()
  })

  it('maps backend confirm_password error to inline field error', () => {
    const error = new ApiError(
      'Password confirmation does not match.',
      400,
      'VALIDATION_ERROR',
      'confirm_password',
    )
    const result = mapApiErrorToFieldErrors(error)
    expect(result.fieldErrors.confirm_password).toBe(
      'Password confirmation does not match.',
    )
    expect(result.unscopedMessage).toBeNull()
  })

  it('treats unscoped ApiError (e.g. PASSWORD_NOT_SET) as unscoped message for toast', () => {
    const error = new ApiError(
      'This account does not have a password configured.',
      400,
      'PASSWORD_NOT_SET',
    )
    const result = mapApiErrorToFieldErrors(error)
    expect(result.fieldErrors).toEqual({})
    expect(result.unscopedMessage).toBe(
      'This account does not have a password configured.',
    )
  })

  it('treats unknown/network error as unscoped message for toast', () => {
    const result = mapApiErrorToFieldErrors(new Error('Network disconnected'))
    expect(result.fieldErrors).toEqual({})
    expect(result.unscopedMessage).toBe('Network disconnected')

    const nullResult = mapApiErrorToFieldErrors(null)
    expect(nullResult.unscopedMessage).toBe('Không thể kết nối đến máy chủ.')
  })
})
