import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { inputSchemaPreviewFields } from '@/entities/card-template'
import { useUnsavedChangesGuard } from '@/shared/hooks/useUnsavedChangesGuard'
import { useTemplateMappingDraft } from './useTemplateMappingDraft'

export function useTemplateMappingWorkspace(noteTypeId: string, applicationId: string) {
  const { t } = useTranslation('template_mapping')
  const navigate = useNavigate()
  const state = useTemplateMappingDraft(noteTypeId, applicationId)
  const [samplesOpen, setSamplesOpen] = useState(false)
  const [side, setSide] = useState<'front' | 'back'>('front')
  const previewFields = useMemo(() => inputSchemaPreviewFields(state.application?.input_schema ?? [], state.sampleFieldTypes), [state.application?.input_schema, state.sampleFieldTypes])
  const { confirmDialog, requestNavigation } = useUnsavedChangesGuard(state.dirty, t('discard_message'), {
    onSave: async () => {
      if (state.saveMutation.isPending) throw new Error(t('saving'))
      await state.saveMutation.mutateAsync()
    },
  })
  const { application, draft } = state
  const effectiveId = application?.id ?? applicationId

  useEffect(() => {
    if (application?.id && application.id !== applicationId) {
      window.history.replaceState(null, '', `/flashcards/note-types/${encodeURIComponent(noteTypeId)}/templates/${encodeURIComponent(application.id)}`)
    }
  }, [application?.id, applicationId, noteTypeId])

  const listPath = `/flashcards/note-types/${encodeURIComponent(noteTypeId)}/templates`
  const mappingPath = `${listPath}/${encodeURIComponent(effectiveId)}`
  const pending = state.saveMutation.isPending
  const handleNavigate = (to: string) => { if (!pending) requestNavigation(() => navigate(to)) }
  return { t, state, samplesOpen, setSamplesOpen, side, setSide, previewFields, confirmDialog, listPath, mappingPath, effectiveId, application, draft, pending, handleNavigate }
}
