import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { attachLibraryTemplate, cardTemplateQueryKeys, fetchTemplateApplications, suggestBindings, validateBindings, type MappingIssue, type TemplateBindings } from '@/entities/card-template'
import { ApiError, apiRequest } from '@/shared/api/client'
import type { ApplyTemplateFormProps, AttachableNoteType } from '../model/applyTemplate'

export function useApplyTemplate({ template, initialNoteTypeId, onOpenChange, onApplied, onPendingChange }: ApplyTemplateFormProps) {
  const { t } = useTranslation('card_templates')
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const mounted = useRef(true)
  const initialized = useRef(false)
  const submitting = useRef(false)
  const [step, setStep] = useState<1 | 2>(initialNoteTypeId ? 2 : 1)
  const [selectedId, setSelectedId] = useState('')
  const [bindings, setBindings] = useState<TemplateBindings>({})
  const [displayName, setDisplayName] = useState(template.name)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const noteTypes = useQuery({
    queryKey: ['note-types', 'template-attachment'],
    queryFn: ({ signal }) => apiRequest<{ items: AttachableNoteType[] }>('/api/note-types?compact=true', { signal }),
  })
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])
  useEffect(() => {
    if (initialized.current || !noteTypes.data) return
    initialized.current = true
    const initial = noteTypes.data.items.find((item) => item.id === initialNoteTypeId)
    if (initial) {
      setSelectedId(initial.id)
      setBindings(suggestBindings(template.input_schema, initial.field_defs))
      setStep(2)
    }
  }, [noteTypes.data, initialNoteTypeId, template.input_schema])
  const selected = noteTypes.data?.items.find((item) => item.id === selectedId)
  const existingApplications = useQuery({
    queryKey: cardTemplateQueryKeys.applications(selectedId),
    queryFn: ({ signal }) => fetchTemplateApplications(selectedId, false, signal),
    enabled: Boolean(selectedId) && error instanceof ApiError && error.code === 'APPLICATION_EXISTS',
  })
  const issues = validateBindings(template.input_schema, selected?.field_defs ?? [], bindings)
  if (error instanceof ApiError && template.input_schema.some((input) => input.key === error.field)) {
    const key = error.field!
    const fieldId = Object.hasOwn(bindings, key) ? bindings[key] ?? '' : ''
    const serverIssue: MappingIssue | null = error.code === 'FIELD_OUT_OF_SCOPE'
      ? { kind: 'field_out_of_scope', key, fieldId, blocking: true }
      : error.code === 'INPUT_TYPE_MISMATCH'
        ? { kind: 'type_mismatch', key, fieldId, blocking: false }
        : error.code === 'INPUT_NOT_FOUND' ? { kind: 'unknown_input', key, blocking: true } : null
    if (serverIssue && !issues.some((issue) => issue.key === key && issue.kind === serverIssue.kind)) issues.push(serverIssue)
  }
  const invalid = !selected || issues.some((issue) => issue.blocking)
    || !displayName.trim() || displayName.length > 255
    || Boolean(template.archived_at)
  const selectNoteType = (id: string) => {
    const next = noteTypes.data?.items.find((item) => item.id === id)
    setSelectedId(id)
    setBindings(suggestBindings(template.input_schema, next?.field_defs ?? []))
    setError(null)
  }
  const submit = async () => {
    if (invalid || submitting.current || !selected) return
    submitting.current = true
    setPending(true)
    onPendingChange?.(true)
    setError(null)
    const noteTypeId = selected.id
    try {
      const application = await attachLibraryTemplate(noteTypeId, {
        template_id: template.id,
        occurrence_key: 'compat',
        display_name: displayName,
        input_bindings: bindings,
      })
      if (application.template_id !== template.id) throw new Error(t('apply_wizard.error_mismatch'))
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['card-template'] }),
        queryClient.invalidateQueries({ queryKey: ['note-type-detail', noteTypeId] }),
        queryClient.invalidateQueries({ queryKey: ['note-types'] }),
      ])
      if (!mounted.current) return
      toast.success(t('apply_wizard.toast_success'), {
        action: { label: t('apply_wizard.toast_action_open'), onClick: () => navigate(`/flashcards/note-types/${encodeURIComponent(noteTypeId)}/templates/${encodeURIComponent(application.id)}`) },
      })
      onApplied?.(application)
      onOpenChange(false)
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause : new Error(t('apply_wizard.error_failed')))
    } finally {
      submitting.current = false
      if (mounted.current) {
        setPending(false)
        onPendingChange?.(false)
      }
    }
  }
  return { noteTypes, step, setStep, selected, selectedId, selectNoteType, bindings,
    setBindings: (next: TemplateBindings) => { setBindings(next); setError(null) },
    displayName, setDisplayName, pending, error, issues, invalid, submit, existingApplications }
}

export function useApplyTemplateDialog(open: boolean) {
  const [pending, setPending] = useState(false)
  useEffect(() => { if (!open) setPending(false) }, [open])
  return { pending, setPending }
}
