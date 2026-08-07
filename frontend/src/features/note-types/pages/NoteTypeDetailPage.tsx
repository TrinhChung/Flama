import { useEffect, useRef, useState } from 'react'
import {
  ArrowLeft,
  Check,
  CheckCircle,
  Plus,
  RotateCcw,
  Share2,
  SlidersHorizontal,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { NoteTypeLivePreview } from '../components/NoteTypeLivePreview'
import { Page } from '@/shared/components/Page'
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

  const activeTextareaRef = useRef<HTMLTextAreaElement | null>(null)

  const detailQuery = useQuery({
    queryKey: ['note-type-detail', noteTypeId],
    queryFn: () => appApi.get<NoteTypeDetail>(`/note-types/${noteTypeId}`),
    enabled: Boolean(noteTypeId),
  })

  const noteType = detailQuery.data
  const templates = noteType?.templates || []
  const fields = (noteType?.field_defs || []).slice().sort((a, b) => a.position - b.position)

  const selectedTemplate = templates.find((t) => t.id === selectedTemplateId) || templates[0] || null

  // Auto select initial template
  useEffect(() => {
    if (templates.length && !selectedTemplateId) {
      setSelectedTemplateId(templates[0].id)
    }
  }, [templates, selectedTemplateId])

  // Sync editor values when selected template changes
  useEffect(() => {
    if (selectedTemplate) {
      setFrontHtml(selectedTemplate.front_html || '')
      setBackHtml(selectedTemplate.back_html || '')
      setSharedCss(selectedTemplate.shared_css || '')
    }
  }, [selectedTemplate?.id])

  // Save Template Mutation
  const saveMutation = useMutation({
    mutationFn: (payload: { front_html: string; back_html: string; shared_css: string }) =>
      appApi.mutate(`/note-types/${noteTypeId}/templates/${selectedTemplateId}`, 'PATCH', payload),
    onSuccess: () => {
      toast.success('Đã lưu Template.')
      void queryClient.invalidateQueries({ queryKey: ['note-type-detail', noteTypeId] })
    },
    onError: (error: Error) => {
      toast.error('Không thể lưu Template', { description: error.message })
    },
  })

  // Create New Template Mutation
  const createTemplateMutation = useMutation({
    mutationFn: () =>
      appApi.mutate<TemplateItem>(`/note-types/${noteTypeId}/templates`, 'POST', {
        name: `Card ${templates.length + 1}`,
        front_html: '{{Word}}',
        back_html: '{{Word}}',
      }),
    onSuccess: (created) => {
      toast.success('Đã tạo Template mới.')
      setSelectedTemplateId(created.id)
      void queryClient.invalidateQueries({ queryKey: ['note-type-detail', noteTypeId] })
    },
    onError: (error: Error) => {
      toast.error('Không thể tạo Template', { description: error.message })
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
      void queryClient.invalidateQueries({ queryKey: ['note-type-detail', noteTypeId] })
    },
    onError: (error: Error) => {
      toast.error('Không thể đặt lại Template', { description: error.message })
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

  // Placeholder Toolbar Click Handler
  const insertPlaceholder = (fieldName: string) => {
    const placeholder = `{{${fieldName}}}`
    const textarea = activeTextareaRef.current

    if (activeTab === 'front') {
      if (textarea) {
        const start = textarea.selectionStart || 0
        const end = textarea.selectionEnd || 0
        setFrontHtml((prev) => prev.slice(0, start) + placeholder + prev.slice(end))
      } else {
        setFrontHtml((prev) => prev + placeholder)
      }
    } else if (activeTab === 'back') {
      if (textarea) {
        const start = textarea.selectionStart || 0
        const end = textarea.selectionEnd || 0
        setBackHtml((prev) => prev.slice(0, start) + placeholder + prev.slice(end))
      } else {
        setBackHtml((prev) => prev + placeholder)
      }
    } else {
      setSharedCss((prev) => prev + `/* ${placeholder} */`)
    }
  }

  if (detailQuery.isPending) return <PageLoading label="Đang tải thông tin NoteType…" />
  if (detailQuery.error) return <Page><PageError error={detailQuery.error} /></Page>

  return (
    <Page className="w-full max-w-none px-4 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-4 sm:space-y-5">
      {/* Top Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-2 sm:mb-3">
        <div className="min-w-0">
          <h2 className="text-lg sm:text-xl font-bold tracking-tight text-foreground truncate">
            {noteType?.name || 'NoteType Detail'}
          </h2>
          <span className="text-xs text-muted-foreground">Field + template management</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-lg">
            <Link to="/flashcards/note-types">
              <ArrowLeft className="size-3.5 mr-1" /> Back
            </Link>
          </Button>

          {noteType?.publish_status === 'published' || noteType?.publish_status === 'unlisted' ? (
            <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold border-emerald-500/40 text-emerald-600 dark:text-emerald-400 rounded-lg">
              <Link to={`/marketplace/note-types/${noteTypeId}`}>
                <CheckCircle className="size-3.5 mr-1 text-emerald-500" /> View on Marketplace
              </Link>
            </Button>
          ) : (
            <Button variant="secondary" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold bg-slate-900 text-white hover:bg-slate-800 rounded-lg">
              <Link to={`/marketplace/note-types/publish?id=${noteTypeId}`}>
                <Share2 className="size-3.5 mr-1 text-orange-400" /> Share Listing
              </Link>
            </Button>
          )}

          <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-lg">
            <Link to={`/flashcards/note-types/${noteTypeId}/fields`}>
              <SlidersHorizontal className="size-3.5 mr-1" /> Edit Fields
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-12 items-stretch mb-4">
        {/* Left Column: Template Editor */}
        <div className="lg:col-span-6 flex flex-col">
          <Card className="p-4 sm:p-5 border-0 sm:border border-border/80 shadow-none sm:shadow-xs flex-1 flex flex-col rounded-2xl">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 mb-3">
              <h3 className="text-sm font-semibold text-foreground">Template Editor</h3>
              <div className="flex items-center gap-2 w-full sm:w-auto overflow-x-auto pb-0.5">
                <NativeSelect
                  value={selectedTemplateId || ''}
                  onChange={(e) => setSelectedTemplateId(e.target.value)}
                  className="h-8 sm:h-9 text-xs flex-1 sm:w-40 min-w-[120px] rounded-lg"
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
                  className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-lg shrink-0"
                  onClick={() => createTemplateMutation.mutate()}
                >
                  <Plus className="size-3.5 mr-1" /> New
                </Button>

                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 sm:h-9 px-3 text-xs font-semibold text-amber-700 hover:bg-amber-50 rounded-lg shrink-0"
                  onClick={() => {
                    if (window.confirm('Khôi phục template về mặc định ban đầu?')) {
                      resetTemplateMutation.mutate()
                    }
                  }}
                >
                  <RotateCcw className="size-3.5 mr-1" /> Reset
                </Button>
              </div>
            </div>

            {/* Placeholder Toolbar */}
            <div className="mb-3">
              <span className="text-xs text-muted-foreground">Insert placeholder:</span>
              <div className="flex flex-wrap gap-1.5 mt-1.5 max-h-28 overflow-y-auto pr-0.5">
                {fields.map((field) => (
                  <Button
                    key={field.id}
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => insertPlaceholder(field.name)}
                    className="h-7 sm:h-8 px-2 sm:px-2.5 text-xs font-mono text-foreground hover:bg-orange-50 hover:border-orange-300 hover:text-orange-700 transition-all cursor-pointer rounded-md"
                  >
                    {`{{${field.name}}}`}
                  </Button>
                ))}
                {!fields.length ? (
                  <span className="text-xs text-muted-foreground italic">Chưa có trường nào</span>
                ) : null}
              </div>
            </div>

            <Tabs
              value={activeTab}
              onValueChange={(val) => setActiveTab(val as 'front' | 'back' | 'css')}
              className="flex-1 flex flex-col"
            >
              <TabsList className="grid grid-cols-3 w-full h-8 sm:h-9 p-1 mb-2 rounded-lg">
                <TabsTrigger value="front" className="text-xs font-semibold py-1 rounded-md">
                  Front HTML
                </TabsTrigger>
                <TabsTrigger value="back" className="text-xs font-semibold py-1 rounded-md">
                  Back HTML
                </TabsTrigger>
                <TabsTrigger value="css" className="text-xs font-semibold py-1 rounded-md">
                  Shared CSS
                </TabsTrigger>
              </TabsList>

              <TabsContent value="front" className="flex-1 mt-0">
                <textarea
                  ref={(el) => {
                    if (activeTab === 'front') activeTextareaRef.current = el
                  }}
                  value={frontHtml}
                  onChange={(e) => setFrontHtml(e.target.value)}
                  className="w-full font-mono text-xs sm:text-sm p-3 rounded-xl border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 min-h-[12rem] sm:min-h-[20rem] h-[clamp(14rem,40vh,30rem)] resize-y overflow-auto overscroll-contain"
                  placeholder="<h2>{{Word}}</h2>"
                />
              </TabsContent>

              <TabsContent value="back" className="flex-1 mt-0">
                <textarea
                  ref={(el) => {
                    if (activeTab === 'back') activeTextareaRef.current = el
                  }}
                  value={backHtml}
                  onChange={(e) => setBackHtml(e.target.value)}
                  className="w-full font-mono text-xs sm:text-sm p-3 rounded-xl border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 min-h-[12rem] sm:min-h-[20rem] h-[clamp(14rem,40vh,30rem)] resize-y overflow-auto overscroll-contain"
                  placeholder="<h2>{{Word}}</h2><hr/><p>{{Meaning}}</p>"
                />
              </TabsContent>

              <TabsContent value="css" className="flex-1 mt-0">
                <textarea
                  ref={(el) => {
                    if (activeTab === 'css') activeTextareaRef.current = el
                  }}
                  value={sharedCss}
                  onChange={(e) => setSharedCss(e.target.value)}
                  className="w-full font-mono text-xs sm:text-sm p-3 rounded-xl border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 min-h-[12rem] sm:min-h-[20rem] h-[clamp(14rem,40vh,30rem)] resize-y overflow-auto overscroll-contain"
                  placeholder=".card { text-align: center; color: #333; }"
                />
              </TabsContent>
            </Tabs>

            <div className="pt-3 flex justify-start border-t mt-3">
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
                className="bg-primary text-primary-foreground font-bold px-5 h-8 sm:h-9 text-xs sm:text-sm rounded-lg shadow-xs"
              >
                <Check className="size-3.5 mr-1" /> Save
              </Button>
            </div>
          </Card>
        </div>

        {/* Right Column: Live Preview Frame (Reusing NoteTypeLivePreview) */}
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
            title="Live Preview"
            subtitle="(Uses sample field data)"
          />
        </div>
      </div>
    </Page>
  )
}
