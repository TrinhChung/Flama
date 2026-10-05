import { useEffect, useState, useMemo } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faArrowLeft,
  faArrowUpRightFromSquare,
  faCheck,
  faCircleCheck,
  faPlus,
  faRobot,
  faRotateLeft,
  faShareNodes,
  faSliders,
} from '@fortawesome/free-solid-svg-icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Button } from '@/components/ui/button'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { AmbientBackground } from '@/components/ambient-background'
import {
  cardTemplateQueryKeys,
  fetchNoteTypeTemplates,
  TemplateCodeEditor,
} from '@/entities/card-template'
import { NoteTypeLivePreview } from '../components/NoteTypeLivePreview'
import { TemplateManagementBar } from '../components/TemplateManagementBar'
import { templateErrorMessage } from '../lib/templateErrors'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'

type FieldDefItem = {
  id: string
  name: string
  field_type: string
  position: number
}

type TemplateItem = {
  id: string
  name: string
  front_html?: string
  back_html?: string
  shared_css?: string
  is_default?: boolean
}

type NoteTypeDetail = {
  id: string
  name: string
  publish_status?: string
  field_defs?: FieldDefItem[]
  templates?: TemplateItem[]
}

type PreviewResponse = {
  front_html?: string
  back_html?: string
  front_renderer_payload?: unknown
  back_renderer_payload?: unknown
}

export function NoteTypeDetailPage() {
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

  // Sync editor values when selected template changes
  const frontHtmlVal = selectedTemplate?.front_html
  const backHtmlVal = selectedTemplate?.back_html
  const sharedCssVal = selectedTemplate?.shared_css
  useEffect(() => {
    if (selectedTemplate) {
      setFrontHtml(frontHtmlVal || '')
      setBackHtml(backHtmlVal || '')
      setSharedCss(sharedCssVal || '')
    }
  }, [selectedTemplate, frontHtmlVal, backHtmlVal, sharedCssVal])

  // Save Template Mutation
  const saveMutation = useMutation({
    mutationFn: (payload: { front_html: string; back_html: string; shared_css: string }) =>
      appApi.mutate(`/note-types/${noteTypeId}/templates/${selectedTemplateId}`, 'PATCH', payload),
    onSuccess: () => {
      toast.success('Đã lưu Template.')
      invalidateTemplates()
    },
    onError: (error: unknown) => {
      toast.error('Không thể lưu Template', { description: templateErrorMessage(error) })
    },
  })

  // Create New Template Mutation
  const createTemplateMutation = useMutation({
    mutationFn: () =>
      appApi.mutate<TemplateItem>(`/note-types/${noteTypeId}/templates`, 'POST', {
        name: `Card ${templates.length + 1}`,
      }),
    onSuccess: (created) => {
      toast.success('Đã tạo Template mới.')
      setSelectedTemplateId(created.id)
      invalidateTemplates()
    },
    onError: (error: unknown) => {
      toast.error('Không thể tạo Template', { description: templateErrorMessage(error) })
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
      toast.success('Đã đặt lại Template mặc định.')
      setFrontHtml(reset.front_html || '')
      setBackHtml(reset.back_html || '')
      setSharedCss(reset.shared_css || '')
      invalidateTemplates()
    },
    onError: (error: unknown) => {
      toast.error('Không thể đặt lại Template', { description: templateErrorMessage(error) })
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
          setPreviewError('Lỗi tải xem trước template.')
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
  }, [noteTypeId, selectedTemplateId, frontHtml, backHtml, sharedCss])

  if (detailQuery.isPending) return <PageLoading label="Đang tải thông tin NoteType…" />
  if (detailQuery.error) return <Page><PageError error={detailQuery.error} /></Page>

  return (
    <Page className="w-full max-w-7xl px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-6">
      <AmbientBackground intensity="subtle" />

      {/* Standardized Flama PageHeader */}
      <PageHeader
        title={noteType?.name || 'Chi tiết Loại thẻ'}
        description="Tùy chỉnh mã Front HTML, Back HTML, CSS và kiểm tra trực tiếp hiệu ứng hiển thị."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-xl gap-1.5">
              <Link to="/flashcards/note-types">
                <FontAwesomeIcon icon={faArrowLeft} className="text-xs" /> Quay lại
              </Link>
            </Button>

            {noteType?.publish_status === 'published' || noteType?.publish_status === 'unlisted' ? (
              <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold border-emerald-500/40 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10 rounded-xl gap-1.5">
                <Link to={`/marketplace/note-types/${noteTypeId}`}>
                  <FontAwesomeIcon icon={faCircleCheck} className="text-emerald-500 text-xs" /> Xem trên Marketplace
                </Link>
              </Button>
            ) : (
              <Button size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-bold rounded-xl shadow-xs gap-1.5">
                <Link to={`/marketplace/note-types/publish?id=${noteTypeId}`}>
                  <FontAwesomeIcon icon={faShareNodes} className="text-xs" /> Chia sẻ lên Kho
                </Link>
              </Button>
            )}

            <Button
              variant="outline"
              size="sm"
              asChild
              className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-xl border-primary/30 text-primary hover:bg-primary/10 gap-1.5"
            >
              <Link to="/flashcards/note-types/guide" target="_blank" rel="noopener noreferrer">
                <FontAwesomeIcon icon={faRobot} className="text-primary text-xs" /> Hướng Dẫn & Prompt AI
                <FontAwesomeIcon icon={faArrowUpRightFromSquare} className="opacity-70 text-[10px]" />
              </Link>
            </Button>

            <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-xl gap-1.5">
              <Link to={`/flashcards/note-types/${noteTypeId}/fields`}>
                <FontAwesomeIcon icon={faSliders} className="text-xs" /> Quản lý Trường
              </Link>
            </Button>
          </div>
        }
      />

      <div className="grid gap-5 lg:grid-cols-12 items-stretch">
        {/* Left Column: Template Editor */}
        <div className="lg:col-span-6 flex flex-col">
          <TemplateManagementBar
            noteTypeId={noteTypeId ?? ''}
            template={
              selectedTemplate
                ? {
                    id: selectedTemplate.id,
                    name: selectedTemplate.name,
                    is_default: Boolean(selectedTemplate.is_default),
                  }
                : null
            }
            noteCount={selectedNoteCount}
            templateCount={templates.length}
            onRenamed={invalidateTemplates}
            onDeleted={(deletedId) => {
              // Chọn ngay template còn lại; không để selectedTemplateId trỏ template đã xóa.
              setSelectedTemplateId(templates.find((item) => item.id !== deletedId)?.id ?? null)
              invalidateTemplates()
            }}
          />

          <TemplateCodeEditor
            headerActions={
              <>
                <NativeSelect
                  value={selectedTemplateId || ''}
                  onChange={(e) => setSelectedTemplateId(e.target.value)}
                  className="h-8 sm:h-9 text-xs font-medium flex-1 sm:w-40 min-w-[120px] rounded-xl bg-background"
                >
                  {templates.map((tmpl) => (
                    <NativeSelectOption key={tmpl.id} value={tmpl.id}>
                      {tmpl.name}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>

                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 sm:h-9 px-2.5 text-xs font-semibold rounded-xl shrink-0 gap-1.5"
                  onClick={() => createTemplateMutation.mutate()}
                >
                  <FontAwesomeIcon icon={faPlus} className="text-xs" /> Mới
                </Button>

                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 sm:h-9 px-2.5 text-xs font-semibold text-destructive hover:bg-destructive/10 rounded-xl shrink-0 gap-1.5"
                  onClick={() => {
                    if (window.confirm('Khôi phục template về mặc định ban đầu?')) {
                      resetTemplateMutation.mutate()
                    }
                  }}
                  title="Đặt lại template mặc định"
                >
                  <FontAwesomeIcon icon={faRotateLeft} className="text-xs" /> Reset
                </Button>
              </>
            }
            fields={fields}
            activeTab={activeTab}
            onActiveTabChange={setActiveTab}
            frontHtml={frontHtml}
            backHtml={backHtml}
            sharedCss={sharedCss}
            onFrontHtmlChange={setFrontHtml}
            onBackHtmlChange={setBackHtml}
            onSharedCssChange={setSharedCss}
            footer={
              <Button
                size="sm"
                disabled={saveMutation.isPending}
                onClick={() =>
                  saveMutation.mutate({
                    front_html: frontHtml,
                    back_html: backHtml,
                    shared_css: sharedCss,
                  })
                }
                className="w-full sm:w-auto font-bold px-5 h-9 sm:h-10 text-xs sm:text-sm rounded-xl shadow-xs justify-center gap-1.5"
              >
                <FontAwesomeIcon icon={faCheck} className="text-xs" /> Lưu Template
              </Button>
            }
          />
        </div>

        {/* Right Column: Live Preview Frame */}
        <div className="lg:col-span-6 flex flex-col">
          <NoteTypeLivePreview
            cardId={`note-type-live-preview-${noteTypeId}`}
            side={activeTab === 'back' ? 'back' : 'front'}
            onSideChange={(s) => setActiveTab(s === 'back' ? 'back' : 'front')}
            frontPayload={previewResult?.front_renderer_payload}
            backPayload={previewResult?.back_renderer_payload}
            frontHtml={previewResult?.front_html}
            backHtml={previewResult?.back_html}
            scope="note_type_live_preview"
            scopeId={noteTypeId}
            fieldDefs={fields}
            isLoading={isPreviewLoading}
            error={previewError}
            title="Xem Trước Trực Tiếp (Live Preview)"
            subtitle="(Hiển thị mô phỏng dữ liệu thẻ mẫu)"
          />
        </div>
      </div>
    </Page>
  )
}
