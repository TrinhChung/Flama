import { ApiError } from '@/shared/api/client'

export function templateErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'SHARED_SCHEMA_VERSIONING_REQUIRED') {
      return 'Template này đang dùng trong bộ thẻ đã chia sẻ nên chưa thể thêm, xóa hoặc đặt lại. Bạn vẫn có thể sửa nội dung HTML/CSS.'
    }
    if (error.code === 'TEMPLATE_COMPILE_ERROR') {
      return `Template có lỗi cú pháp: ${error.message}`
    }
    if (error.message === 'Cannot delete default template.') {
      return 'Không thể xóa template mặc định.'
    }
    if (error.message === 'A note type requires at least one template.') {
      return 'Loại thẻ cần ít nhất một template.'
    }
    return error.message?.trim() || 'Đã có lỗi xảy ra. Vui lòng thử lại.'
  }
  if (error instanceof Error && error.message?.trim()) return error.message.trim()
  return 'Đã có lỗi xảy ra. Vui lòng thử lại.'
}
