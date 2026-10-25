import '@/shared/config/i18n'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { ApiError } from '@/shared/api/client'
import {
  archiveLibraryTemplate, cardTemplateQueryKeys, deleteLibraryTemplate, fetchLibraryTemplate, previewLibraryTemplate, templateSampleValues, updateLibraryTemplate, useTemplateSamples,
  type CardTemplateItem, type TemplateInputSpec, type TemplateLibraryDetail, type TemplateLibraryPreview,
  type TemplateLibraryTemplate, type TemplateWriteBody,
} from '@/entities/card-template'
import { inputSchemaIssues } from '../lib/inputSchemaValidation'

export type TemplateLibraryDraft = {
  name: string
  description: string
  primary_category: string
  front_html: string
  back_html: string
  shared_css: string
  input_schema: TemplateInputSpec[]
}
const toDraft = (template: TemplateLibraryTemplate): TemplateLibraryDraft => ({
  name: template.name, description: template.description, primary_category: template.primary_category ?? '',
  front_html: template.front_html, back_html: template.back_html, shared_css: template.shared_css,
  input_schema: template.input_schema.map((input) => ({ ...input })),
})
type EditorState = { id: string; draft: TemplateLibraryDraft; baseline: TemplateLibraryDraft; head: string | null }
const fromTemplate = (template: TemplateLibraryTemplate): EditorState => ({ id: template.id, draft: toDraft(template), baseline: toDraft(template), head: template.current_version_id })
const isDirty = (state: EditorState) => JSON.stringify(state.draft) !== JSON.stringify(state.baseline)
const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'Đã có lỗi xảy ra. Vui lòng thử lại.'

export function useTemplateLibraryEditor(id: string) {
  const { t } = useTranslation('card_templates')
  const client = useQueryClient()
  const identity = useRef({ id, generation: 0, mounted: true })
  if (identity.current.id !== id) identity.current = { id, generation: identity.current.generation + 1, mounted: true }
  useEffect(() => { identity.current.mounted = true; return () => { identity.current.mounted = false } }, [])
  const capture = () => ({ id, generation: identity.current.generation })
  const stillCurrent = (request: { id: string; generation: number }) => identity.current.mounted && request.id === identity.current.id && request.generation === identity.current.generation
  const detailQuery = useQuery({ queryKey: cardTemplateQueryKeys.libraryDetail(id), queryFn: ({ signal }) => fetchLibraryTemplate(id, signal), enabled: Boolean(id) })
  const [state, setState] = useState<EditorState | null>(null)
  const [replacingId, setReplacingId] = useState<string | null>(null)
  const [reloadError, setReloadError] = useState<{ id: string; message: string } | null>(null)
  const [saveError, setSaveError] = useState<{ id: string; message: string; stale: boolean } | null>(null)
  useEffect(() => { setState(null) }, [id])
  useEffect(() => {
    const data = detailQuery.data
    if (data?.id !== id) return
    setState((old) => old?.id === id && isDirty(old) ? old : fromTemplate(data))
  }, [id, detailQuery.data])
  useEffect(() => { setReloadError(null); setSaveError(null) }, [id])
  const current = state?.id === id ? state : null
  const draft = current?.draft ?? null
  const dirty = current ? isDirty(current) : false
  const schemaIssues = draft ? inputSchemaIssues(draft.input_schema) : []
  const samples = useTemplateSamples(id, draft?.input_schema.map((input) => ({ key: input.key, type: input.type })) ?? [])
  const sampleValues = samples.values

  const invalidate = async (usages = detailQuery.data?.applications ?? []) => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['card-template'] }),
      ...[...new Set(usages.map((application) => application.note_type_id))].map((noteTypeId) => client.invalidateQueries({ queryKey: ['note-type-detail', noteTypeId] })),
    ])
  }
  const saveMutation = useMutation({
    mutationFn: (request: { id: string; generation: number; body: TemplateWriteBody }) => updateLibraryTemplate(request.id, request.body),
    onSuccess: async (template, request) => {
      if (!stillCurrent(request)) return
      setState(fromTemplate(template)); setSaveError(null)
      client.setQueryData<TemplateLibraryDetail>(cardTemplateQueryKeys.libraryDetail(request.id), (old) => old && ({ ...old, ...template }))
      toast.success(t('editor.toast_saved'))
      await invalidate()
    },
    onError: (error, request) => {
      if (!stillCurrent(request)) return
      const stale = error instanceof ApiError && (error.status === 409 || error.code === 'TEMPLATE_VERSION_STALE')
      setSaveError({ id: request.id, stale, message: stale ? t('editor.stale_error') : errorMessage(error) })
    },
  })
  const archiveMutation = useMutation({
    mutationFn: (request: { id: string; generation: number; archived: boolean }) => archiveLibraryTemplate(request.id, request.archived),
    onSuccess: async (template, request) => {
      if (!stillCurrent(request)) return
      client.setQueryData<TemplateLibraryDetail>(cardTemplateQueryKeys.libraryDetail(request.id), (old) => old && ({ ...old, ...template }))
      await invalidate()
    },
    onError: (error, request) => { if (stillCurrent(request)) toast.error(t('editor.archive_error_title'), { description: errorMessage(error) }) },
  })
  const deleteMutation = useMutation({
    mutationFn: (request: { id: string; generation: number }) => deleteLibraryTemplate(request.id),
    onSuccess: async (_data, request) => {
      if (!stillCurrent(request)) return
      toast.success(t('detail.delete_success'))
      await invalidate()
    },
    onError: (error, request) => {
      if (stillCurrent(request)) toast.error(errorMessage(error))
    },
  })

  // Restore/distribution responses have intentionally different DTOs. Replace explicit
  // sources first, then fetch the full library schema and metadata with a fresh request.
  const refreshAndReplaceDraft = useCallback(async (restored?: CardTemplateItem) => {
    const request = { id, generation: identity.current.generation }
    if (restored && restored.id !== id) return
    setReplacingId(id); setReloadError(null)
    if (restored) setState((old) => old?.id === id ? { ...old, head: restored.current_version_id ?? null, draft: { ...old.draft, front_html: restored.front_html, back_html: restored.back_html, shared_css: restored.shared_css } } : old)
    try {
      const key = cardTemplateQueryKeys.libraryDetail(id)
      await client.cancelQueries({ queryKey: key, exact: true })
      const fresh = await client.fetchQuery({ queryKey: key, queryFn: ({ signal }) => fetchLibraryTemplate(id, signal), staleTime: 0 })
      if (!stillCurrent(request)) return
      setState(fromTemplate(fresh)); setSaveError(null)
      await invalidate(fresh.applications)
    } catch (error) {
      if (stillCurrent(request)) setReloadError({ id, message: errorMessage(error) })
      throw error
    } finally { if (stillCurrent(request)) setReplacingId(null) }
  // identity generation and request checks are intentionally evaluated on invocation.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, client])

  const [preview, setPreview] = useState<{ key: string; data: TemplateLibraryPreview | null; error: string | null; loading: boolean } | null>(null)
  const previewBody = draft ? { front_html: draft.front_html, back_html: draft.back_html, shared_css: draft.shared_css, input_schema: draft.input_schema,
    sample_values: templateSampleValues(draft.input_schema.map((input) => ({ key: input.key, type: input.type })), sampleValues) } : null
  const previewKey = JSON.stringify([id, previewBody])
  useEffect(() => {
    if (!previewBody || schemaIssues.length) return
    const controller = new AbortController()
    let active = true
    const timer = setTimeout(async () => {
      setPreview({ key: previewKey, data: null, error: null, loading: true })
      try {
        const data = await previewLibraryTemplate(id, previewBody, controller.signal)
        if (active) setPreview({ key: previewKey, data, error: null, loading: false })
      } catch (error) { if (active && !controller.signal.aborted) setPreview({ key: previewKey, data: null, error: errorMessage(error), loading: false }) }
    }, 500)
    return () => { active = false; clearTimeout(timer); controller.abort() }
  // previewKey includes exactly the preview source, schema and sample values.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, previewKey])

  const isReplacingDraft = replacingId === id
  const error = saveError?.id === id ? saveError : null
  const refreshError = reloadError?.id === id ? reloadError.message : null
  const canSave = Boolean(draft?.name.trim() && draft.name.trim().length <= 255 && draft.primary_category.length <= 120 && !schemaIssues.length && !saveMutation.isPending && !isReplacingDraft && !error?.stale && !refreshError)
  return {
    detailQuery, template: detailQuery.data?.id === id ? detailQuery.data : null, draft, dirty, schemaIssues,
    persistedInputKeys: current?.baseline.input_schema.map((input) => input.key) ?? [],
    resetSampleValues: samples.reset,
    sampleValues, setSampleValue: samples.setValue,
    updateDraft: (patch: Partial<TemplateLibraryDraft>) => setState((old) => old?.id === id && !isReplacingDraft ? { ...old, draft: { ...old.draft, ...patch } } : old),
    canSave, saveMutation, saveError: error?.message ?? null, isStale: error?.stale ?? false,
    save: () => { if (current && canSave) saveMutation.mutate({ ...capture(), body: { ...current.draft, name: current.draft.name.trim(), primary_category: current.draft.primary_category || null, expected_current_version_id: current.head } }) },
    saveAsync: async () => {
      if (!current || !canSave) throw new Error(error?.message ?? refreshError ?? t('editor.preview_schema_error'))
      await saveMutation.mutateAsync({ ...capture(), body: { ...current.draft, name: current.draft.name.trim(), primary_category: current.draft.primary_category || null, expected_current_version_id: current.head } })
    },
    archiveMutation, setArchived: (archived: boolean) => archiveMutation.mutate({ ...capture(), archived }),
    archive: (archived: boolean) => archiveMutation.mutateAsync({ ...capture(), archived }),
    deleteMutation,
    deleteTemplate: () => deleteMutation.mutateAsync({ ...capture() }),
    refreshAndReplaceDraft, isReplacingDraft, refreshError,
    previewResult: preview?.key === previewKey ? preview.data : null,
    previewError: schemaIssues.length ? t('editor.preview_schema_error') : preview?.key === previewKey ? preview.error : null,
    isPreviewLoading: Boolean(previewBody && !schemaIssues.length && (preview?.key !== previewKey || preview?.loading)),
  }
}
