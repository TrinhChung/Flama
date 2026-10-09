import i18next from 'i18next'
import { ApiError } from '@/shared/api/client'

export function templateErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'SHARED_SCHEMA_VERSIONING_REQUIRED') {
      return i18next.isInitialized
        ? i18next.t('note_types:errors.shared_schema_versioning', {
            defaultValue:
              'Template này đang dùng trong bộ thẻ đã chia sẻ nên chưa thể thêm, xóa hoặc đặt lại. Bạn vẫn có thể sửa nội dung HTML/CSS.',
          })
        : 'Template này đang dùng trong bộ thẻ đã chia sẻ nên chưa thể thêm, xóa hoặc đặt lại. Bạn vẫn có thể sửa nội dung HTML/CSS.'
    }
    if (error.code === 'TEMPLATE_COMPILE_ERROR') {
      return i18next.isInitialized
        ? i18next.t('note_types:errors.compile_error', {
            message: error.message,
            defaultValue: `Template có lỗi cú pháp: ${error.message}`,
          })
        : `Template có lỗi cú pháp: ${error.message}`
    }
    if (error.message === 'Cannot delete default template.') {
      return i18next.isInitialized
        ? i18next.t('note_types:errors.cannot_delete_default', {
            defaultValue: 'Không thể xóa template mặc định.',
          })
        : 'Không thể xóa template mặc định.'
    }
    if (error.message === 'A note type requires at least one template.') {
      return i18next.isInitialized
        ? i18next.t('note_types:errors.requires_at_least_one', {
            defaultValue: 'Loại thẻ cần ít nhất một template.',
          })
        : 'Loại thẻ cần ít nhất một template.'
    }
    return (
      error.message?.trim() ||
      (i18next.isInitialized
        ? i18next.t('note_types:errors.generic', {
            defaultValue: 'Đã có lỗi xảy ra. Vui lòng thử lại.',
          })
        : 'Đã có lỗi xảy ra. Vui lòng thử lại.')
    )
  }
  if (error instanceof Error && error.message?.trim()) return error.message.trim()
  return i18next.isInitialized
    ? i18next.t('note_types:errors.generic', {
        defaultValue: 'Đã có lỗi xảy ra. Vui lòng thử lại.',
      })
    : 'Đã có lỗi xảy ra. Vui lòng thử lại.'
}
