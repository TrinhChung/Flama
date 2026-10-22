/** Suggested template categories; authors may still type their own. */
export const TEMPLATE_MARKET_CATEGORIES = [
  'Từ vựng',
  'Kanji / Hán tự',
  'Ngữ pháp',
  'Nghe & Phát âm',
  'Đục lỗ (Cloze)',
  'Luyện gõ',
  'Hỏi đáp (Q&A)',
  'Code & IT',
  'Tối giản',
] as const

export const TEMPLATE_MIN_PRICE = 1000
export type TemplateListingDraft = {
  description: string
  primary_category: string
  pricing_mode: 'free' | 'paid'
  price_amount_minor: number
}
export function templateListingValidationError(draft: TemplateListingDraft): 'description' | 'category' | 'price' | null {
  if (!draft.description.trim()) return 'description'
  if (!draft.primary_category.trim()) return 'category'
  if (draft.pricing_mode === 'paid' && (!Number.isInteger(draft.price_amount_minor) || draft.price_amount_minor < TEMPLATE_MIN_PRICE)) return 'price'
  return null
}
