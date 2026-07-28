import { useEffect, useRef, useState } from 'react'
import {
  ArrowLeft,
  Check,
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
  field_defs?: FieldDefItem[]
  templates?: TemplateItem[]
}

type PreviewResponse = {
  front_html?: string
  back_html?: string
  front_renderer_payload?: string
  back_renderer_payload?: string
}

export function NoteTypeDetailPage() {
  const { id: noteTypeId } = useParams<{ id: string }>()
  const queryClient = useQueryClient()

  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'front' | 'back' | 'css'>('front')

  const [frontHtml, setFrontHtml] = useState('')
  const [backHtml, setBackHtml] = useState('')
  const [sharedCss, setSharedCss] = useState('')

  const [previewHtml, setPreviewHtml] = useState<string>('')
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)

  const activeTextareaRef = useRef<HTMLTextAreaElement | null>(null)

  const detailQuery = useQuery({
    queryKey: ['note-type-detail', noteTypeId],
    queryFn: () => appApi.get<NoteTypeDetail>(`/api/note-types/${noteTypeId}`),
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
      appApi.mutate(`/api/note-types/${noteTypeId}/templates/${selectedTemplateId}`, 'PATCH', payload),
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
      appApi.mutate<TemplateItem>(`/api/note-types/${noteTypeId}/templates`, 'POST', {
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
        `/api/note-types/${noteTypeId}/templates/${selectedTemplateId}/reset`,
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
    const timer = setTimeout(async () => {
      setIsPreviewLoading(true)
      try {
        const side = activeTab === 'back' ? 'back' : 'front'
        const res = await appApi.mutate<PreviewResponse>(
          `/api/note-types/${noteTypeId}/templates/${selectedTemplateId}/preview`,
          'POST',
          {
            front_html: frontHtml,
            back_html: backHtml,
            shared_css: sharedCss,
            use_sample_data: true,
          },
        )
        const rawPayload = side === 'back' ? res.back_renderer_payload : res.front_renderer_payload
        const payloadHtml =
          typeof rawPayload === 'object' && rawPayload
            ? (rawPayload as { html?: string }).html
            : typeof rawPayload === 'string'
              ? rawPayload
              : ''
        const content =
          side === 'back'
            ? res.back_html || payloadHtml || ''
            : res.front_html || payloadHtml || ''

        const fullHtml = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      padding: 0;
      background-color: transparent;
      color: initial;
    }
    .card-container {
      width: 100%;
      min-height: 100%;
      padding: 16px;
      box-sizing: border-box;
    }
    .card-container img, .card-container video, .card-container canvas, .card-container svg, .card-container audio {
      max-width: 100%;
    }
    ${sharedCss}
  </style>
</head>
<body>
  <div class="card-container">
    ${content}
  </div>
</body>
</html>`
        setPreviewHtml(fullHtml)
      } catch {
        setPreviewHtml('<p style="color:red;">Lỗi tải xem trước template.</p>')
      } finally {
        setIsPreviewLoading(false)
      }
    }, 500)

    return () => clearTimeout(timer)
  }, [noteTypeId, selectedTemplateId, frontHtml, backHtml, sharedCss, activeTab])

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
    <Page className="w-full max-w-none px-4 lg:px-8 py-3 space-y-3">
      {/* Top Header Row */}
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-foreground">{noteType?.name || 'NoteType Detail'}</h2>
          <span className="text-xs text-muted-foreground">Field + template management</span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild className="h-8 text-xs">
            <Link to="/flashcards/note-types">
              <ArrowLeft className="size-3.5 mr-1" /> Back
            </Link>
          </Button>

          <Button variant="secondary" size="sm" asChild className="h-8 text-xs bg-slate-900 text-white hover:bg-slate-800">
            <a href={`/flashcards/share-note-type/${noteTypeId}`}>
              <Share2 className="size-3.5 mr-1 text-orange-400" /> Share Listing
            </a>
          </Button>

          <Button variant="outline" size="sm" asChild className="h-8 text-xs">
            <Link to={`/flashcards/note-types/${noteTypeId}/fields`}>
              <SlidersHorizontal className="size-3.5 mr-1" /> Edit Fields
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-12 items-stretch mb-4">
        {/* Left Column: Template Editor */}
        <div className="lg:col-span-6 flex flex-col">
          <Card className="p-3 border-border/80 shadow-sm flex-1 flex flex-col rounded-xl">
            <div className="flex items-center justify-between gap-2 mb-2">
              <h3 className="text-sm font-semibold text-foreground">Template Editor</h3>
              <div className="flex items-center gap-2">
                <NativeSelect
                  value={selectedTemplateId || ''}
                  onChange={(e) => setSelectedTemplateId(e.target.value)}
                  className="h-8 text-xs w-36"
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
                  className="h-8 text-xs"
                  onClick={() => createTemplateMutation.mutate()}
                >
                  <Plus className="size-3.5 mr-1" /> New
                </Button>

                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 text-xs text-amber-700 hover:bg-amber-50"
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
            <div className="mb-2">
              <span className="text-xs text-muted-foreground">Insert placeholder:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {fields.map((field) => (
                  <Button
                    key={field.id}
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => insertPlaceholder(field.name)}
                    className="h-7 px-2 text-xs font-mono text-foreground hover:bg-orange-50 hover:border-orange-300 hover:text-orange-700 transition-all cursor-pointer"
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
              <TabsList className="grid grid-cols-3 w-full h-8 mb-2">
                <TabsTrigger value="front" className="text-xs font-semibold py-1">
                  Front HTML
                </TabsTrigger>
                <TabsTrigger value="back" className="text-xs font-semibold py-1">
                  Back HTML
                </TabsTrigger>
                <TabsTrigger value="css" className="text-xs font-semibold py-1">
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
                  className="w-full font-mono text-xs p-3 rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring min-h-[clamp(24rem,55vh,36rem)] h-[clamp(24rem,55vh,36rem)] resize-y overflow-auto overscroll-contain"
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
                  className="w-full font-mono text-xs p-3 rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring min-h-[clamp(24rem,55vh,36rem)] h-[clamp(24rem,55vh,36rem)] resize-y overflow-auto overscroll-contain"
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
                  className="w-full font-mono text-xs p-3 rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring min-h-[clamp(24rem,55vh,36rem)] h-[clamp(24rem,55vh,36rem)] resize-y overflow-auto overscroll-contain"
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
                className="bg-primary text-primary-foreground font-semibold px-4 h-8 text-xs"
              >
                <Check className="size-3.5 mr-1" /> Save
              </Button>
            </div>
          </Card>
        </div>

        {/* Right Column: Live Preview Frame */}
        <div className="lg:col-span-6 flex flex-col">
          <Card className="p-3 border-border/80 shadow-sm flex-1 flex flex-col rounded-xl">
            <div className="flex items-center gap-2 mb-2 h-[31px]">
              <h3 className="text-sm font-semibold text-foreground">Live Preview</h3>
              <span className="text-xs text-muted-foreground">(Uses sample field data)</span>
              {isPreviewLoading ? (
                <span className="text-[11px] text-orange-600 font-semibold animate-pulse ml-auto">
                  Đang cập nhật…
                </span>
              ) : null}
            </div>
            <iframe
              title="Template Live Preview"
              srcDoc={previewHtml}
              className="w-full flex-1 rounded-md border border-border bg-[#f8f9fa] min-h-[clamp(24rem,55vh,36rem)] h-[clamp(24rem,55vh,36rem)] overflow-anchor-none"
              sandbox="allow-scripts"
            />
          </Card>
        </div>
      </div>
    </Page>
  )
}
