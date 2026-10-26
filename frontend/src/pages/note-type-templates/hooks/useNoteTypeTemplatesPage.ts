import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { cardTemplateQueryKeys, fetchTemplateApplications } from '@/entities/card-template'
import type { MappingNoteType } from '@/features/note-types'
import { apiRequest } from '@/shared/api/client'

export function useNoteTypeTemplatesPage(noteTypeId: string) {
  const [attachOpen, setAttachOpen] = useState(false)
  const detail = useQuery({ queryKey: ['note-type-detail', noteTypeId], enabled: Boolean(noteTypeId),
    queryFn: ({ signal }) => apiRequest<MappingNoteType>(`/api/note-types/${encodeURIComponent(noteTypeId)}`, { signal }) })
  const applications = useQuery({ queryKey: cardTemplateQueryKeys.applications(noteTypeId, true), enabled: Boolean(noteTypeId),
    queryFn: ({ signal }) => fetchTemplateApplications(noteTypeId, true, signal) })

  return { detail, applications, attachOpen, setAttachOpen }
}
