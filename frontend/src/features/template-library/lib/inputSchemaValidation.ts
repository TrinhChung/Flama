import type { TemplateInputSpec } from '@/entities/card-template'

export const templateInputTypes = ['text', 'richtext', 'markdown', 'image', 'audio', 'diagram'] as const
export function inputSchemaIssues(value: TemplateInputSpec[]): Array<{ index: number; message: string }> {
  const issues: Array<{ index: number; message: string }> = []
  const seen = new Set<string>()
  value.forEach((input, index) => {
    if (!input.key || input.key.trim() !== input.key || /[{}#^/!>&=\r\n]/.test(input.key) || input.key === '.' || input.key === 'FrontSide') issues.push({ index, message: 'Key không hợp lệ: không để trống, thêm khoảng trắng ở đầu/cuối hoặc dùng ký tự dành riêng.' })
    if (seen.has(input.key)) issues.push({ index, message: 'Key input phải duy nhất.' })
    seen.add(input.key)
    if (input.label.length > 255) issues.push({ index, message: 'Nhãn tối đa 255 ký tự.' })
    if (!(templateInputTypes as readonly string[]).includes(input.type)) issues.push({ index, message: 'Kiểu input không hợp lệ.' })
  })
  return issues
}
