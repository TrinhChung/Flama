import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { AlertCircle, Check } from 'lucide-react'
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
import { PublishDeckTree } from '../components/PublishDeckTree'
import { loadDeckOptionsForPublish, type PublishDeckOption } from '../publishApi'


import {
  CATEGORY_PRESETS,
  TAXONOMY_DOMAINS,
  TAXONOMY_SUBJECTS,
  TAXONOMY_DIFFICULTIES,
  TAXONOMY_LEARNING_GOALS,
  TAXONOMY_TOPICS
} from '../utils/publishTaxonomyConstants'


function FieldErrorMessage({ error }: { error?: string }) {
  if (!error) return null
  return (
    <p className="text-xs font-semibold text-destructive mt-1.5 flex items-center gap-1.5 animate-in fade-in">
      <AlertCircle className="w-3.5 h-3.5 shrink-0" />
      <span>{error}</span>
    </p>
  )
}


export function MarketplacePublishDeckPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryParamDeckId = searchParams.get('deck_id') || searchParams.get('id') || searchParams.get('source_deck_id') || ''

  const [sourceDeckId, setSourceDeckId] = useState<string>(queryParamDeckId)
  const [title, setTitle] = useState('')
  const [previewText, setPreviewText] = useState('')
  const [description, setDescription] = useState('')
  const [pricingMode, setPricingMode] = useState<'free' | 'paid'>('free')
  const [priceAmountMinor, setPriceAmountMinor] = useState<number>(10000)
  const [version, setVersion] = useState('1.0.0')
  const [tags, setTags] = useState('')
  const [changelog, setChangelog] = useState('')
  const [primaryCategory, setPrimaryCategory] = useState('General')
  const [customCategory, setCustomCategory] = useState('')
  const [subcategory, setSubcategory] = useState('')
  const [targetAudience, setTargetAudience] = useState('')

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

  const decksQuery = useQuery({
    queryKey: ['my-decks-for-publish'],
    queryFn: loadDeckOptionsForPublish,
  })

  const effectiveCategory = primaryCategory === 'Custom' ? customCategory.trim() || 'Khác' : primaryCategory

  const publishMutation = useMutation({
    mutationFn: () =>
      appApi.mutate('/api/shared/decks', 'POST', {
        source_deck_id: Number(sourceDeckId),
        title: title.trim(),
        preview_text: previewText.trim(),
        description: description.trim(),
        pricing_mode: pricingMode,
        price_amount_minor: pricingMode === 'paid' ? priceAmountMinor : 0,
        version: version.trim() || '1.0.0',
        tags: tags ? tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
        changelog: changelog.trim(),
        primary_category: effectiveCategory,
        subcategory: subcategory.trim(),
        target_audience: targetAudience.trim(),
        taxonomy_domain: taxonomyDomain,
        taxonomy_subject: taxonomySubject,
        taxonomy_difficulty_band: taxonomyDifficulty,
        taxonomy_learning_goals: taxonomyGoals,
        taxonomy_primary_topics: taxonomyTopics,
        publish_status: 'published',
      }),
    onSuccess: (data: any) => {
      toast.success('Đã xuất bản bộ thẻ lên Marketplace thành công!')
      navigate(`/marketplace/decks/${data.id || ''}`)
    },
    onError: (error: any) => {
      const msg = error?.message || ''
      const field = error?.field || ''
      const serverErrs: Record<string, string> = {}

      if (field === 'source_deck_id' || msg.includes('source_deck_id')) {
        serverErrs.sourceDeckId = msg || 'Vui lòng chọn bộ thẻ từ tài khoản của bạn.'
      }
      if (field === 'title' || msg.includes('Title')) {
        serverErrs.title = 'Vui lòng nhập tiêu đề xuất bản.'
      }
      if (field === 'description' || msg.includes('Description')) {
        serverErrs.description = 'Vui lòng nhập mô tả chi tiết học liệu.'
      }
      if (field === 'preview_text' || msg.includes('Preview text')) {
        serverErrs.previewText = 'Vui lòng nhập tóm tắt xem trước ngắn (Preview Text).'
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
    const selectedSourceDeck = decks.find((deck) => String(deck.id) === sourceDeckId)
    if (!sourceDeckId || !selectedSourceDeck) {
      errs.sourceDeckId = 'Vui lòng chọn bộ thẻ cần chia sẻ từ tài khoản của bạn.'
    } else if (!selectedSourceDeck.is_selectable) {
      errs.sourceDeckId = selectedSourceDeck.block_reason || 'Bộ thẻ này không thể chia sẻ.'
    }
    if (!title.trim()) {
      errs.title = 'Vui lòng nhập tiêu đề xuất bản.'
    }
    if (!previewText.trim()) {
      errs.previewText = 'Vui lòng nhập tóm tắt xem trước ngắn (Preview Text) để người học xem nhanh.'
    }
    if (!description.trim()) {
      errs.description = 'Vui lòng nhập mô tả chi tiết giới thiệu học liệu.'
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
      errs.taxonomyGoals = 'Vui lòng chọn ít nhất 1 Mục tiêu học tập (bấm vào các ô màu bên dưới).'
    }
    if (taxonomyTopics.length === 0) {
      errs.taxonomyTopics = 'Vui lòng chọn ít nhất 1 Chủ đề chính (bấm vào các ô màu bên dưới).'
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

  const decks = useMemo(() => decksQuery.data?.items || [], [decksQuery.data?.items])

  // Sync search param ID if passed in URL
  useEffect(() => {
    if (!queryParamDeckId || sourceDeckId || decks.length === 0) return
    const queryDeck = decks.find((deck) => String(deck.id) === queryParamDeckId)
    if (queryDeck?.is_selectable) {
      setSourceDeckId(queryParamDeckId)
      return
    }
    if (queryDeck) {
      setFieldErrors((current) => ({
        ...current,
        sourceDeckId: queryDeck.block_reason || 'Bộ thẻ này không thể chia sẻ.',
      }))
    }
  }, [decks, queryParamDeckId, sourceDeckId])

  useEffect(() => {
    if (!sourceDeckId || decks.length === 0) return
    const found = decks.find((deck) => String(deck.id) === sourceDeckId)
    if (!found || found.is_selectable) return
    setSourceDeckId('')
    setFieldErrors((current) => ({
      ...current,
      sourceDeckId: found.block_reason || 'Bộ thẻ này không thể chia sẻ.',
    }))
  }, [decks, sourceDeckId])

  // Auto set title if title is empty when selected deck changes
  useEffect(() => {
    if (sourceDeckId && decks.length > 0 && !title) {
      const found = decks.find((d) => String(d.id) === sourceDeckId)
      if (found?.is_selectable) {
        setTitle(found.name)
      }
    }
  }, [decks, sourceDeckId, title])

  if (decksQuery.isPending) return <PageLoading label="Đang tải danh sách bộ thẻ của bạn…" />
  if (decksQuery.error) return <Page><PageError error={decksQuery.error} /></Page>

  const selectedDeck = decks.find((d) => String(d.id) === sourceDeckId)
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
                Flama Creator Hub
              </Badge>
              <Badge variant="secondary" className="text-[11px] font-medium">
                Đa môn học & Lĩnh vực
              </Badge>
            </div>
            <h1 className="text-xl sm:text-2xl md:text-3xl font-black tracking-tight text-foreground">
              Chia sẻ Bộ thẻ vào Marketplace
            </h1>
            <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed max-w-3xl">
              Đóng gói và phát hành học liệu Flashcard của bạn tới cộng đồng người học toàn quốc. Hỗ trợ mọi môn học từ Ngoại ngữ, CNTT, Y dược tới Thường thức.
            </p>
          </div>

          <Button variant="outline" asChild className="h-9 px-3.5 text-xs font-semibold rounded-xl shrink-0 self-start sm:self-center">
            <Link to="/marketplace/decks">
              Quay lại Marketplace
            </Link>
          </Button>
        </div>
      </div>

      {/* Global Form Validation Warning Alert */}
      {Object.keys(fieldErrors).length > 0 && (
        <div className="rounded-2xl border border-destructive/40 bg-destructive/10 p-4 sm:p-5 flex items-start gap-3.5 animate-in fade-in duration-200">
          <AlertCircle className="w-5 h-5 text-destructive shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs sm:text-sm">
            <div className="font-bold text-destructive">
              Thông tin đăng tải chưa hoàn thiện ({Object.keys(fieldErrors).length} vị trí bị thiếu)
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
                1. Chọn Học liệu & Thông tin hiển thị
              </CardTitle>
              <CardDescription className="text-xs">
                Chọn bộ thẻ cá nhân và cung cấp các thông tin giới thiệu thu hút người học.
              </CardDescription>
            </CardHeader>

            <CardContent className="p-4 sm:p-6 space-y-5">
              {/* Select Source Deck */}
              <div className="space-y-2">
                <Label className="text-xs font-semibold flex items-center justify-between">
                  <span>Chọn Bộ thẻ cần chia sẻ <span className="text-destructive">*</span></span>
                </Label>
                <PublishDeckTree
                  decks={decks}
                  selectedDeckId={sourceDeckId}
                  onSelectDeck={(deck: PublishDeckOption) => {
                    setSourceDeckId(String(deck.id))
                    clearFieldError('sourceDeckId')
                    if (!title) setTitle(deck.name)
                  }}
                />
                <p className="text-[11px] leading-relaxed text-muted-foreground">
                  Chỉ bộ thẻ do bạn tự tạo hoặc đồng bộ từ Anki mới có thể chia sẻ. Bộ thẻ cài từ Marketplace,
                  bộ đã chia sẻ và bộ con nằm trong một bộ cha đã chia sẻ sẽ bị khóa.
                </p>
                <FieldErrorMessage error={fieldErrors.sourceDeckId} />
              </div>

              {/* Listing Title */}
              <div className="space-y-2">
                <Label htmlFor="title" className="text-xs font-semibold flex items-center justify-between">
                  <span>Tiêu đề xuất bản (Listing Title) <span className="text-destructive">*</span></span>
                </Label>
                <Input
                  id="title"
                  placeholder="Ví dụ: 1000 Từ vựng IELTS 7.0+, N3 Kanji Luyện đọc, hay ReactJS Essentials"
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
                <Label htmlFor="preview" className="text-xs font-semibold flex items-center justify-between">
                  <span>Mô tả ngắn xem trước (Preview Text) <span className="text-destructive">*</span></span>
                </Label>
                <Input
                  id="preview"
                  placeholder="1 dòng mô tả tóm tắt điểm nổi bật để người học xem nhanh trên danh sách"
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

              {/* Detailed Description */}
              <div className="space-y-2">
                <Label htmlFor="description" className="text-xs font-semibold flex items-center justify-between">
                  <span>Mô tả chi tiết học liệu <span className="text-destructive">*</span></span>
                </Label>
                <Textarea
                  id="description"
                  rows={6}
                  placeholder="Giới thiệu mục tiêu bài học, đối tượng phù hợp, cấu trúc thẻ, hướng dẫn ôn tập và lý do nên sử dụng bộ thẻ này…"
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

              {/* Pricing Selector Cards */}
              <div className="space-y-2 pt-2 border-t border-border/40">
                <Label className="text-xs font-semibold">Mô hình phân phối & Giá bán</Label>
                <div className="grid grid-cols-2 gap-3">
                  <div
                    onClick={() => setPricingMode('free')}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                      pricingMode === 'free'
                        ? 'border-emerald-500 bg-emerald-500/10 shadow-xs font-bold'
                        : 'border-border bg-card hover:bg-muted/40'
                    }`}
                  >
                    <div className="font-bold text-xs sm:text-sm">Miễn phí (Free)</div>
                    <div className="text-[11px] text-muted-foreground">Chia sẻ tự do</div>
                  </div>

                  <div
                    onClick={() => setPricingMode('paid')}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                      pricingMode === 'paid'
                        ? 'border-amber-500 bg-amber-500/10 shadow-xs font-bold'
                        : 'border-border bg-card hover:bg-muted/40'
                    }`}
                  >
                    <div className="font-bold text-xs sm:text-sm">Trả phí (Paid)</div>
                    <div className="text-[11px] text-muted-foreground">Đặt giá niêm yết</div>
                  </div>
                </div>

                {pricingMode === 'paid' && (
                  <div className="pt-2 space-y-1.5 animate-in fade-in duration-200">
                    <Label htmlFor="price" className="text-xs font-semibold">Giá bán niêm yết (VND)</Label>
                    <div className="relative">
                      <Input
                        id="price"
                        type="number"
                        min={1000}
                        step={1000}
                        value={priceAmountMinor}
                        onChange={(e) => {
                          setPriceAmountMinor(Number(e.target.value))
                          clearFieldError('priceAmountMinor')
                        }}
                        className={`h-10 text-xs sm:text-sm rounded-xl font-bold pr-16 ${
                          fieldErrors.priceAmountMinor ? 'border-destructive bg-destructive/5' : ''
                        }`}
                      />
                      <span className="absolute right-3.5 top-1/2 -translate-y-1/2 text-xs font-bold text-muted-foreground">VND</span>
                    </div>
                    <FieldErrorMessage error={fieldErrors.priceAmountMinor} />
                  </div>
                )}
              </div>

              {/* Version & Tags */}
              <div className="grid gap-4 sm:grid-cols-2 pt-2 border-t border-border/40">
                <div className="space-y-1.5">
                  <Label htmlFor="version" className="text-xs font-semibold">Phiên bản (Version)</Label>
                  <Input
                    id="version"
                    value={version}
                    onChange={(e) => setVersion(e.target.value)}
                    className="h-10 text-xs sm:text-sm rounded-xl font-mono"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="tags" className="text-xs font-semibold">Thẻ Tags (cách bởi dấu phẩy)</Label>
                  <Input
                    id="tags"
                    placeholder="ielts, english, vocabulary, kanji, react..."
                    value={tags}
                    onChange={(e) => setTags(e.target.value)}
                    className="h-10 text-xs sm:text-sm rounded-xl"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="changelog" className="text-xs font-semibold">Nhật ký thay đổi (Changelog)</Label>
                <Textarea
                  id="changelog"
                  rows={2}
                  placeholder="Ghi chú nội dung cập nhật mới nhất cho phiên bản này…"
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
          {/* Category & Metadata Selection */}
          <Card className="shadow-xs rounded-2xl border-border/80 bg-card/90 backdrop-blur-sm overflow-hidden">
            <CardHeader className="p-4 sm:p-5 pb-3 border-b border-border/40 bg-muted/20">
              <CardTitle className="text-base font-bold">
                2. Phân loại Môn học & Taxonomy
              </CardTitle>
              <CardDescription className="text-xs">
                Giúp hệ thống phân loại chính xác tài liệu để người học dễ dàng tìm kiếm.
              </CardDescription>
            </CardHeader>

            <CardContent className="p-4 sm:p-5 space-y-4">
              {/* Category Quick Presets */}
              <div className="space-y-2">
                <Label htmlFor="primary-category" className="text-xs font-semibold">Danh mục chính</Label>
                <NativeSelect
                  id="primary-category"
                  value={primaryCategory}
                  onChange={(e) => setPrimaryCategory(e.target.value)}
                  className="h-10 text-xs sm:text-sm rounded-xl font-medium"
                >
                  {CATEGORY_PRESETS.map((cat) => (
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
                    placeholder="Ví dụ: Âm nhạc, Đố vui, Lịch sử..."
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
                <Label htmlFor="tax-domain" className="text-xs font-semibold flex items-center justify-between">
                  <span>Lĩnh vực học tập (Domain) <span className="text-destructive">*</span></span>
                </Label>
                <NativeSelect
                  id="tax-domain"
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
                <Label htmlFor="tax-subject" className="text-xs font-semibold flex items-center justify-between">
                  <span>Ngôn ngữ / Môn học (Subject) <span className="text-destructive">*</span></span>
                </Label>
                <NativeSelect
                  id="tax-subject"
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
                <Label htmlFor="tax-diff" className="text-xs font-semibold flex items-center justify-between">
                  <span>Trình độ / Mức độ khó (Difficulty) <span className="text-destructive">*</span></span>
                </Label>
                <NativeSelect
                  id="tax-diff"
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

              <div className="space-y-1.5 pt-2 border-t border-border/40">
                <Label htmlFor="subcategory" className="text-xs font-semibold">Trình độ chi tiết (Ví dụ: N3, IELTS 6.5)</Label>
                <Input
                  id="subcategory"
                  placeholder="Ví dụ: N3, IELTS 6.5, HSK4, ReactJS..."
                  value={subcategory}
                  onChange={(e) => setSubcategory(e.target.value)}
                  className="h-10 text-xs sm:text-sm rounded-xl"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="target-audience" className="text-xs font-semibold">Đối tượng phù hợp</Label>
                <Input
                  id="target-audience"
                  placeholder="Ví dụ: Người mới bắt đầu, Sinh viên IT, Người đi làm..."
                  value={targetAudience}
                  onChange={(e) => setTargetAudience(e.target.value)}
                  className="h-10 text-xs sm:text-sm rounded-xl"
                />
              </div>
            </CardContent>
          </Card>

          {/* Realtime Live Marketplace Preview Card */}
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
                      {title.trim() || 'Tiêu đề bộ thẻ của bạn'}
                    </div>
                    <div className="text-xs text-muted-foreground line-clamp-2">
                      {previewText.trim() || 'Mô tả ngắn hiển thị tại đây khi người học tìm kiếm tài liệu...'}
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
                  {subcategory && (
                    <Badge variant="outline" className="text-[10px] font-medium">
                      {subcategory}
                    </Badge>
                  )}
                  {selectedDeck?.card_count ? (
                    <Badge variant="outline" className="text-[10px] text-muted-foreground">
                      {selectedDeck.card_count} thẻ
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
                  disabled={publishMutation.isPending}
                >
                  {publishMutation.isPending ? 'Đang xuất bản…' : 'Xuất bản Bộ thẻ ngay'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </form>
    </Page>
  )
}

