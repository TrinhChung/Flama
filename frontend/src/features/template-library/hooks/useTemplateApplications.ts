import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  attachLibraryTemplate, deleteNoteTypeTemplate, fetchTemplateApplications, retireTemplateApplication, updateTemplateApplication,
  cardTemplateQueryKeys, type MappingField, type TemplateApplication,
} from '@/entities/card-template'
import { apiRequest } from '@/shared/api/client'
import type { TemplateApplicationsPanelProps } from '../model/templateApplications'

type ApplicationMutation = 'default' | 'retire' | 'reattach' | 'delete'

export function useTemplateApplications({ noteTypeId, fields, onChanged }: TemplateApplicationsPanelProps) {
  const { t } = useTranslation('card_templates')
  const queryClient = useQueryClient()
  const mounted = useRef(true)
  const submitting = useRef(false)
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])
  const applications = useQuery({
    queryKey: cardTemplateQueryKeys.applications(noteTypeId, true),
    queryFn: ({ signal }) => fetchTemplateApplications(noteTypeId, true, signal),
  })
  const detail = useQuery({
    queryKey: ['note-type-detail', noteTypeId, 'attachment-fields'],
    queryFn: ({ signal }) => apiRequest<{ field_defs: MappingField[] }>(`/api/note-types/${encodeURIComponent(noteTypeId)}`, { signal }),
    enabled: fields === undefined,
  })
  const execute = async (kind: ApplicationMutation, application: TemplateApplication): Promise<boolean> => {
    if (submitting.current) return false
    submitting.current = true
    setPendingId(application.id)
    setError(null)
    try {
      if (kind === 'delete') {
        await deleteNoteTypeTemplate(noteTypeId, application.template_id)
      } else {
        const result = kind === 'retire'
          ? await retireTemplateApplication(noteTypeId, application.id)
          : kind === 'default'
            ? await updateTemplateApplication(noteTypeId, application.id, { is_default: true })
            : await attachLibraryTemplate(noteTypeId, {
              template_id: application.template_id,
              occurrence_key: application.occurrence_key,
              input_bindings: application.input_bindings,
              display_name: application.display_name,
              position: application.position,
              is_default: application.is_default,
            })
        if (result.id !== application.id || result.template_id !== application.template_id) {
          throw new Error(t('applications_panel.error_mismatch'))
        }
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['card-template'] }),
        queryClient.invalidateQueries({ queryKey: ['note-type-detail', noteTypeId] }),
        queryClient.invalidateQueries({ queryKey: ['note-types'] }),
      ])
      if (!mounted.current) return false
      onChanged?.()
      return true
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause : new Error(t('applications_panel.error_failed')))
      return false
    } finally {
      submitting.current = false
      if (mounted.current) setPendingId(null)
    }
  }
  return { applications, detail, fields: fields ?? detail.data?.field_defs ?? [], pendingId, error, setError, execute }
}
