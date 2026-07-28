import { z } from 'zod'

export const createDeckSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, 'Vui lòng nhập tên deck.')
    .max(255, 'Tên deck quá dài.'),
  deck_path: z.string().trim().max(1000, 'Đường dẫn deck quá dài.'),
  parent_id: z.string(),
})

export type CreateDeckForm = z.infer<typeof createDeckSchema>

export const renameDeckSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, 'Vui lòng nhập tên deck.')
    .max(255, 'Tên deck quá dài.'),
})

export type RenameDeckForm = z.infer<typeof renameDeckSchema>

export const moveDeckSchema = z.object({
  parent_id: z.string(),
})

export type MoveDeckForm = z.infer<typeof moveDeckSchema>
