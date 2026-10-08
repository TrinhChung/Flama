import { useEffect, useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import {
  cardTemplateQueryKeys,
  fetchNoteTypeTemplates,
} from '@/entities/card-template'
import { templateErrorMessage } from '../lib/templateErrors'

export type FieldDefItem = {
  id: string
  name: string
  field_type: string
  position: number
}

export type TemplateItem = {
  id: string
  name: string
  front_html?: string
  back_html?: string
  shared_css?: string
  is_default?: boolean
}

export type NoteTypeDetail = {
  id: string
  name: string
  publish_status?: string
  field_defs?: FieldDefItem[]
  templates?: TemplateItem[]
}

export type PreviewResponse = {
  front_html?: string
  back_html?: string
  front_renderer_payload?: unknown
  back_renderer_payload?: unknown
}

export function useNoteTypeDetail() {
  const { t } = useTranslation('note_types')
  const { id: noteTypeId } = useParams<{ id: string }>()
  const queryClient = useQueryClient()

  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'front' | 'back' | 'css'>('front')

  const [frontHtml, setFrontHtml] = useState('')
  const [backHtml, setBackHtml] = useState('')
  const [sharedCss, setSharedCss] = useState('')

  const [previewResult, setPreviewResult] = useState<PreviewResponse | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)

  const detailQuery = useQuery({
    queryKey: ['note-type-detail', noteTypeId],
    queryFn: () => appApi.get<NoteTypeDetail>(`/note-types/${noteTypeId}`),
    enabled: Boolean(noteTypeId),
  })

  const templatesWithCountsQuery = useQuery({
    queryKey: cardTemplateQueryKeys.noteTypeTemplates(noteTypeId ?? ''),
    queryFn: ({ signal }) => fetchNoteTypeTemplates(noteTypeId as string, signal),
    enabled: Boolean(noteTypeId),
  })

  const noteType = detailQuery.data
  const templates = useMemo(() => noteType?.templates || [], [noteType?.templates])
  const fields = (noteType?.field_defs || []).slice().sort((a, b) => a.position - b.position)

  const selectedTemplate = useMemo(() => {
    return templates.find((t) => t.id === selectedTemplateId) || templates[0] || null
  }, [templates, selectedTemplateId])

  const selectedNoteCount =
    templatesWithCountsQuery.data?.items.find((item) => item.id === selectedTemplate?.id)?.note_count ?? null

  const invalidateTemplates = () => {
    void queryClient.invalidateQueries({ queryKey: ['note-type-detail', noteTypeId] })
    void queryClient.invalidateQueries({
      queryKey: cardTemplateQueryKeys.noteTypeTemplates(noteTypeId ?? ''),
    })
  }

  // Auto select initial template
  useEffect(() => {
    if (templates.length && !selectedTemplateId) {
      setSelectedTemplateId(templates[0].id)
    }
  }, [templates, selectedTemplateId])

  // Sync on template identity/content changes, preserving drafts on metadata-only refetches.
  const editorTemplateId = selectedTemplate?.id
  const frontHtmlVal = selectedTemplate?.front_html
  const backHtmlVal = selectedTemplate?.back_html
  const sharedCssVal = selectedTemplate?.shared_css
  useEffect(() => {
    if (editorTemplateId) {
      setFrontHtml(frontHtmlVal || '')
      setBackHtml(backHtmlVal || '')
      setSharedCss(sharedCssVal || '')
    }
  }, [editorTemplateId, frontHtmlVal, backHtmlVal, sharedCssVal])

  // Save Template Mutation
  const saveMutation = useMutation({
    mutationFn: (payload: { front_html: string; back_html: string; shared_css: string }) =>
      appApi.mutate(`/note-types/${noteTypeId}/templates/${selectedTemplateId}`, 'PATCH', payload),
    onSuccess: () => {
      toast.success(t('detail.messages.save_success'))
      invalidateTemplates()
    },
    onError: (error: unknown) => {
      toast.error(t('detail.messages.save_error'), { description: templateErrorMessage(error) })
    },
  })

  // Create New Template Mutation
  const createTemplateMutation = useMutation({
    mutationFn: () =>
      appApi.mutate<TemplateItem>(`/note-types/${noteTypeId}/templates`, 'POST', {
        name: `Card ${templates.length + 1}`,
      }),
    onSuccess: (created) => {
      toast.success(t('detail.messages.create_success'))
      setSelectedTemplateId(created.id)
      invalidateTemplates()
    },
    onError: (error: unknown) => {
      toast.error(t('detail.messages.create_error'), { description: templateErrorMessage(error) })
    },
  })

  // Reset Template Mutation
  const resetTemplateMutation = useMutation({
    mutationFn: () =>
      appApi.mutate<TemplateItem>(
        `/note-types/${noteTypeId}/templates/${selectedTemplateId}/reset`,
        'POST',
      ),
    onSuccess: (reset) => {
      toast.success(t('detail.messages.reset_success'))
      setFrontHtml(reset.front_html || '')
      setBackHtml(reset.back_html || '')
      setSharedCss(reset.shared_css || '')
      invalidateTemplates()
    },
    onError: (error: unknown) => {
      toast.error(t('detail.messages.reset_error'), { description: templateErrorMessage(error) })
    },
  })

  // Live Preview Fetcher
  useEffect(() => {
    if (!noteTypeId || !selectedTemplateId) return
    let cancelled = false
    const timer = setTimeout(async () => {
      setIsPreviewLoading(true)
      setPreviewError(null)
      try {
        const res = await appApi.mutate<PreviewResponse>(
          `/note-types/${noteTypeId}/templates/${selectedTemplateId}/preview`,
          'POST',
          {
            front_html: frontHtml,
            back_html: backHtml,
            shared_css: sharedCss,
            use_sample_data: true,
          },
        )
        if (!cancelled) {
          setPreviewResult(res)
        }
      } catch {
        if (!cancelled) {
          setPreviewResult(null)
          setPreviewError(t('live_preview.error'))
        }
      } finally {
        if (!cancelled) {
          setIsPreviewLoading(false)
        }
      }
    }, 500)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [noteTypeId, selectedTemplateId, frontHtml, backHtml, sharedCss, t])

  return {
    noteTypeId,
    detailQuery,
    templatesWithCountsQuery,
    noteType,
    templates,
    fields,
    selectedTemplate,
    selectedNoteCount,
    selectedTemplateId,
    setSelectedTemplateId,
    activeTab,
    setActiveTab,
    frontHtml,
    setFrontHtml,
    backHtml,
    setBackHtml,
    sharedCss,
    setSharedCss,
    previewResult,
    previewError,
    isPreviewLoading,
    saveMutation,
    createTemplateMutation,
    resetTemplateMutation,
    invalidateTemplates,
  }
}
