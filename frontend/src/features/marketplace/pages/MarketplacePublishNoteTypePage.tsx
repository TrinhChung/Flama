import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { AlertCircle, Check, Loader2 } from 'lucide-react'
import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { Page } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'

import {
  NOTE_TYPE_CATEGORY_PRESETS,
  TAXONOMY_DOMAINS,
  TAXONOMY_SUBJECTS,
  TAXONOMY_DIFFICULTIES,
  TAXONOMY_LEARNING_GOALS,
  TAXONOMY_TOPICS
} from '../utils/publishTaxonomyConstants'

type SimpleNoteType = {
  id: string
  name: string
  field_count?: number
  publish_status?: string
  is_marketplace_install?: boolean
}

function FieldErrorMessage({ error }: { error?: string }) {
  if (!error) return null
  return (
    <p className="text-xs font-semibold text-destructive mt-1.5 flex items-center gap-1.5 animate-in fade-in">
      <AlertCircle className="w-3.5 h-3.5 shrink-0" />
      <span>{error}</span>
    </p>
  )
}


export function MarketplacePublishNoteTypePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryParamId = searchParams.get('id') || ''
  const isEditMode = searchParams.get('edit') === '1'

  const [sourceNoteTypeId, setSourceNoteTypeId] = useState<string>(queryParamId)
  const [title, setTitle] = useState('')
  const [previewText, setPreviewText] = useState('')
  const [description, setDescription] = useState('')
  const [pricingMode, setPricingMode] = useState<'free' | 'paid'>('free')
  const [priceAmountMinor, setPriceAmountMinor] = useState<number>(10000)
  const [version, setVersion] = useState('1.0.0')
  const [tags, setTags] = useState('')
  const [changelog, setChangelog] = useState('')
  const [primaryCategory, setPrimaryCategory] = useState('Templates')
  const [customCategory, setCustomCategory] = useState('')

  // Taxonomy states
  const [taxonomyDomain, setTaxonomyDomain] = useState('language_learning')
  const [taxonomySubject, setTaxonomySubject] = useState('japanese')
  const [taxonomyDifficulty, setTaxonomyDifficulty] = useState('beginner')
  const [taxonomyGoals, setTaxonomyGoals] = useState<string[]>(['vocabulary'])
  const [taxonomyTopics, setTaxonomyTopics] = useState<string[]>(['meaning_recall'])

  // Field validation errors
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const clearFieldError = (name: string) => {
    if (fieldErrors[name]) {
      setFieldErrors((prev) => {
        const next = { ...prev }
        delete next[name]
        return next
      })
    }
  }

  const noteTypesQuery = useQuery({
    queryKey: ['my-note-types-for-publish'],
    queryFn: () => appApi.get<{ items: SimpleNoteType[] }>('/note-types'),
  })

  // Fetch detailed info of selected note type (fields & templates)
  const selectedNoteTypeDetailQuery = useQuery({
    queryKey: ['note-type-detail-publish', sourceNoteTypeId],
    queryFn: () => appApi.get<any>(`/api/note-types/${sourceNoteTypeId}`),
    enabled: Boolean(sourceNoteTypeId),
  })

  // Sync search param ID if passed in URL
  useEffect(() => {
    if (queryParamId && !sourceNoteTypeId) {
      setSourceNoteTypeId(queryParamId)
    }
  }, [queryParamId, sourceNoteTypeId])

  const noteTypes = noteTypesQuery.data?.items || []
  const selectedNoteType = noteTypes.find((nt) => nt.id === sourceNoteTypeId)
  const isSelectedInstalledCopy = Boolean(selectedNoteType?.is_marketplace_install)
  const isSelectedAlreadyPublished = Boolean(
    !isEditMode &&
    selectedNoteType && (
      selectedNoteType.publish_status === 'published'
      || selectedNoteType.publish_status === 'unlisted'
    )
  )
  const detailData = selectedNoteTypeDetailQuery.data

  const effectiveCategory = primaryCategory === 'Custom' ? customCategory.trim() || 'Khác' : primaryCategory

  // Auto set title if title is empty when selectedNoteType changes
  useEffect(() => {
    if (!isEditMode && selectedNoteType && !title) {
      setTitle(selectedNoteType.name)
    }
  }, [selectedNoteType, title, isEditMode])

  // Populate form states from edit data
  useEffect(() => {
    if (isEditMode && detailData) {
      setTitle(detailData.title || detailData.name || '')
      setPreviewText(detailData.preview_text || '')
      setDescription(detailData.description || '')
      setPricingMode(detailData.pricing_mode || 'free')
      setPriceAmountMinor(detailData.price_amount_minor || 10000)
      setVersion(detailData.version || '1.0.0')
      setTags(detailData.tags ? detailData.tags.join(', ') : '')
      setChangelog(detailData.changelog || '')
      
      const cat = detailData.primary_category || 'Templates'
      const noteTypeCategoryPresetsValues = NOTE_TYPE_CATEGORY_PRESETS.map(p => p.id)
      if (noteTypeCategoryPresetsValues.includes(cat)) {
        setPrimaryCategory(cat)
        setCustomCategory('')
      } else {
        setPrimaryCategory('Custom')
        setCustomCategory(cat)
      }

      setTaxonomyDomain(detailData.taxonomy_metadata?.domain || 'language_learning')
      setTaxonomySubject(detailData.taxonomy_metadata?.subject || 'japanese')
      setTaxonomyDifficulty(detailData.taxonomy_metadata?.difficulty_band || 'beginner')
      setTaxonomyGoals(detailData.taxonomy_metadata?.learning_goals || ['vocabulary'])
      setTaxonomyTopics(detailData.taxonomy_metadata?.primary_topics || ['meaning_recall'])
    }
  }, [isEditMode, detailData])

  const publishMutation = useMutation({
    mutationFn: () =>
      appApi.mutate(`/api/note-types/${sourceNoteTypeId}/publish`, 'POST', {
        title: title.trim(),
        preview_text: previewText.trim(),
        description: description.trim(),
        pricing_mode: pricingMode,
        price_amount_minor: pricingMode === 'paid' ? priceAmountMinor : 0,
        version: version.trim() || '1.0.0',
        tags: tags ? tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
        changelog: changelog.trim(),
        primary_category: effectiveCategory,
        taxonomy_domain: taxonomyDomain,
        taxonomy_subject: taxonomySubject,
        taxonomy_difficulty_band: taxonomyDifficulty,
        taxonomy_learning_goals: taxonomyGoals,
        taxonomy_primary_topics: taxonomyTopics,
      }),
    onSuccess: () => {
      toast.success(
        isEditMode
          ? 'Đã cập nhật cấu hình chia sẻ Loại thẻ thành công!'
          : 'Đã xuất bản Loại thẻ lên Marketplace thành công!'
      )
      navigate(`/marketplace/note-types/${sourceNoteTypeId}`)
    },
    onError: (error: any) => {
      const msg = error?.message || ''
      const field = error?.field || ''
      const serverErrs: Record<string, string> = {}

      if (field === 'source_note_type_id' || msg.includes('source_note_type_id')) {
        serverErrs.sourceNoteTypeId = 'Vui lòng chọn loại thẻ cần xuất bản.'
      }
      if (field === 'title' || msg.includes('Title')) {
        serverErrs.title = 'Vui lòng nhập tiêu đề hiển thị.'
      }
      if (field === 'description' || msg.includes('Description')) {
        serverErrs.description = 'Vui lòng nhập mô tả chi tiết mẫu thẻ.'
      }
      if (field === 'preview_text' || msg.includes('Preview text')) {
        serverErrs.previewText = 'Vui lòng nhập xem trước ngắn (Preview Text).'
      }
      if (field === 'taxonomy_domain' || msg.includes('taxonomy_domain')) {
        serverErrs.taxonomyDomain = 'Vui lòng chọn Lĩnh vực học tập.'
      }
      if (field === 'taxonomy_subject' || msg.includes('taxonomy_subject')) {
        serverErrs.taxonomySubject = 'Vui lòng chọn Ngôn ngữ / Môn học.'
      }
      if (field === 'taxonomy_difficulty_band' || msg.includes('taxonomy_difficulty_band')) {
        serverErrs.taxonomyDifficulty = 'Vui lòng chọn Trình độ / Mức độ khó.'
      }
      if (field === 'taxonomy_learning_goals' || msg.includes('learning goal')) {
        serverErrs.taxonomyGoals = 'Vui lòng chọn ít nhất 1 Mục tiêu học tập.'
      }
      if (field === 'taxonomy_primary_topics' || msg.includes('primary topic')) {
        serverErrs.taxonomyTopics = 'Vui lòng chọn ít nhất 1 Chủ đề chính.'
      }

      if (Object.keys(serverErrs).length > 0) {
        setFieldErrors((prev) => ({ ...prev, ...serverErrs }))
        toast.error('Có thông tin bị thiếu hoặc không hợp lệ. Vui lòng kiểm tra các vị trí báo đỏ bên dưới.')
      } else {
        toast.error(msg || 'Không thể xuất bản. Vui lòng kiểm tra lại thông tin.')
      }
    },
  })

  const validateForm = (): boolean => {
    const errs: Record<string, string> = {}
    if (!isEditMode && !sourceNoteTypeId) {
      errs.sourceNoteTypeId = 'Vui lòng chọn Loại thẻ cần xuất bản.'
    }
    if (!title.trim()) {
      errs.title = 'Vui lòng nhập tiêu đề hiển thị.'
    }
    if (!previewText.trim()) {
      errs.previewText = 'Vui lòng nhập xem trước ngắn (Preview Text) để hiển thị danh sách.'
    }
    if (!description.trim()) {
      errs.description = 'Vui lòng nhập mô tả chi tiết mẫu thẻ.'
    }
    if (primaryCategory === 'Custom' && !customCategory.trim()) {
      errs.customCategory = 'Vui lòng nhập tên danh mục tùy chỉnh.'
    }
    if (!taxonomyDomain) {
      errs.taxonomyDomain = 'Vui lòng chọn Lĩnh vực học tập.'
    }
    if (!taxonomySubject) {
      errs.taxonomySubject = 'Vui lòng chọn Ngôn ngữ / Môn học.'
    }
    if (!taxonomyDifficulty) {
      errs.taxonomyDifficulty = 'Vui lòng chọn Trình độ / Mức độ khó.'
    }
    if (taxonomyGoals.length === 0) {
      errs.taxonomyGoals = 'Vui lòng chọn ít nhất 1 Mục tiêu học tập (bấm chọn các ô màu).'
    }
    if (taxonomyTopics.length === 0) {
      errs.taxonomyTopics = 'Vui lòng chọn ít nhất 1 Chủ đề chính (bấm chọn các ô màu).'
    }
    if (pricingMode === 'paid' && (!priceAmountMinor || priceAmountMinor <= 0)) {
      errs.priceAmountMinor = 'Vui lòng nhập giá bán hợp lệ (> 0 VND).'
    }

    setFieldErrors(errs)
    if (Object.keys(errs).length > 0) {
      toast.error('Thông tin chưa đầy đủ! Vui lòng điền các trường màu đỏ bên dưới.')
      return false
    }
    return true
  }

  if (noteTypesQuery.isPending || (isEditMode && selectedNoteTypeDetailQuery.isPending)) return <PageLoading label="Đang tải dữ liệu..." />
  if (noteTypesQuery.error) return <Page><PageError error={noteTypesQuery.error} /></Page>
  if (sourceNoteTypeId && selectedNoteTypeDetailQuery.error) {
    return <Page><PageError error={selectedNoteTypeDetailQuery.error} /></Page>
  }

  const fieldDefs: Array<{ name: string; label?: string }> = detailData?.field_defs || []
  const templates: Array<{ name: string }> = detailData?.templates || []
  const availableSubjects = TAXONOMY_SUBJECTS[taxonomyDomain] || TAXONOMY_SUBJECTS.other

  return (
    <Page className="space-y-6 relative px-3 sm:px-6 lg:px-8 py-4 sm:py-6 max-w-7xl mx-auto">
      <AmbientBackground intensity="subtle" />

      {/* Hero Header Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-card/80 p-4 sm:p-6 shadow-sm backdrop-blur-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="border-primary/40 bg-primary/10 text-primary font-bold text-[11px] px-2.5 py-0.5">
                NoteType Publisher
              </Badge>
              <Badge variant="secondary" className="text-[11px] font-medium">
                Mẫu thẻ Anki / Flama
              </Badge>
            </div>
            <h1 className="text-xl sm:text-2xl md:text-3xl font-black tracking-tight text-foreground">
              {isEditMode ? 'Chỉnh sửa thông tin chia sẻ Loại thẻ' : 'Chia sẻ Loại thẻ (Note Type) vào Marketplace'}
            </h1>
            <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed max-w-3xl">
              {isEditMode
                ? 'Cập nhật lại các thông tin mô tả chi tiết, phân loại học tập và giá bán của loại thẻ đã xuất bản.'
                : 'Đóng gói thiết kế mẫu thẻ (Cloze, Từ vựng song ngữ, Code Snippets, Q&A...) và cấu hình trường dữ liệu để chia sẻ cho cộng đồng.'}
            </p>
          </div>

          <Button variant="outline" asChild className="h-9 px-3.5 text-xs font-semibold rounded-xl shrink-0 self-start sm:self-center">
            <Link to={isEditMode ? `/marketplace/note-types/${sourceNoteTypeId}` : "/marketplace/note-types"}>
              {isEditMode ? 'Quay lại chi tiết' : 'Quay lại NoteTypes'}
            </Link>
          </Button>
        </div>
      </div>

      {isSelectedInstalledCopy ? (
        <div className="rounded-2xl border border-destructive/30 bg-destructive/10 p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-in fade-in duration-200">
          <div className="space-y-1">
            <div className="font-bold text-sm text-destructive">
              Note Type cài từ Marketplace không thể chia sẻ lại
            </div>
            <div className="text-xs text-muted-foreground">
              Mẫu NoteType &ldquo;{selectedNoteType?.name}&rdquo; được tải về từ Marketplace nên không thể xuất bản.
            </div>
          </div>
        </div>
      ) : isSelectedAlreadyPublished ? (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-in fade-in duration-200">
          <div className="space-y-1">
            <div className="font-bold text-sm text-amber-700 dark:text-amber-400">
              NoteType này đã được xuất bản trên Marketplace
            </div>
            <div className="text-xs text-muted-foreground">
              Mẫu NoteType &ldquo;{selectedNoteType?.name}&rdquo; đã có sẵn trên Marketplace.
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button variant="outline" size="sm" asChild className="h-9 text-xs font-bold rounded-xl border-amber-500/40 text-amber-600 dark:text-amber-400">
              <Link to={`/marketplace/note-types/${selectedNoteType?.id}`}>
                Xem mẫu thẻ trên Marketplace
              </Link>
            </Button>
            <Button variant="default" size="sm" asChild className="h-9 text-xs font-bold rounded-xl">
              <Link to={`/marketplace/note-types/publish?id=${selectedNoteType?.id}&edit=1`}>
                Chỉnh sửa thông tin
              </Link>
            </Button>
          </div>
        </div>
      ) : null}

      {/* Global Form Validation Warning Alert */}
      {Object.keys(fieldErrors).length > 0 && (
        <div className="rounded-2xl border border-destructive/40 bg-destructive/10 p-4 sm:p-5 flex items-start gap-3.5 animate-in fade-in duration-200">
          <AlertCircle className="w-5 h-5 text-destructive shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs sm:text-sm">
            <div className="font-bold text-destructive">
              Thông tin xuất bản chưa hoàn thiện ({Object.keys(fieldErrors).length} vị trí bị thiếu)
            </div>
            <div className="text-destructive/90 font-medium leading-relaxed">
              Vui lòng xem các dòng báo lỗi đỏ dưới từng ô nhập liệu bên dưới để bổ sung trước khi bấm Xuất bản.
            </div>
          </div>
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (isSelectedInstalledCopy || isSelectedAlreadyPublished) return
          if (validateForm()) {
            publishMutation.mutate()
          }
        }}
        className="grid gap-6 lg:grid-cols-3 items-start"
      >
        {/* Main Listing Details Form */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="shadow-xs rounded-2xl border-border/80 bg-card/90 backdrop-blur-sm overflow-hidden">
            <CardHeader className="p-4 sm:p-6 pb-3 border-b border-border/40 bg-muted/20">
              <CardTitle className="text-base sm:text-lg font-bold">
                1. Chọn Mẫu NoteType & Thông tin mô tả
              </CardTitle>
              <CardDescription className="text-xs">
                Chọn mẫu loại thẻ cá nhân và cung cấp các thông tin giới thiệu hấp dẫn.
              </CardDescription>
            </CardHeader>

            <CardContent className="p-4 sm:p-6 space-y-5">
              <div className="space-y-2">
                <Label htmlFor="source-nt" className="text-xs font-semibold flex items-center justify-between">
                  <span>Loại thẻ chia sẻ nguồn <span className="text-destructive">*</span></span>
                </Label>
                {isEditMode ? (
                  <div className="p-3.5 rounded-xl border border-primary/20 bg-primary/5 text-xs font-semibold text-foreground flex items-center justify-between">
                    <span>{title || 'Loại thẻ nguồn'}</span>
                    <span className="text-[10px] text-muted-foreground font-mono">ID: {sourceNoteTypeId}</span>
                  </div>
                ) : (
                  <NativeSelect
                    id="source-nt"
                    value={sourceNoteTypeId}
                    onChange={(e) => {
                      setSourceNoteTypeId(e.target.value)
                      clearFieldError('sourceNoteTypeId')
                      const found = noteTypes.find((nt) => nt.id === e.target.value)
                      if (found && !title) setTitle(found.name)
                    }}
                    className={`h-10 text-xs sm:text-sm rounded-xl font-medium ${
                      fieldErrors.sourceNoteTypeId ? 'border-destructive focus-visible:ring-destructive bg-destructive/5' : ''
                    }`}
                    required
                  >
                    <NativeSelectOption value="">-- Chọn loại thẻ chưa xuất bản --</NativeSelectOption>
                    {noteTypes.map((nt) => {
                      const isPublished = nt.publish_status === 'published' || nt.publish_status === 'unlisted'
                      const isBlocked = isPublished || Boolean(nt.is_marketplace_install)
                      return (
                        <NativeSelectOption key={nt.id} value={nt.id} disabled={isBlocked}>
                          {nt.name} {nt.is_marketplace_install ? '(Từ Marketplace)' : isPublished ? '(Đã xuất bản)' : ''}
                        </NativeSelectOption>
                      )
                    })}
                  </NativeSelect>
                )}
                <FieldErrorMessage error={fieldErrors.sourceNoteTypeId} />
              </div>

              {/* NoteType Field & Template Badge Summary */}
              {sourceNoteTypeId ? (
                <div className="rounded-xl border border-primary/20 bg-primary/5 p-3.5 space-y-2 text-xs">
                  <div className="font-bold text-foreground flex items-center justify-between">
                    <span>Cấu trúc NoteType đã chọn:</span>
                    <span className="text-[11px] text-muted-foreground font-mono">ID: {sourceNoteTypeId}</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {fieldDefs.length > 0 ? (
                      fieldDefs.map((f, i) => (
                        <Badge key={i} variant="secondary" className="text-[11px] bg-background border font-semibold">
                          Trường: {f.name}
                        </Badge>
                      ))
                    ) : (
                      <Badge variant="outline" className="text-[11px]">Đang tải cấu trúc trường...</Badge>
                    )}
                    {templates.length > 0 ? (
                      <Badge variant="outline" className="text-[11px] border-primary/40 text-primary font-bold">
                        {templates.length} Templates
                      </Badge>
                    ) : null}
                  </div>
                </div>
              ) : null}

              {/* Title */}
              <div className="space-y-2">
                <Label htmlFor="nt-title" className="text-xs font-semibold flex items-center justify-between">
                  <span>Tiêu đề hiển thị (Listing Title) <span className="text-destructive">*</span></span>
                </Label>
                <Input
                  id="nt-title"
                  placeholder="Ví dụ: Cloze Deletion Chuẩn Anki, Mẫu Từ vựng Đa ngữ, Code Snippets..."
                  value={title}
                  onChange={(e) => {
                    setTitle(e.target.value)
                    clearFieldError('title')
                  }}
                  className={`h-10 text-xs sm:text-sm rounded-xl font-medium ${
                    fieldErrors.title ? 'border-destructive focus-visible:ring-destructive bg-destructive/5' : ''
                  }`}
                />
                <FieldErrorMessage error={fieldErrors.title} />
              </div>

              {/* Short Preview */}
              <div className="space-y-2">
                <Label htmlFor="nt-preview" className="text-xs font-semibold flex items-center justify-between">
                  <span>Xem trước ngắn (Preview Text) <span className="text-destructive">*</span></span>
                </Label>
                <Input
                  id="nt-preview"
                  placeholder="1 dòng tóm tắt thiết kế mẫu thẻ để người học xem nhanh trên danh sách"
                  value={previewText}
                  onChange={(e) => {
                    setPreviewText(e.target.value)
                    clearFieldError('previewText')
                  }}
                  className={`h-10 text-xs sm:text-sm rounded-xl ${
                    fieldErrors.previewText ? 'border-destructive focus-visible:ring-destructive bg-destructive/5' : ''
                  }`}
                  maxLength={160}
                />
                <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                  <div><FieldErrorMessage error={fieldErrors.previewText} /></div>
                  <div>{previewText.length}/160 ký tự</div>
                </div>
              </div>

              {/* Description */}
              <div className="space-y-2">
                <Label htmlFor="nt-desc" className="text-xs font-semibold flex items-center justify-between">
                  <span>Mô tả chi tiết mẫu thẻ <span className="text-destructive">*</span></span>
                </Label>
                <Textarea
                  id="nt-desc"
                  rows={5}
                  placeholder="Mô tả chi tiết cấu trúc field, thiết kế CSS, cách trình bày và trường hợp sử dụng phù hợp…"
                  value={description}
                  onChange={(e) => {
                    setDescription(e.target.value)
                    clearFieldError('description')
                  }}
                  className={`text-xs sm:text-sm rounded-xl leading-relaxed ${
                    fieldErrors.description ? 'border-destructive focus-visible:ring-destructive bg-destructive/5' : ''
                  }`}
                />
                <FieldErrorMessage error={fieldErrors.description} />
              </div>

              {/* Changelog */}
              <div className="space-y-2">
                <Label htmlFor="nt-changelog" className="text-xs font-semibold">Ghi chú phát hành (Changelog)</Label>
                <Textarea
                  id="nt-changelog"
                  rows={2}
                  placeholder="Ví dụ: Phiên bản đầu tiên hỗ trợ highlight cú pháp và audio tự động..."
                  value={changelog}
                  onChange={(e) => setChangelog(e.target.value)}
                  className="text-xs sm:text-sm rounded-xl"
                />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar: Taxonomy & Live Marketplace Preview */}
        <div className="space-y-6">
          {/* Category & Pricing Options */}
          <Card className="shadow-xs rounded-2xl border-border/80 bg-card/90 backdrop-blur-sm overflow-hidden">
            <CardHeader className="p-4 sm:p-5 pb-3 border-b border-border/40 bg-muted/20">
              <CardTitle className="text-base font-bold">
                2. Phân loại & Mô hình Giá
              </CardTitle>
              <CardDescription className="text-xs">
                Thiết lập phân loại và tùy chọn giá bán cho NoteType.
              </CardDescription>
            </CardHeader>

            <CardContent className="p-4 sm:p-5 space-y-4">
              {/* Category Quick Presets */}
              <div className="space-y-2">
                <Label htmlFor="nt-category" className="text-xs font-semibold">Danh mục mẫu thẻ</Label>
                <NativeSelect
                  id="nt-category"
                  value={primaryCategory}
                  onChange={(e) => setPrimaryCategory(e.target.value)}
                  className="h-10 text-xs sm:text-sm rounded-xl font-medium"
                >
                  {NOTE_TYPE_CATEGORY_PRESETS.map((cat) => (
                    <NativeSelectOption key={cat.id} value={cat.id}>
                      {cat.label} — {cat.sub}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </div>

              {primaryCategory === 'Custom' && (
                <div className="space-y-1.5 animate-in fade-in duration-200">
                  <Label htmlFor="custom-category" className="text-xs font-semibold">Tên danh mục tùy chỉnh <span className="text-destructive">*</span></Label>
                  <Input
                    id="custom-category"
                    placeholder="Ví dụ: Lập trình Python, Kanji nâng cao..."
                    value={customCategory}
                    onChange={(e) => {
                      setCustomCategory(e.target.value)
                      clearFieldError('customCategory')
                    }}
                    className={`h-10 text-xs sm:text-sm rounded-xl ${
                      fieldErrors.customCategory ? 'border-destructive bg-destructive/5' : ''
                    }`}
                  />
                  <FieldErrorMessage error={fieldErrors.customCategory} />
                </div>
              )}

              {/* Taxonomy Domain Selection */}
              <div className="space-y-2 pt-2 border-t border-border/40">
                <Label htmlFor="nt-tax-domain" className="text-xs font-semibold flex items-center justify-between">
                  <span>Lĩnh vực học tập (Domain) <span className="text-destructive">*</span></span>
                </Label>
                <NativeSelect
                  id="nt-tax-domain"
                  value={taxonomyDomain}
                  onChange={(e) => {
                    const newDomain = e.target.value
                    setTaxonomyDomain(newDomain)
                    clearFieldError('taxonomyDomain')
                    const subs = TAXONOMY_SUBJECTS[newDomain] || TAXONOMY_SUBJECTS.other
                    if (subs.length > 0) setTaxonomySubject(subs[0].id)
                  }}
                  className={`h-10 text-xs sm:text-sm rounded-xl font-medium ${
                    fieldErrors.taxonomyDomain ? 'border-destructive bg-destructive/5' : ''
                  }`}
                >
                  {TAXONOMY_DOMAINS.map((d) => (
                    <NativeSelectOption key={d.id} value={d.id}>
                      {d.label}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
                <FieldErrorMessage error={fieldErrors.taxonomyDomain} />
              </div>

              {/* Taxonomy Subject Selection */}
              <div className="space-y-2">
                <Label htmlFor="nt-tax-subject" className="text-xs font-semibold flex items-center justify-between">
                  <span>Ngôn ngữ / Môn học (Subject) <span className="text-destructive">*</span></span>
                </Label>
                <NativeSelect
                  id="nt-tax-subject"
                  value={taxonomySubject}
                  onChange={(e) => {
                    setTaxonomySubject(e.target.value)
                    clearFieldError('taxonomySubject')
                  }}
                  className={`h-10 text-xs sm:text-sm rounded-xl font-medium ${
                    fieldErrors.taxonomySubject ? 'border-destructive bg-destructive/5' : ''
                  }`}
                >
                  {availableSubjects.map((s) => (
                    <NativeSelectOption key={s.id} value={s.id}>
                      {s.label}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
                <FieldErrorMessage error={fieldErrors.taxonomySubject} />
              </div>

              {/* Taxonomy Difficulty Selection */}
              <div className="space-y-2">
                <Label htmlFor="nt-tax-diff" className="text-xs font-semibold flex items-center justify-between">
                  <span>Trình độ / Mức độ khó (Difficulty) <span className="text-destructive">*</span></span>
                </Label>
                <NativeSelect
                  id="nt-tax-diff"
                  value={taxonomyDifficulty}
                  onChange={(e) => {
                    setTaxonomyDifficulty(e.target.value)
                    clearFieldError('taxonomyDifficulty')
                  }}
                  className={`h-10 text-xs sm:text-sm rounded-xl font-medium ${
                    fieldErrors.taxonomyDifficulty ? 'border-destructive bg-destructive/5' : ''
                  }`}
                >
                  {TAXONOMY_DIFFICULTIES.map((d) => (
                    <NativeSelectOption key={d.id} value={d.id}>
                      {d.label}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
                <FieldErrorMessage error={fieldErrors.taxonomyDifficulty} />
              </div>

              {/* Taxonomy Learning Goals Multi-select Chips */}
              <div className="space-y-2 pt-2 border-t border-border/40">
                <Label className="text-xs font-semibold flex items-center justify-between">
                  <span>Mục tiêu học tập (Learning Goals) <span className="text-destructive">*</span></span>
                  <span className="text-[11px] text-muted-foreground font-normal">Chọn ít nhất 1</span>
                </Label>
                <div className="flex flex-wrap gap-1.5 pt-0.5">
                  {TAXONOMY_LEARNING_GOALS.map((g) => {
                    const isSelected = taxonomyGoals.includes(g.id)
                    return (
                      <Badge
                        key={g.id}
                        variant={isSelected ? 'default' : 'outline'}
                        className={`cursor-pointer text-[11px] py-1 px-2.5 rounded-lg transition-all ${
                          isSelected
                            ? 'bg-primary text-primary-foreground font-bold shadow-2xs'
                            : 'hover:bg-muted font-medium'
                        }`}
                        onClick={() => {
                          clearFieldError('taxonomyGoals')
                          setTaxonomyGoals((prev) =>
                            isSelected ? prev.filter((id) => id !== g.id) : [...prev, g.id]
                          )
                        }}
                      >
                        {isSelected && <Check className="w-3 h-3 mr-1 inline shrink-0" />}
                        {g.label}
                      </Badge>
                    )
                  })}
                </div>
                <FieldErrorMessage error={fieldErrors.taxonomyGoals} />
              </div>

              {/* Taxonomy Primary Topics Multi-select Chips */}
              <div className="space-y-2 pt-2 border-t border-border/40">
                <Label className="text-xs font-semibold flex items-center justify-between">
                  <span>Chủ đề chính (Primary Topics) <span className="text-destructive">*</span></span>
                  <span className="text-[11px] text-muted-foreground font-normal">Chọn ít nhất 1</span>
                </Label>
                <div className="flex flex-wrap gap-1.5 pt-0.5">
                  {TAXONOMY_TOPICS.map((t) => {
                    const isSelected = taxonomyTopics.includes(t.id)
                    return (
                      <Badge
                        key={t.id}
                        variant={isSelected ? 'default' : 'outline'}
                        className={`cursor-pointer text-[11px] py-1 px-2.5 rounded-lg transition-all ${
                          isSelected
                            ? 'bg-primary text-primary-foreground font-bold shadow-2xs'
                            : 'hover:bg-muted font-medium'
                        }`}
                        onClick={() => {
                          clearFieldError('taxonomyTopics')
                          setTaxonomyTopics((prev) =>
                            isSelected ? prev.filter((id) => id !== t.id) : [...prev, t.id]
                          )
                        }}
                      >
                        {isSelected && <Check className="w-3 h-3 mr-1 inline shrink-0" />}
                        {t.label}
                      </Badge>
                    )
                  })}
                </div>
                <FieldErrorMessage error={fieldErrors.taxonomyTopics} />
              </div>

              {/* Pricing Segment Toggle */}
              <div className="space-y-2 pt-2 border-t border-border/40">
                <Label className="text-xs font-semibold">Mô hình phân phối</Label>
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    type="button"
                    variant={pricingMode === 'free' ? 'default' : 'outline'}
                    className="h-9 text-xs font-bold rounded-xl"
                    onClick={() => setPricingMode('free')}
                  >
                    Miễn phí (Free)
                  </Button>
                  <Button
                    type="button"
                    variant={pricingMode === 'paid' ? 'default' : 'outline'}
                    className="h-9 text-xs font-bold rounded-xl"
                    onClick={() => setPricingMode('paid')}
                  >
                    Trả phí (Paid)
                  </Button>
                </div>
              </div>

              {pricingMode === 'paid' && (
                <div className="space-y-1.5 animate-in fade-in duration-200">
                  <Label htmlFor="nt-price" className="text-xs font-semibold">Giá bán (VND)</Label>
                  <Input
                    id="nt-price"
                    type="number"
                    min={1000}
                    step={1000}
                    value={priceAmountMinor}
                    onChange={(e) => {
                      setPriceAmountMinor(Number(e.target.value))
                      clearFieldError('priceAmountMinor')
                    }}
                    className={`h-10 text-xs sm:text-sm rounded-xl font-bold text-primary ${
                      fieldErrors.priceAmountMinor ? 'border-destructive bg-destructive/5' : ''
                    }`}
                  />
                  <FieldErrorMessage error={fieldErrors.priceAmountMinor} />
                </div>
              )}

              <div className="grid gap-3 sm:grid-cols-2 pt-2 border-t border-border/40">
                <div className="space-y-1.5">
                  <Label htmlFor="nt-version" className="text-xs font-semibold">Phiên bản</Label>
                  <Input
                    id="nt-version"
                    value={version}
                    onChange={(e) => setVersion(e.target.value)}
                    className="h-10 text-xs sm:text-sm rounded-xl font-mono"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="nt-tags" className="text-xs font-semibold">Tags (cách nhau dấu phẩy)</Label>
                  <Input
                    id="nt-tags"
                    placeholder="cloze, kanji, code"
                    value={tags}
                    onChange={(e) => setTags(e.target.value)}
                    className="h-10 text-xs sm:text-sm rounded-xl"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Live Marketplace Card Preview */}
          <Card className="shadow-sm rounded-2xl border-primary/30 bg-gradient-to-br from-card via-background to-primary/5 overflow-hidden">
            <CardHeader className="p-4 sm:p-5 pb-2">
              <CardTitle className="text-sm font-bold text-foreground">
                Xem trước trên Marketplace (Live Preview)
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 sm:p-5 pt-0 space-y-3">
              <div className="rounded-xl border bg-card/90 p-4 space-y-3 shadow-2xs">
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1 min-w-0">
                    <div className="font-bold text-sm text-foreground line-clamp-1">
                      {title.trim() || 'Tiêu đề NoteType của bạn'}
                    </div>
                    <div className="text-xs text-muted-foreground line-clamp-2">
                      {previewText.trim() || 'Mô tả ngắn hiển thị tại đây khi người học duyệt danh sách loại thẻ...'}
                    </div>
                  </div>
                  <Badge variant={pricingMode === 'paid' ? 'default' : 'secondary'} className="shrink-0 text-xs font-bold">
                    {pricingMode === 'paid' ? `${priceAmountMinor.toLocaleString('vi-VN')} đ` : 'Miễn phí'}
                  </Badge>
                </div>

                <div className="flex flex-wrap items-center gap-1.5 pt-1">
                  <Badge variant="outline" className="text-[10px] bg-primary/5 text-primary border-primary/20 font-semibold">
                    {effectiveCategory}
                  </Badge>
                  {fieldDefs.length > 0 ? (
                    <Badge variant="outline" className="text-[10px] text-muted-foreground">
                      {fieldDefs.length} trường
                    </Badge>
                  ) : null}
                  <Badge variant="outline" className="text-[10px] text-muted-foreground font-mono">
                    v{version}
                  </Badge>
                </div>
              </div>

              <div className="pt-2">
                <Button
                  type="submit"
                  size="lg"
                  className="w-full h-11 font-bold text-sm rounded-xl shadow-md bg-primary hover:bg-primary/90 text-primary-foreground"
                  disabled={isSelectedInstalledCopy || isSelectedAlreadyPublished || publishMutation.isPending}
                >
                  {isSelectedInstalledCopy 
                    ? 'Bản cài Marketplace (Không thể xuất bản)' 
                    : isSelectedAlreadyPublished 
                      ? 'Đã xuất bản (Bấm Chỉnh sửa ở trên)' 
                      : publishMutation.isPending 
                        ? 'Đang lưu…' 
                        : isEditMode 
                          ? 'Cập nhật cấu hình chia sẻ' 
                          : 'Xuất bản Loại thẻ ngay'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </form>
    </Page>
  )
}
