import { z } from 'zod'

z.config({ jitless: true })

const text = z.string().max(1_000_000)
const artifactTemplate = z.object({
  renderer_abi: z.literal('flama-client-mustache.v2'), version: text,
  front_source: text, back_source: text, shared_css: text,
  front_inline_scripts: z.array(text).max(100), back_inline_scripts: z.array(text).max(100),
  field_defs: z.array(z.object({ id: z.string().optional(), name: text,
    field_type: text, required: z.boolean().optional(), position: z.number().optional() })).max(100),
})
const artifactContent = z.object({
  renderer_abi: z.literal('flama-client-mustache.v2'),
  field_values: z.record(z.string(), z.unknown()), render_context: z.record(z.string(), z.unknown()),
  media: z.array(z.object({ id: text, field_name: text, filename: text,
    mime_type: text, sha256: text, proxy_url: text })).max(500),
})
export const previewSchema = z.object({
  schema_version: z.literal('template-preview.v1'),
  candidate_hash: z.string().min(1).max(160).nullable(), renderer_abi: z.literal('flama-client-mustache.v2'),
  checks: z.record(z.string(), z.enum(['passed', 'failed', 'not_run', 'unsupported'])),
  diagnostics: z.array(z.object({ code: z.string().max(100), severity: z.enum(['error', 'warning', 'info']),
    stage: z.string().max(100), source_part: z.string().max(200), message: z.string().max(4000),
    hint: z.string().max(4000).optional(), line: z.number().int().positive().nullable().optional(),
    column: z.number().int().positive().nullable().optional(), suggestions: z.array(z.string().max(255)).max(5).optional() })).max(200),
  preview: z.object({ template_artifact: artifactTemplate, content_artifact: artifactContent }).nullable(),
  sample_source: z.record(z.string(), z.unknown()).optional(),
  media_base_url: z.string().max(2000).optional(),
})
export type TemplatePreview = z.infer<typeof previewSchema>

export function parseTemplatePreview(result: unknown): TemplatePreview {
  if (!result || typeof result !== 'object') throw new Error('Missing preview result.')
  const envelope = result as Record<string, unknown>
  const structured = envelope.structuredContent
  if (envelope.isError && (!structured || typeof structured !== 'object' || !('schema_version' in structured))) {
    throw new Error('Template preview failed. Check the tool diagnostics in chat.')
  }
  const candidate = envelope.structuredContent ?? result
  const metadata = envelope._meta as Record<string, unknown> | undefined
  const hidden = metadata?.['flama/template-preview'] as Record<string, unknown> | undefined
  // Hidden UI payloads never replace the candidate identity or checks seen by the model.
  const hydrated = candidate && typeof candidate === 'object' && hidden
    && hidden.candidate_hash === (candidate as Record<string, unknown>).candidate_hash
    ? { ...candidate, preview: hidden.preview } : candidate
  const parsed = previewSchema.safeParse(hydrated)
  if (!parsed.success) throw new Error('Invalid or incompatible template preview result.')
  return parsed.data
}
