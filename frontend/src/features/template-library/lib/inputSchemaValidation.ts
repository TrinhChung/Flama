import type { TemplateInputSpec, TemplateTypingOptions } from '@/entities/card-template'

export const templateInputTypes = ['text', 'richtext', 'markdown', 'image', 'audio', 'diagram', 'answers'] as const
export const defaultTypingOptions: TemplateTypingOptions = { show_length: true, hints: true }

type IssueKey = 'input_schema.val_invalid_key' | 'input_schema.val_unique_key' | 'input_schema.val_label_max' | 'input_schema.val_invalid_type' | 'input_schema.val_single_answers'

export function inputSchemaIssues(value: TemplateInputSpec[], t?: (key: IssueKey) => string): Array<{ index: number; message: string }> {
  const issues: Array<{ index: number; message: string }> = []
  const seen = new Set<string>()
  // Parked 2026-10-10: host typing mode (STUDY_TYPING_ANSWER_PLAN §12) allowed a
  // single answers input; templates now check answers in their own HTML/JS.
  // let answersSeen = false
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
    // if (input.type === 'answers') {
    //   if (answersSeen) issues.push({ index, message: t ? t('input_schema.val_single_answers') : 'Mỗi mẫu chỉ có một input đáp án gõ.' })
    //   answersSeen = true
    // }
  })
  return issues
}

/** Changing an input's type drops typing options saved by the parked typing mode. */
export function withInputType(input: TemplateInputSpec, type: TemplateInputSpec['type']): TemplateInputSpec {
  const { typing: _typing, ...rest } = input
  // Parked 2026-10-10: host typing mode (STUDY_TYPING_ANSWER_PLAN §12).
  // return type === 'answers'
  //   ? { ...rest, type, typing: input.typing ?? { ...defaultTypingOptions } }
  //   : { ...rest, type }
  return { ...rest, type }
}
