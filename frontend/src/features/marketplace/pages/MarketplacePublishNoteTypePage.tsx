import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  DollarSign,
  Sparkles,
  Target
} from 'lucide-react'
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

import { useTaxonomySchema } from '../hooks/useTaxonomySchema'
import {
  NOTE_TYPE_CATEGORY_PRESETS,
  TAXONOMY_DIFFICULTIES,
  getDefaultGoalsForSubject,
  getDefaultTopicsForSubject,
} from '../utils/publishTaxonomyConstants'

const WIZARD_STEPS = [
  { id: 1, title: 'Mẫu thẻ & Mô tả', sub: 'Chọn NoteType và giới thiệu', icon: BookOpen },
  { id: 2, title: 'Phân loại & Trình độ', sub: 'Chứng chỉ & Môn học', icon: Sparkles },
  { id: 3, title: 'Mục tiêu & Kỹ năng', sub: 'Goals & Chủ đề trọng tâm', icon: Target },
  { id: 4, title: 'Giá bán & Đăng tải', sub: 'Thiết lập giá và xuất bản', icon: DollarSign },
]

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
  const [taxonomyFramework, setTaxonomyFramework] = useState('')
  const [taxonomyFrameworkLevel, setTaxonomyFrameworkLevel] = useState('')
  const [taxonomyDifficulty, setTaxonomyDifficulty] = useState('beginner')
  const [taxonomyGoals, setTaxonomyGoals] = useState<string[]>(['vocabulary'])
  const [taxonomyTopics, setTaxonomyTopics] = useState<string[]>(['meaning_recall'])

  // Wizard Step state
  const [currentStep, setCurrentStep] = useState<number>(1)

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
      setTaxonomyFramework(detailData.taxonomy_metadata?.framework || '')
      setTaxonomyFrameworkLevel(detailData.taxonomy_metadata?.framework_level || '')
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
        taxonomy_framework: taxonomyFramework || undefined,
        taxonomy_framework_level: taxonomyFrameworkLevel || undefined,
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
        toast.error('Có thông tin bị thiếu hoặc không hợp lệ. Vui lòng kiểm tra các vị trí báo đỏ.')
      } else {
        toast.error(msg || 'Không thể xuất bản. Vui lòng kiểm tra lại thông tin.')
      }
    },
  })

  const validateStep = (stepNumber: number): boolean => {
    const errs: Record<string, string> = {}
    if (stepNumber === 1) {
      if (!isEditMode && !sourceNoteTypeId) {
        errs.sourceNoteTypeId = 'Vui lòng chọn Loại thẻ cần xuất bản.'
      }
      if (!title.trim()) {
        errs.title = 'Vui lòng nhập tiêu đề hiển thị.'
      }
      if (!previewText.trim()) {
        errs.previewText = 'Vui lòng nhập xem trước ngắn (Preview Text).'
      }
      if (!description.trim()) {
        errs.description = 'Vui lòng nhập mô tả chi tiết mẫu thẻ.'
      }
    } else if (stepNumber === 2) {
      if (!taxonomyDomain) {
        errs.taxonomyDomain = 'Vui lòng chọn Lĩnh vực học tập.'
      }
      if (!taxonomySubject) {
        errs.taxonomySubject = 'Vui lòng chọn Ngôn ngữ / Môn học.'
      }
      if (!taxonomyDifficulty) {
        errs.taxonomyDifficulty = 'Vui lòng chọn Trình độ / Mức độ khó.'
      }
      if (primaryCategory === 'Custom' && !customCategory.trim()) {
        errs.customCategory = 'Vui lòng nhập tên danh mục tùy chỉnh.'
      }
    } else if (stepNumber === 3) {
      if (taxonomyGoals.length === 0) {
        errs.taxonomyGoals = 'Vui lòng chọn ít nhất 1 Mục tiêu học tập.'
      }
      if (taxonomyTopics.length === 0) {
        errs.taxonomyTopics = 'Vui lòng chọn ít nhất 1 Chủ đề chính.'
      }
    } else if (stepNumber === 4) {
      if (pricingMode === 'paid' && (!priceAmountMinor || priceAmountMinor <= 0)) {
        errs.priceAmountMinor = 'Vui lòng nhập giá bán hợp lệ (> 0 VND).'
      }
    }

    setFieldErrors(errs)
    if (Object.keys(errs).length > 0) {
      toast.error('Vui lòng hoàn thiện các trường bắt buộc trong bước này.')
      return false
    }
    return true
  }

  const validateForm = (): boolean => {
    for (let s = 1; s <= 4; s++) {
      if (!validateStep(s)) {
        setCurrentStep(s)
        return false
      }
    }
    return true
  }

  const handlePublish = () => {
    if (currentStep !== 4) return
    if (isSelectedInstalledCopy || isSelectedAlreadyPublished) return
    if (validateForm()) {
      publishMutation.mutate()
    }
  }

  const handleNextStep = () => {
    if (validateStep(currentStep)) {
      setCurrentStep((prev) => Math.min(prev + 1, 4))
    }
  }

  const handlePrevStep = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 1))
  }

  const goToStep = (targetStep: number) => {
    if (targetStep < currentStep) {
      setCurrentStep(targetStep)
      return
    }
    if (validateStep(currentStep)) {
      setCurrentStep(targetStep)
    }
  }

  const taxonomySchema = useTaxonomySchema('note_type')

  const availableDomains = taxonomySchema.domains
  const availableSubjects = taxonomySchema.subjectsByDomain(taxonomyDomain)
  const availableFrameworks = useMemo(
    () => taxonomySchema.frameworksForSubject(taxonomySubject),
    [taxonomySchema, taxonomySubject],
  )
  const activeFramework = useMemo(
    () => availableFrameworks.find((f) => f.id === taxonomyFramework) || availableFrameworks[0] || null,
    [availableFrameworks, taxonomyFramework],
  )
  const availableGoals = useMemo(
    () => taxonomySchema.goalsForSubject(taxonomySubject, taxonomyDomain),
    [taxonomySchema, taxonomySubject, taxonomyDomain],
  )
  const availableTopics = useMemo(
    () => taxonomySchema.topicsForSubject(taxonomySubject, taxonomyDomain),
    [taxonomySchema, taxonomySubject, taxonomyDomain],
  )

  if (noteTypesQuery.isPending || (isEditMode && selectedNoteTypeDetailQuery.isPending)) return <PageLoading label="Đang tải dữ liệu..." />
  if (noteTypesQuery.error) return <Page><PageError error={noteTypesQuery.error} /></Page>
  if (sourceNoteTypeId && selectedNoteTypeDetailQuery.error) {
    return <Page><PageError error={selectedNoteTypeDetailQuery.error} /></Page>
  }

  const fieldDefs: Array<{ name: string; label?: string }> = detailData?.field_defs || []
  const templates: Array<{ name: string }> = detailData?.templates || []

  return (
    <Page className="space-y-6 relative px-3 sm:px-6 lg:px-8 py-4 sm:py-6 max-w-7xl mx-auto">
      <AmbientBackground intensity="subtle" />

      {/* Hero Header Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-border/80 bg-card/60 p-4 sm:p-6 shadow-xs backdrop-blur-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="border-border/80 bg-muted font-bold text-[11px] px-2.5 py-0.5 text-foreground">
                NoteType Publisher
              </Badge>
              <Badge variant="outline" className="text-[11px] font-medium text-muted-foreground">
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
        <div className="rounded-2xl border border-border/80 bg-muted/40 p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-in fade-in duration-200">
          <div className="space-y-1">
            <div className="font-bold text-sm text-foreground">
              NoteType này đã được xuất bản trên Marketplace
            </div>
            <div className="text-xs text-muted-foreground">
              Mẫu NoteType &ldquo;{selectedNoteType?.name}&rdquo; đã có sẵn trên Marketplace.
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button variant="outline" size="sm" asChild className="h-9 text-xs font-bold rounded-xl">
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

      {/* Wizard Stepper Progress Bar */}
      <div className="rounded-2xl border border-border/80 bg-card/90 p-1.5 sm:p-3 shadow-xs backdrop-blur-md">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-1.5 sm:gap-2">
          {WIZARD_STEPS.map((s) => {
            const StepIcon = s.icon
            const isActive = currentStep === s.id
            const isCompleted = currentStep > s.id
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => goToStep(s.id)}
                className={`flex items-center gap-2 p-2 sm:p-3 rounded-xl text-left transition-all relative overflow-hidden select-none min-h-[46px] sm:min-h-[52px] ${
                  isActive
                    ? 'bg-primary text-primary-foreground shadow-sm ring-2 ring-primary/20 font-bold scale-[1.01]'
                    : isCompleted
                      ? 'bg-muted/60 hover:bg-muted/90 text-foreground font-semibold border border-border/80 cursor-pointer'
                      : 'bg-muted/30 hover:bg-muted/60 text-muted-foreground font-medium border border-transparent cursor-pointer'
                }`}
              >
                <div
                  className={`w-6 h-6 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center shrink-0 text-xs font-bold transition-all ${
                    isActive
                      ? 'bg-primary-foreground/20 text-primary-foreground'
                      : isCompleted
                        ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                        : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {isCompleted ? <Check className="w-3.5 h-3.5 sm:w-4 sm:h-4" /> : <StepIcon className="w-3.5 h-3.5 sm:w-4 sm:h-4" />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-[11px] sm:text-xs font-bold truncate">
                    B{s.id}: {s.title}
                  </div>
                  <div className={`text-[10px] hidden xs:block truncate ${isActive ? 'text-primary-foreground/80' : 'text-muted-foreground'}`}>
                    {s.sub}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.target as HTMLElement).tagName === 'INPUT') {
            e.preventDefault()
          }
        }}
        className="grid gap-6 lg:grid-cols-3 items-start"
      >
        {/* Active Step Content Card (2 spans) */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="shadow-xs rounded-2xl border-border/80 bg-card/90 backdrop-blur-sm overflow-hidden min-h-[480px] flex flex-col justify-between">
            {/* Step Header */}
            <CardHeader className="p-4 sm:p-6 pb-4 border-b border-border/40 bg-muted/20">
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2.5">
                  <span className="flex items-center justify-center w-7 h-7 rounded-xl bg-foreground text-background text-xs font-bold shadow-2xs">
                    {currentStep}
                  </span>
                  <div>
                    <CardTitle className="text-base sm:text-lg font-bold">
                      {WIZARD_STEPS[currentStep - 1].title}
                    </CardTitle>
                    <CardDescription className="text-xs">
                      {WIZARD_STEPS[currentStep - 1].sub}
                    </CardDescription>
                  </div>
                </div>
                <Badge variant="secondary" className="text-xs font-semibold text-muted-foreground bg-muted/60 border-border/60 px-2.5 py-1 shrink-0">
                  Bước {currentStep} / 4
                </Badge>
              </div>
            </CardHeader>

            {/* Step Body */}
            <CardContent className="p-4 sm:p-6 space-y-5 flex-1">
              {/* STEP 1: Chọn Mẫu NoteType & Thông tin mô tả */}
              {currentStep === 1 && (
                <div className="space-y-5 animate-in fade-in duration-200">
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
                          <span className="text-muted-foreground">Không có trường tùy biến</span>
                        )}
                        {templates.length > 0 ? (
                          templates.map((t, i) => (
                            <Badge key={i} variant="outline" className="text-[11px] bg-background border-primary/30 text-primary font-semibold">
                              Thẻ: {t.name}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-muted-foreground">Không có mẫu mặt thẻ</span>
                        )}
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
                      placeholder="Ví dụ: Mẫu thẻ Kanji đa tầng có Furigana & Audio, Thẻ Code Syntax Highlight..."
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

                  {/* Tags & Changelog in 2 columns */}
                  <div className="grid gap-4 sm:grid-cols-2 pt-2 border-t border-border/40">
                    <div className="space-y-1.5">
                      <Label htmlFor="nt-tags" className="text-xs font-semibold">Thẻ Tags (cách nhau dấu phẩy)</Label>
                      <Input
                        id="nt-tags"
                        placeholder="cloze, kanji, code..."
                        value={tags}
                        onChange={(e) => setTags(e.target.value)}
                        className="h-10 text-xs sm:text-sm rounded-xl"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="nt-changelog" className="text-xs font-semibold">Ghi chú phát hành (Changelog)</Label>
                      <Input
                        id="nt-changelog"
                        placeholder="Ví dụ: Hỗ trợ syntax highlight và audio tự động..."
                        value={changelog}
                        onChange={(e) => setChangelog(e.target.value)}
                        className="h-10 text-xs sm:text-sm rounded-xl"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* STEP 2: Phân loại Môn học & Trình độ */}
              {currentStep === 2 && (
                <div className="space-y-5 animate-in fade-in duration-200">
                  {/* Domain & Subject in 2 columns */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="nt-tax-domain" className="text-xs font-semibold">
                        Lĩnh vực học tập (Domain) <span className="text-destructive">*</span>
                      </Label>
                      <NativeSelect
                        id="nt-tax-domain"
                        value={taxonomyDomain}
                        onChange={(e) => {
                          const newDomain = e.target.value
                          setTaxonomyDomain(newDomain)
                          clearFieldError('taxonomyDomain')
                          const subs = taxonomySchema.subjectsByDomain(newDomain)
                          const newSub = subs.length > 0 ? subs[0].id : 'other'
                          setTaxonomySubject(newSub)
                          clearFieldError('taxonomySubject')

                          const nextFrameworks = taxonomySchema.frameworksForSubject(newSub)
                          if (nextFrameworks.length > 0) {
                            setTaxonomyFramework(nextFrameworks[0].id)
                            setTaxonomyFrameworkLevel('')
                          } else {
                            setTaxonomyFramework('')
                            setTaxonomyFrameworkLevel('')
                          }

                          setTaxonomyGoals(getDefaultGoalsForSubject(newSub))
                          setTaxonomyTopics(getDefaultTopicsForSubject(newSub))
                        }}
                        className={`h-10 text-xs sm:text-sm rounded-xl font-medium ${
                          fieldErrors.taxonomyDomain ? 'border-destructive bg-destructive/5' : ''
                        }`}
                      >
                        {availableDomains.map((d) => (
                          <NativeSelectOption key={d.id} value={d.id}>
                            {d.label}
                          </NativeSelectOption>
                        ))}
                      </NativeSelect>
                      <FieldErrorMessage error={fieldErrors.taxonomyDomain} />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="nt-tax-subject" className="text-xs font-semibold">
                        Ngôn ngữ / Môn học (Subject) <span className="text-destructive">*</span>
                      </Label>
                      <NativeSelect
                        id="nt-tax-subject"
                        value={taxonomySubject}
                        onChange={(e) => {
                          const newSub = e.target.value
                          setTaxonomySubject(newSub)
                          clearFieldError('taxonomySubject')
                          const nextFrameworks = taxonomySchema.frameworksForSubject(newSub)
                          if (nextFrameworks.length > 0) {
                            setTaxonomyFramework(nextFrameworks[0].id)
                            setTaxonomyFrameworkLevel('')
                          } else {
                            setTaxonomyFramework('')
                            setTaxonomyFrameworkLevel('')
                          }

                          setTaxonomyGoals(getDefaultGoalsForSubject(newSub))
                          setTaxonomyTopics(getDefaultTopicsForSubject(newSub))
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
                  </div>

                  {/* 1-Click Framework & Level Selection */}
                  {availableFrameworks.length > 0 && (
                    <div className="space-y-3.5 p-4 rounded-2xl bg-muted/30 border border-border/80">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div className="p-1 rounded-lg bg-muted text-foreground">
                            <Sparkles className="w-4 h-4" />
                          </div>
                          <div>
                            <Label className="text-xs font-bold text-foreground">
                              Khung chứng chỉ & Trình độ (Chọn nhanh 1 chạm)
                            </Label>
                            <p className="text-[11px] text-muted-foreground">
                              Tự động điền độ khó và thẻ tìm kiếm
                            </p>
                          </div>
                        </div>
                        {taxonomyFrameworkLevel && (
                          <button
                            type="button"
                            onClick={() => setTaxonomyFrameworkLevel('')}
                            className="text-xs text-muted-foreground hover:text-foreground font-medium underline transition-colors"
                          >
                            Bỏ chọn
                          </button>
                        )}
                      </div>

                      {/* Framework Tabs */}
                      {availableFrameworks.length > 1 && (
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          {availableFrameworks.map((fw) => {
                            const isFwActive = activeFramework?.id === fw.id
                            return (
                              <Button
                                key={fw.id}
                                type="button"
                                size="sm"
                                variant={isFwActive ? 'default' : 'outline'}
                                className={`h-8 px-3.5 text-xs rounded-xl font-semibold transition-all ${
                                  isFwActive
                                    ? 'bg-foreground text-background shadow-xs'
                                    : 'bg-card hover:bg-muted text-muted-foreground'
                                }`}
                                onClick={() => setTaxonomyFramework(fw.id)}
                              >
                                {fw.label}
                              </Button>
                            )
                          })}
                        </div>
                      )}

                      {/* Level Cards */}
                      {activeFramework && (
                        <div className="space-y-2 pt-1">
                          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                            {activeFramework.levels.map((lvl) => {
                              const isSelected = taxonomyFrameworkLevel === lvl.id
                              return (
                                <div
                                  key={lvl.id}
                                  onClick={() => {
                                    setTaxonomyFramework(activeFramework.id)
                                    setTaxonomyFrameworkLevel(lvl.id)
                                    setTaxonomyDifficulty(lvl.difficulty_band)
                                    clearFieldError('taxonomyDifficulty')

                                    if (lvl.suggestedTags && lvl.suggestedTags.length > 0) {
                                      setTags((prev) => {
                                        const currentList = prev.split(',').map((t) => t.trim()).filter(Boolean)
                                        const merged = Array.from(new Set([...currentList, ...(lvl.suggestedTags || [])]))
                                        return merged.join(', ')
                                      })
                                    }
                                  }}
                                  className={`p-2.5 rounded-xl border text-xs font-medium cursor-pointer transition-all flex items-center justify-between select-none ${
                                    isSelected
                                      ? 'bg-card border-primary text-foreground font-bold shadow-xs ring-1 ring-primary/30 scale-[1.01]'
                                      : 'bg-card hover:bg-muted/70 text-foreground border-border/80'
                                  }`}
                                >
                                  <span className="truncate">{lvl.label}</span>
                                  {isSelected && <Check className="w-3.5 h-3.5 text-primary shrink-0 ml-1" />}
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Difficulty & Category in 2 columns */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="nt-tax-diff" className="text-xs font-semibold">
                        Mức độ khó (Difficulty) <span className="text-destructive">*</span>
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

                    <div className="space-y-2">
                      <Label htmlFor="nt-category" className="text-xs font-semibold">
                        Danh mục mẫu thẻ
                      </Label>
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
                </div>
              )}

              {/* STEP 3: Mục tiêu học tập & Kỹ năng trọng tâm */}
              {currentStep === 3 && (
                <div className="space-y-6 animate-in fade-in duration-200">
                  {/* Contextual Subject Banner */}
                  <div className="flex items-center justify-between p-3.5 rounded-xl border border-border/80 bg-muted/30 text-xs">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-muted-foreground shrink-0" />
                      <div>
                        <span className="text-muted-foreground">Môn học đang chọn: </span>
                        <strong className="text-foreground">
                          {availableSubjects.find((s) => s.id === taxonomySubject)?.label || taxonomySubject}
                        </strong>
                      </div>
                    </div>
                    <Badge variant="secondary" className="text-[10px] bg-card border-border/80 text-foreground font-semibold">
                      {availableDomains.find((d) => d.id === taxonomyDomain)?.label.split('(')[0].trim() || 'Lĩnh vực'}
                    </Badge>
                  </div>

                  {/* Learning Goals */}
                  <div className="space-y-2.5">
                    <div className="flex items-center justify-between">
                      <div>
                        <Label className="text-xs font-bold text-foreground flex items-center gap-1.5">
                          <span>Mục tiêu học tập (Learning Goals)</span>
                          <span className="text-destructive">*</span>
                        </Label>
                        <p className="text-[11px] text-muted-foreground">
                          Chọn các mục tiêu mẫu thẻ này hỗ trợ tốt nhất
                        </p>
                      </div>
                      <Badge variant="secondary" className="text-[10px] font-mono shrink-0">
                        Đã chọn: {taxonomyGoals.length}
                      </Badge>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                      {availableGoals.map((g) => {
                        const isSelected = taxonomyGoals.includes(g.id)
                        return (
                          <div
                            key={g.id}
                            onClick={() => {
                              clearFieldError('taxonomyGoals')
                              setTaxonomyGoals((prev) =>
                                isSelected ? prev.filter((id) => id !== g.id) : [...prev, g.id]
                              )
                            }}
                            className={`p-3 rounded-xl border transition-all cursor-pointer select-none flex flex-col justify-between gap-1 min-h-[56px] ${
                              isSelected
                                ? 'bg-card border-primary text-foreground font-semibold shadow-xs ring-1 ring-primary/30'
                                : 'bg-card border-border/70 text-muted-foreground hover:text-foreground hover:border-border hover:bg-muted/30'
                            }`}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-xs font-semibold leading-tight text-foreground">{g.label}</span>
                              {isSelected ? (
                                <CheckCircle2 className="w-4 h-4 text-primary shrink-0" />
                              ) : (
                                <div className="w-4 h-4 rounded-full border border-border shrink-0" />
                              )}
                            </div>
                            {g.sub && (
                              <span className="text-[10px] font-normal leading-tight text-muted-foreground">
                                {g.sub}
                              </span>
                            )}
                          </div>
                        )
                      })}
                    </div>
                    <FieldErrorMessage error={fieldErrors.taxonomyGoals} />
                  </div>

                  {/* Primary Topics */}
                  <div className="space-y-2.5 pt-4 border-t border-border/40">
                    <div className="flex items-center justify-between">
                      <div>
                        <Label className="text-xs font-bold text-foreground flex items-center gap-1.5">
                          <span>Chủ đề chính liên kết (Primary Topics)</span>
                          <span className="text-destructive">*</span>
                        </Label>
                        <p className="text-[11px] text-muted-foreground">
                          Chủ đề được tối ưu hóa riêng theo môn học <strong>{availableSubjects.find((s) => s.id === taxonomySubject)?.label || taxonomySubject}</strong>
                        </p>
                      </div>
                      <Badge variant="secondary" className="text-[10px] font-mono shrink-0">
                        Đã chọn: {taxonomyTopics.length}
                      </Badge>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                      {availableTopics.map((t) => {
                        const isSelected = taxonomyTopics.includes(t.id)
                        return (
                          <div
                            key={t.id}
                            onClick={() => {
                              clearFieldError('taxonomyTopics')
                              setTaxonomyTopics((prev) =>
                                isSelected ? prev.filter((id) => id !== t.id) : [...prev, t.id]
                              )
                            }}
                            className={`p-3 rounded-xl border transition-all cursor-pointer select-none flex flex-col justify-between gap-1 min-h-[56px] ${
                              isSelected
                                ? 'bg-card border-primary text-foreground font-semibold shadow-xs ring-1 ring-primary/30'
                                : 'bg-card border-border/70 text-muted-foreground hover:text-foreground hover:border-border hover:bg-muted/30'
                            }`}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-xs font-semibold leading-tight text-foreground">{t.label}</span>
                              {isSelected ? (
                                <CheckCircle2 className="w-4 h-4 text-primary shrink-0" />
                              ) : (
                                <div className="w-4 h-4 rounded-full border border-border shrink-0" />
                              )}
                            </div>
                            {t.sub && (
                              <span className="text-[10px] font-normal leading-tight text-muted-foreground">
                                {t.sub}
                              </span>
                            )}
                          </div>
                        )
                      })}
                    </div>
                    <FieldErrorMessage error={fieldErrors.taxonomyTopics} />
                  </div>
                </div>
              )}

              {/* STEP 4: Giá bán & Xác nhận */}
              {currentStep === 4 && (
                <div className="space-y-5 animate-in fade-in duration-200">
                  {/* Pricing Selector Cards */}
                  <div className="space-y-2">
                    <Label className="text-xs font-semibold">Mô hình phân phối & Giá bán</Label>
                    <div className="grid grid-cols-2 gap-3">
                      <div
                        onClick={() => setPricingMode('free')}
                        className={`p-4 rounded-xl border cursor-pointer transition-all text-center select-none ${
                          pricingMode === 'free'
                            ? 'border-primary bg-primary/10 text-foreground font-bold ring-2 ring-primary/30'
                            : 'border-border bg-card hover:bg-muted/50 text-muted-foreground'
                        }`}
                      >
                        <div className="font-bold text-sm sm:text-base">Miễn phí (Free)</div>
                        <div className="text-xs opacity-80 mt-0.5">Chia sẻ tự do tới mọi người</div>
                      </div>

                      <div
                        onClick={() => setPricingMode('paid')}
                        className={`p-4 rounded-xl border cursor-pointer transition-all text-center select-none ${
                          pricingMode === 'paid'
                            ? 'border-primary bg-primary/10 text-foreground font-bold ring-2 ring-primary/30'
                            : 'border-border bg-card hover:bg-muted/50 text-muted-foreground'
                        }`}
                      >
                        <div className="font-bold text-sm sm:text-base">Có phí (Paid)</div>
                        <div className="text-xs opacity-80 mt-0.5">Nhận thu nhập qua payOS</div>
                      </div>
                    </div>

                    {pricingMode === 'paid' && (
                      <div className="space-y-1.5 animate-in fade-in duration-200">
                        <Label htmlFor="nt-price" className="text-xs font-semibold">
                          Giá bán niêm yết (VNĐ) <span className="text-destructive">*</span>
                        </Label>
                        <div className="relative">
                          <Input
                            id="nt-price"
                            type="number"
                            min="1000"
                            step="1000"
                            value={priceAmountMinor || ''}
                            onChange={(e) => {
                              setPriceAmountMinor(Number(e.target.value))
                              clearFieldError('priceAmountMinor')
                            }}
                            className={`h-11 sm:h-10 text-sm rounded-xl pr-14 font-mono font-semibold ${
                              fieldErrors.priceAmountMinor ? 'border-destructive bg-destructive/5' : ''
                            }`}
                          />
                          <span className="absolute right-3.5 top-1/2 -translate-y-1/2 text-xs text-muted-foreground font-bold">
                            VND
                          </span>
                        </div>
                        <FieldErrorMessage error={fieldErrors.priceAmountMinor} />
                      </div>
                    )}
                  </div>

                  {/* Version */}
                  <div className="space-y-1.5">
                    <Label htmlFor="nt-version" className="text-xs font-semibold">Phiên bản phát hành</Label>
                    <Input
                      id="nt-version"
                      value={version}
                      onChange={(e) => setVersion(e.target.value)}
                      className="h-10 text-xs sm:text-sm rounded-xl font-mono"
                    />
                  </div>

                  {/* Summary Checklist before Submit */}
                  <div className="p-4 rounded-xl border border-border/80 bg-muted/30 space-y-2.5 text-xs">
                    <div className="font-bold text-foreground flex items-center gap-1.5">
                      <Sparkles className="w-4 h-4 text-muted-foreground" />
                      <span>Tóm tắt thông tin xuất bản NoteType:</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-muted-foreground">
                      <div>Tiêu đề: <strong className="text-foreground">{title || 'Chưa đặt'}</strong></div>
                      <div>Môn học: <strong className="text-foreground">{availableSubjects.find(s => s.id === taxonomySubject)?.label || taxonomySubject}</strong></div>
                      <div>Danh mục: <strong className="text-foreground">{effectiveCategory}</strong></div>
                      <div>Mô hình: <strong className="text-foreground">{pricingMode === 'paid' ? `${priceAmountMinor.toLocaleString('vi-VN')} đ` : 'Miễn phí'}</strong></div>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>

            {/* Step Navigation Actions Footer */}
            <div className="p-4 sm:p-6 border-t border-border/40 bg-muted/10 flex items-center justify-between gap-3">
              <Button
                type="button"
                variant="outline"
                size="default"
                onClick={handlePrevStep}
                disabled={currentStep === 1}
                className="h-11 sm:h-10 px-4 text-xs font-semibold rounded-xl shrink-0"
              >
                <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
                Quay lại
              </Button>

              <div className="text-xs text-muted-foreground font-medium hidden sm:block">
                Bước <strong className="text-foreground">{currentStep}</strong> / 4: {WIZARD_STEPS[currentStep - 1].title}
              </div>

              {currentStep < 4 ? (
                <Button
                  type="button"
                  size="default"
                  onClick={handleNextStep}
                  className="h-11 sm:h-10 px-5 text-xs font-bold rounded-xl bg-primary text-primary-foreground shadow-sm hover:bg-primary/90 transition-all cursor-pointer flex-1 sm:flex-initial justify-center"
                >
                  <span>Tiếp tục (Bước {currentStep + 1})</span>
                  <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                </Button>
              ) : (
                <Button
                  type="button"
                  size="default"
                  onClick={handlePublish}
                  disabled={isSelectedInstalledCopy || isSelectedAlreadyPublished || publishMutation.isPending}
                  className="h-11 sm:h-10 px-6 text-xs font-bold rounded-xl bg-primary text-primary-foreground shadow-md hover:bg-primary/90 transition-all cursor-pointer flex-1 sm:flex-initial justify-center"
                >
                  <CheckCircle2 className="w-4 h-4 mr-1.5" />
                  <span>
                    {isSelectedInstalledCopy 
                      ? 'Bản cài Marketplace (Không thể xuất bản)' 
                      : isSelectedAlreadyPublished 
                        ? 'Đã xuất bản (Bấm Chỉnh sửa ở trên)' 
                        : publishMutation.isPending 
                          ? 'Đang lưu…' 
                          : isEditMode 
                            ? 'Cập nhật cấu hình chia sẻ' 
                            : 'Xuất bản Loại thẻ ngay'}
                  </span>
                </Button>
              )}
            </div>
          </Card>
        </div>

        {/* Sidebar Column: Live Preview & Progress Checklist (1 span) */}
        <div className="lg:col-span-1 space-y-6 lg:sticky lg:top-6 self-start">
          {/* Live Marketplace Card Preview */}
          <Card className="shadow-xs rounded-2xl border-border/80 bg-card/90 overflow-hidden">
            <CardHeader className="p-4 sm:p-5 pb-2 border-b border-border/40 bg-muted/20">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs font-bold text-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-muted-foreground" />
                  <span>Xem trước Marketplace</span>
                </CardTitle>
                <Badge variant="secondary" className="text-[10px]">
                  Live Card
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="p-4 sm:p-5 space-y-3">
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
                  <Badge variant="secondary" className="text-[10px] bg-muted/60 text-foreground border-border/60 font-semibold">
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
            </CardContent>
          </Card>

          {/* Step Progress Checklist (Desktop only - mobile already has top Stepper) */}
          <Card className="hidden lg:block shadow-xs rounded-2xl border-border/80 bg-card/90 backdrop-blur-sm overflow-hidden">
            <CardHeader className="p-4 sm:p-5 pb-3 border-b border-border/40 bg-muted/20">
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Tiến trình hoàn thiện
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 sm:p-5 space-y-2.5 text-xs">
              {WIZARD_STEPS.map((s) => {
                const isCurrent = currentStep === s.id
                const isDone = currentStep > s.id
                return (
                  <div
                    key={s.id}
                    onClick={() => goToStep(s.id)}
                    className={`p-2.5 rounded-xl border flex items-center justify-between cursor-pointer transition-all ${
                      isCurrent
                        ? 'border-primary/50 bg-primary/5 font-semibold text-foreground ring-1 ring-primary/20'
                        : isDone
                          ? 'border-border/60 bg-card hover:bg-muted/40 font-medium text-muted-foreground'
                          : 'border-border/40 bg-muted/20 text-muted-foreground'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div
                        className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                          isDone
                            ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                            : isCurrent
                              ? 'bg-primary/20 text-primary'
                              : 'bg-muted text-muted-foreground'
                        }`}
                      >
                        {isDone ? <Check className="w-3 h-3" /> : s.id}
                      </div>
                      <span>{s.title}</span>
                    </div>
                    {isDone && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />}
                  </div>
                )
              })}
            </CardContent>
          </Card>
        </div>
      </form>
    </Page>
  )
}
