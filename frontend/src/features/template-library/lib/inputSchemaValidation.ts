import type { TemplateInputSpec } from '@/entities/card-template'

export const templateInputTypes = ['text', 'richtext', 'markdown', 'image', 'audio', 'diagram'] as const
export function inputSchemaIssues(value: TemplateInputSpec[], t?: (key: 'input_schema.val_invalid_key' | 'input_schema.val_unique_key' | 'input_schema.val_label_max' | 'input_schema.val_invalid_type') => string): Array<{ index: number; message: string }> {
  const issues: Array<{ index: number; message: string }> = []
  const seen = new Set<string>()
  value.forEach((input, index) => {
    if (!input.key || input.key.trim() !== input.key || /[{}#^/!>&=\r\n]/.test(input.key) || input.key === '.' || input.key === 'FrontSide') {
      issues.push({ index, message: t ? t('input_schema.val_invalid_key') : 'Key không hợp lệ: không để trống, thêm khoảng trắng ở đầu/cuối hoặc dùng ký tự dành riêng.' })
    }
    if (seen.has(input.key)) {
      issues.push({ index, message: t ? t('input_schema.val_unique_key') : 'Key input phải duy nhất.' })
    }
    seen.add(input.key)
    if (input.label.length > 255) {
      issues.push({ index, message: t ? t('input_schema.val_label_max') : 'Nhãn tối đa 255 ký tự.' })
    }
    if (!(templateInputTypes as readonly string[]).includes(input.type)) {
      issues.push({ index, message: t ? t('input_schema.val_invalid_type') : 'Kiểu input không hợp lệ.' })
    }
  })
  return issues
}
