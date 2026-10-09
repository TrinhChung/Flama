import { describe, expect, it } from 'vitest'
import { ApiError } from '@/shared/api/client'
import { templateErrorMessage } from './templateErrors'

describe('templateErrorMessage', () => {
  it('xử lý ApiError mã SHARED_SCHEMA_VERSIONING_REQUIRED', () => {
    const error = new ApiError('schema error', 409, 'SHARED_SCHEMA_VERSIONING_REQUIRED')
    expect(templateErrorMessage(error)).toBe(
      'Giao diện thẻ này đang dùng trong bộ thẻ đã chia sẻ nên chưa thể thêm, xóa hoặc đặt lại. Bạn vẫn có thể sửa nội dung HTML/CSS.',
    )
  })

  it('xử lý ApiError mã TEMPLATE_COMPILE_ERROR', () => {
    const error = new ApiError('Unclosed tag {{Kanji}}', 400, 'TEMPLATE_COMPILE_ERROR')
    expect(templateErrorMessage(error)).toBe('Template có lỗi cú pháp: Unclosed tag {{Kanji}}')
  })

  it('xử lý ApiError Cannot delete default template.', () => {
    const error = new ApiError('Cannot delete default template.', 409, 'VALIDATION_ERROR')
    expect(templateErrorMessage(error)).toBe('Không thể xóa giao diện thẻ mặc định.')
  })

  it('xử lý ApiError A note type requires at least one template.', () => {
    const error = new ApiError('A note type requires at least one template.', 409, 'VALIDATION_ERROR')
    expect(templateErrorMessage(error)).toBe('Cấu trúc thẻ cần ít nhất một giao diện thẻ.')
  })

  it('xử lý ApiError thông thường giữ nguyên message', () => {
    const error = new ApiError('Tên không hợp lệ', 400, 'VALIDATION_ERROR')
    expect(templateErrorMessage(error)).toBe('Tên không hợp lệ')
  })

  it('xử lý ApiError với message rỗng trả thông báo mặc định', () => {
    const error = new ApiError('', 400, 'VALIDATION_ERROR')
    expect(templateErrorMessage(error)).toBe('Đã có lỗi xảy ra. Vui lòng thử lại.')
  })

  it('xử lý Error thông thường có message', () => {
    const error = new Error('Lỗi kết nối mạng')
    expect(templateErrorMessage(error)).toBe('Lỗi kết nối mạng')
  })

  it('xử lý Error với message rỗng trả thông báo mặc định', () => {
    const error = new Error('')
    expect(templateErrorMessage(error)).toBe('Đã có lỗi xảy ra. Vui lòng thử lại.')
  })

  it('xử lý ApiError và Error với message chỉ chứa khoảng trắng trả thông báo mặc định', () => {
    const apiError = new ApiError('   ', 400, 'VALIDATION_ERROR')
    expect(templateErrorMessage(apiError)).toBe('Đã có lỗi xảy ra. Vui lòng thử lại.')
    const standardError = new Error('   ')
    expect(templateErrorMessage(standardError)).toBe('Đã có lỗi xảy ra. Vui lòng thử lại.')
  })

  it('xử lý giá trị không phải Error trả thông báo mặc định', () => {
    expect(templateErrorMessage(null)).toBe('Đã có lỗi xảy ra. Vui lòng thử lại.')
    expect(templateErrorMessage(undefined)).toBe('Đã có lỗi xảy ra. Vui lòng thử lại.')
    expect(templateErrorMessage('chuỗi lỗi')).toBe('Đã có lỗi xảy ra. Vui lòng thử lại.')
    expect(templateErrorMessage({ error: 'unknown' })).toBe('Đã có lỗi xảy ra. Vui lòng thử lại.')
  })
})
