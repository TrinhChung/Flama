import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { apiRequest } from '@/shared/api/client'
import {
  cardTemplateQueryKeys, defaultTemplateSample, fetchTemplateApplications, previewLibraryTemplate, previewSampleValue, updateTemplateApplication, useTemplateSamples, validateBindings,
  type MappingField, type TemplateApplication, type TemplateBindings, type TemplateInputSpec, type TemplateLibraryPreview, type TemplatePreviewBody, type TemplateSampleValues,
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
export function mappingSampleValues(inputs: TemplateInputSpec[], fields: MappingField[], bindings: TemplateBindings, samples: TemplateSampleValues): NonNullable<TemplatePreviewBody['sample_values']> {
  const fieldById = new Map(fields.map((field) => [field.id, field]))
  return Object.fromEntries(inputs.flatMap((input): Array<[string, ReturnType<typeof previewSampleValue>]> => {
    const target = Object.hasOwn(bindings, input.key) ? bindings[input.key] : null
    const field = target ? fieldById.get(target) : undefined
    if (!field) return [[input.key, '']]
    if (Object.hasOwn(samples, field.id)) return [[input.key, previewSampleValue(samples[field.id], field.field_type)]]
    return [[input.key, defaultTemplateSample(field.field_type)]]
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
  const application = useMemo(() => {
    const items = applications.data?.items
    if (!items || !applicationId) return undefined

    const exact = items.find((item) => item.id === applicationId)
    if (exact) return exact

    const byTemplate = items.find((item) => item.template_id === applicationId)
    if (byTemplate) return byTemplate

    const appMatch = applicationId.match(/:application:([^:]+)/)?.[1]
    if (appMatch) {
      const byApp = items.find((item) => item.id === appMatch)
      if (byApp) return byApp
    }

    const tmplMatch = applicationId.match(/:template:([^:]+)/)?.[1]
    if (tmplMatch) {
      const byTmpl = items.find((item) => item.template_id === tmplMatch)
      if (byTmpl) return byTmpl
    }

    return undefined
  }, [applications.data?.items, applicationId])

  const effectiveApplicationId = application?.id ?? applicationId
  const fields = useMemo(() => detail.data?.field_defs ?? [], [detail.data])
  const [draft, setDraft] = useState<Draft | null>(null)
  const sampleState = useTemplateSamples(`${noteTypeId}:${effectiveApplicationId}`, fields.map((field) => ({ key: field.id, type: field.field_type })))
  const samples = sampleState.values
  const [preview, setPreview] = useState<{ key: string; data?: TemplateLibraryPreview; error?: string } | null>(null)
  useEffect(() => {
    if (!application || !detail.data) return
    setDraft((old) => old?.applicationId === application.id && fingerprint(old.name, old.bindings) !== old.baseline
      ? old : fromApplication(application, detail.data.field_defs))
  }, [application, detail.data])
  const current = draft?.applicationId === effectiveApplicationId ? draft : null
  const dirty = Boolean(current && fingerprint(current.name, current.bindings) !== current.baseline)
  const issues = application && current ? validateBindings(application.input_schema, fields, current.bindings) : []
  const invalid = !application || !current || application.status_code !== 'ACTIVE' || issues.some((issue) => issue.blocking)
    || !current.name.trim() || current.name.trim().length > 255
  const sourceChanged = Boolean(current && application && current.source !== sourceFingerprint(application, fields))

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!current || invalid) throw new Error(t('needs_repair'))
      const captured = { name: current.name.trim(), input_bindings: { ...current.bindings } }
      const result = await updateTemplateApplication(noteTypeId, effectiveApplicationId, { input_bindings: captured.input_bindings, display_name: captured.name })
      if (result.id !== effectiveApplicationId || result.note_type_id !== noteTypeId) throw new Error(t('not_found'))
      return { result, fields }
    },
    onSuccess: async ({ result, fields: latestFields }) => {
      if (active.current) { setDraft(fromApplication(result, latestFields)); toast.success(t('saved')) }
      client.setQueryData(cardTemplateQueryKeys.applications(noteTypeId, true), (old: { schema_version: string; items: TemplateApplication[] } | undefined) => {
        if (!old) return old
        return { ...old, items: old.items.map((item) => (item.id === result.id ? result : item)) }
      })
      await Promise.all([
        client.invalidateQueries({ queryKey: ['card-template'] }),
        client.invalidateQueries({ queryKey: ['note-type-detail', noteTypeId] }),
      ])
    },
  })
  const bindings = current?.bindings
  const sampleFieldTypes = useMemo(() => Object.fromEntries((application?.input_schema ?? []).flatMap((input) => {
    const target = bindings && Object.hasOwn(bindings, input.key) ? bindings[input.key] : null
    const field = fields.find((item) => item.id === target)
    return field ? [[input.key, field.field_type]] : []
  })), [application?.input_schema, bindings, fields])
  const previewBody = useMemo(() => application && bindings ? {
    front_html: application.template.front_html, back_html: application.template.back_html, shared_css: application.template.shared_css,
    input_schema: application.input_schema, sample_values: mappingSampleValues(application.input_schema, fields, bindings, samples),
    sample_field_types: sampleFieldTypes,
  } : null, [application, bindings, fields, samples, sampleFieldTypes])
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
    detail, applications, application, fields, draft: current, dirty, issues, invalid, sourceChanged, saveMutation, sampleFieldTypes,
    updateName: (name: string) => { saveMutation.reset(); setDraft((old) => old ? { ...old, name } : old) },
    updateBindings: (bindings: TemplateBindings) => { saveMutation.reset(); setDraft((old) => old ? { ...old, bindings } : old) },
    samples, setSample: sampleState.setValue, resetSamples: sampleState.reset,
    preview: preview?.key === previewKey ? preview.data : undefined,
    previewError: preview?.key === previewKey ? preview.error : undefined,
    isPreviewLoading: Boolean(previewBody && preview?.key !== previewKey),
  }
}
