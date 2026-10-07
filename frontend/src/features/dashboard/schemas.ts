import { z } from 'zod'
import i18n from '@/shared/config/i18n'

export type DashboardTranslator = (key: any) => string

function defaultTranslator(key: string): string {
  return i18n.isInitialized ? (i18n.t as any)(key, { ns: 'dashboard' }) : (key === 'validation.name_required' ? 'Vui lòng nhập tên deck.' : key === 'validation.name_max' ? 'Tên deck quá dài.' : 'Đường dẫn deck quá dài.')
}

export function getCreateDeckSchema(t?: DashboardTranslator) {
  const translate = t || defaultTranslator
  return z.object({
    name: z
      .string()
      .trim()
      .min(1, translate('validation.name_required'))
      .max(255, translate('validation.name_max')),
    deck_path: z
      .string()
      .trim()
      .max(1000, translate('validation.path_max')),
    parent_id: z.string(),
    note_type_id: z.string().optional(),
  })
}

export const createDeckSchema = getCreateDeckSchema()
export type CreateDeckForm = z.infer<typeof createDeckSchema>

export function getRenameDeckSchema(t?: DashboardTranslator) {
  const translate = t || defaultTranslator
  return z.object({
    name: z
      .string()
      .trim()
      .min(1, translate('validation.name_required'))
      .max(255, translate('validation.name_max')),
  })
}

export const renameDeckSchema = getRenameDeckSchema()
export type RenameDeckForm = z.infer<typeof renameDeckSchema>

export const moveDeckSchema = z.object({
  parent_id: z.string(),
})

export type MoveDeckForm = z.infer<typeof moveDeckSchema>
