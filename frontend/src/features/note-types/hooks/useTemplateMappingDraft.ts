import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { apiRequest } from '@/shared/api/client'
import {
  cardTemplateQueryKeys, fetchTemplateApplications, previewLibraryTemplate, updateTemplateApplication, validateBindings,
  type MappingField, type TemplateApplication, type TemplateBindings, type TemplateInputSpec, type TemplateLibraryPreview,
} from '@/entities/card-template'

export type MappingNoteType = { id: string; name: string; field_defs: Array<MappingField & { position: number; required?: boolean }> }
type Draft = { applicationId: string; bindings: TemplateBindings; name: string; baseline: string; source: string }
const fingerprint = (name: string, bindings: TemplateBindings) => JSON.stringify([name, Object.entries(bindings).sort(([a], [b]) => a.localeCompare(b))])
const sourceFingerprint = (application: TemplateApplication, fields: MappingField[]) => JSON.stringify([
  application.template.current_version_id, application.input_schema, fields.map((field) => [field.id, field.name, field.field_type]),
])
const fromApplication = (application: TemplateApplication, fields: MappingField[]): Draft => {
  const name = application.display_name ?? application.template.name
  const bindings = { ...application.input_bindings }
  return { applicationId: application.id, name, bindings, baseline: fingerprint(name, bindings), source: sourceFingerprint(application, fields) }
}

/** An omitted value requests a system sample; an explicitly empty value must render empty. */
export function mappingSampleValues(inputs: TemplateInputSpec[], fields: MappingField[], bindings: TemplateBindings, samples: Record<string, string>): Record<string, string> {
  const fieldById = new Map(fields.map((field) => [field.id, field]))
  return Object.fromEntries(inputs.flatMap((input) => {
    const target = Object.hasOwn(bindings, input.key) ? bindings[input.key] : null
    const field = target ? fieldById.get(target) : undefined
    if (!field || field.field_type !== input.type) return [[input.key, '']]
    if (Object.hasOwn(samples, field.id)) return [[input.key, samples[field.id]]]
    if (input.type === 'image' || input.type === 'audio') return []
    return [[input.key, field.name]]
  }))
}

export function useTemplateMappingDraft(noteTypeId: string, applicationId: string) {
  const { t } = useTranslation('template_mapping')
  const client = useQueryClient()
  const active = useRef(true)
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  const detail = useQuery({ queryKey: ['note-type-detail', noteTypeId], enabled: Boolean(noteTypeId),
    queryFn: ({ signal }) => apiRequest<MappingNoteType>(`/api/note-types/${encodeURIComponent(noteTypeId)}`, { signal }) })
  const applications = useQuery({ queryKey: cardTemplateQueryKeys.applications(noteTypeId, true), enabled: Boolean(noteTypeId),
    queryFn: ({ signal }) => fetchTemplateApplications(noteTypeId, true, signal) })
  const application = applications.data?.items.find((item) => item.id === applicationId)
  const fields = useMemo(() => detail.data?.field_defs ?? [], [detail.data])
  const [draft, setDraft] = useState<Draft | null>(null)
  const [samples, setSamples] = useState<Record<string, string>>({})
  const [preview, setPreview] = useState<{ key: string; data?: TemplateLibraryPreview; error?: string } | null>(null)
  useEffect(() => {
    if (!application || !detail.data) return
    setDraft((old) => old?.applicationId === application.id && fingerprint(old.name, old.bindings) !== old.baseline
      ? old : fromApplication(application, detail.data.field_defs))
  }, [application, detail.data])
  const current = draft?.applicationId === applicationId ? draft : null
  const dirty = Boolean(current && fingerprint(current.name, current.bindings) !== current.baseline)
  const issues = application && current ? validateBindings(application.input_schema, fields, current.bindings) : []
  const invalid = !application || !current || application.status_code !== 'ACTIVE' || issues.some((issue) => issue.blocking)
    || !current.name.trim() || current.name.trim().length > 255
  const sourceChanged = Boolean(current && application && current.source !== sourceFingerprint(application, fields))

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!current || invalid) throw new Error(t('needs_repair'))
      const captured = { name: current.name.trim(), input_bindings: { ...current.bindings } }
      const [fresh, freshDetail] = await Promise.all([
        client.fetchQuery({ queryKey: cardTemplateQueryKeys.applications(noteTypeId, true), queryFn: ({ signal }) => fetchTemplateApplications(noteTypeId, true, signal), staleTime: 0 }),
        client.fetchQuery({ queryKey: ['note-type-detail', noteTypeId], queryFn: ({ signal }) => apiRequest<MappingNoteType>(`/api/note-types/${encodeURIComponent(noteTypeId)}`, { signal }), staleTime: 0 }),
      ])
      const latest = fresh.items.find((item) => item.id === applicationId)
      if (!latest || latest.status_code !== 'ACTIVE') throw new Error(t('retired_notice'))
      if (validateBindings(latest.input_schema, freshDetail.field_defs, captured.input_bindings).some((issue) => issue.blocking)) throw new Error(t('source_changed'))
      const result = await updateTemplateApplication(noteTypeId, applicationId, { input_bindings: captured.input_bindings, display_name: captured.name })
      if (result.id !== applicationId || result.note_type_id !== noteTypeId || result.template_id !== latest.template_id) throw new Error(t('not_found'))
      return { result, fields: freshDetail.field_defs }
    },
    onSuccess: async ({ result, fields: latestFields }) => {
      if (active.current) { setDraft(fromApplication(result, latestFields)); toast.success(t('saved')) }
      await Promise.all([
        client.invalidateQueries({ queryKey: ['card-template'] }),
        client.invalidateQueries({ queryKey: ['note-type-detail', noteTypeId] }),
      ])
    },
  })
  const bindings = current?.bindings
  const previewBody = useMemo(() => application && bindings ? {
    front_html: application.template.front_html, back_html: application.template.back_html, shared_css: application.template.shared_css,
    input_schema: application.input_schema, sample_values: mappingSampleValues(application.input_schema, fields, bindings, samples),
  } : null, [application, bindings, fields, samples])
  const previewKey = previewBody ? JSON.stringify([application?.template_id, previewBody]) : ''
  const templateId = application?.template_id
  useEffect(() => {
    if (!previewBody || !templateId) return
    const controller = new AbortController()
    let cancelled = false
    const timer = window.setTimeout(() => {
      void previewLibraryTemplate(templateId, previewBody, controller.signal).then((data) => {
        if (!cancelled) setPreview({ key: previewKey, data })
      }).catch((error: unknown) => {
        if (!cancelled) setPreview({ key: previewKey, error: error instanceof Error ? error.message : t('retry') })
      })
    }, 400)
    return () => { cancelled = true; controller.abort(); window.clearTimeout(timer) }
  }, [templateId, previewBody, previewKey, t])
  return {
    detail, applications, application, fields, draft: current, dirty, issues, invalid, sourceChanged, saveMutation,
    updateName: (name: string) => { saveMutation.reset(); setDraft((old) => old ? { ...old, name } : old) },
    updateBindings: (bindings: TemplateBindings) => { saveMutation.reset(); setDraft((old) => old ? { ...old, bindings } : old) },
    samples, setSample: (fieldId: string, value: string) => setSamples((old) => ({ ...old, [fieldId]: value })), resetSamples: () => setSamples({}),
    preview: preview?.key === previewKey ? preview.data : undefined,
    previewError: preview?.key === previewKey ? preview.error : undefined,
    isPreviewLoading: Boolean(previewBody && preview?.key !== previewKey),
  }
}
