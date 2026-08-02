import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
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
import { PageLoading } from '@/shared/components/PageState'

type SimpleDeck = {
  id: number
  name: string
  card_count?: number
}

type SimpleNoteType = {
  id: string
  name: string
  field_count?: number
}

const CATEGORY_PRESETS = [
  { id: 'General', label: 'Tổng hợp', sub: 'Thường thức, đố vui, tổng hợp' },
  { id: 'Japanese', label: 'Tiếng Nhật', sub: 'JLPT, Kanji, Kaiwa, Từ vựng' },
  { id: 'English', label: 'Tiếng Anh', sub: 'IELTS, TOEIC, TOEFL, Giao tiếp' },
  { id: 'Chinese', label: 'Tiếng Trung', sub: 'HSK, Chữ Hán, Giao tiếp' },
  { id: 'Korean', label: 'Tiếng Hàn', sub: 'TOPIK, Từ vựng, Ngữ pháp' },
  { id: 'IT', label: 'Công nghệ & IT', sub: 'Lập trình, Web, Mobile, DevOps' },
  { id: 'Certification', label: 'Chứng chỉ', sub: 'AWS, PMP, GMAT, Thi công chức' },
  { id: 'Academic', label: 'Học thuật', sub: 'Y dược, Toán, Lý, Hóa, Luật' },
  { id: 'Custom', label: 'Tùy chỉnh', sub: 'Nhập tên danh mục riêng' },
]

export function MarketplacePublishDeckPage() {
  const navigate = useNavigate()
  const [sourceDeckId, setSourceDeckId] = useState<string>('')
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

  const decksQuery = useQuery({
    queryKey: ['my-decks-for-publish'],
    queryFn: () => appApi.get<{ items: SimpleDeck[] }>('/decks'),
  })

  const effectiveCategory = primaryCategory === 'Custom' ? customCategory.trim() || 'Khác' : primaryCategory

  const publishMutation = useMutation({
    mutationFn: () =>
      appApi.mutate('/api/shared/decks', 'POST', {
        source_deck_id: Number(sourceDeckId),
        title,
        preview_text: previewText,
        description,
        pricing_mode: pricingMode,
        price_amount_minor: pricingMode === 'paid' ? priceAmountMinor : 0,
        version,
        tags: tags ? tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
        changelog,
        primary_category: effectiveCategory,
        subcategory,
        target_audience: targetAudience,
      }),
    onSuccess: (data: any) => {
      toast.success('Đã xuất bản bộ thẻ lên Marketplace thành công!')
      navigate(`/marketplace/decks/${data.id || ''}`)
    },
    onError: (error: Error) => toast.error(error.message),
  })

  if (decksQuery.isPending) return <PageLoading label="Đang tải danh sách bộ thẻ của bạn…" />

  const decks = decksQuery.data?.items || []
  const selectedDeck = decks.find((d) => String(d.id) === sourceDeckId)

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

      <form
        onSubmit={(e) => {
          e.preventDefault()
          publishMutation.mutate()
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
                <Label htmlFor="source-deck" className="text-xs font-semibold">
                  Chọn Bộ thẻ cần chia sẻ <span className="text-destructive">*</span>
                </Label>
                <NativeSelect
                  id="source-deck"
                  value={sourceDeckId}
                  onChange={(e) => {
                    setSourceDeckId(e.target.value)
                    const found = decks.find((d) => String(d.id) === e.target.value)
                    if (found && !title) setTitle(found.name)
                  }}
                  className="h-10 text-xs sm:text-sm rounded-xl font-medium"
                  required
                >
                  <NativeSelectOption value="">-- Chọn bộ thẻ từ tài khoản của bạn --</NativeSelectOption>
                  {decks.map((d) => (
                    <NativeSelectOption key={d.id} value={String(d.id)}>
                      {d.name} {d.card_count ? `(${d.card_count} thẻ)` : ''}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </div>

              {/* Listing Title */}
              <div className="space-y-2">
                <Label htmlFor="title" className="text-xs font-semibold">
                  Tiêu đề xuất bản (Listing Title) <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="title"
                  placeholder="Ví dụ: 1000 Từ vựng IELTS 7.0+, N3 Kanji Luyện đọc, hay ReactJS Essentials"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="h-10 text-xs sm:text-sm rounded-xl font-medium"
                  required
                />
              </div>

              {/* Short Preview */}
              <div className="space-y-2">
                <Label htmlFor="preview" className="text-xs font-semibold">
                  Mô tả ngắn xem trước (Preview Text)
                </Label>
                <Input
                  id="preview"
                  placeholder="1 dòng mô tả tóm tắt điểm nổi bật để người học xem nhanh trên danh sách"
                  value={previewText}
                  onChange={(e) => setPreviewText(e.target.value)}
                  className="h-10 text-xs sm:text-sm rounded-xl"
                  maxLength={160}
                />
                <div className="flex justify-end text-[11px] text-muted-foreground">
                  {previewText.length}/160 ký tự
                </div>
              </div>

              {/* Detailed Description */}
              <div className="space-y-2">
                <Label htmlFor="description" className="text-xs font-semibold">
                  Mô tả chi tiết học liệu <span className="text-destructive">*</span>
                </Label>
                <Textarea
                  id="description"
                  rows={6}
                  placeholder="Giới thiệu mục tiêu bài học, đối tượng phù hợp, cấu trúc thẻ, hướng dẫn ôn tập và lý do nên sử dụng bộ thẻ này…"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="text-xs sm:text-sm rounded-xl leading-relaxed"
                  required
                />
              </div>

              {/* Pricing Selector Cards */}
              <div className="space-y-2 pt-2 border-t">
                <Label className="text-xs font-semibold">Mô hình phân phối & Giá bán</Label>
                <div className="grid grid-cols-2 gap-3">
                  <div
                    onClick={() => setPricingMode('free')}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                      pricingMode === 'free'
                        ? 'border-emerald-500 bg-emerald-500/10 shadow-xs'
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
                        ? 'border-amber-500 bg-amber-500/10 shadow-xs'
                        : 'border-border bg-card hover:bg-muted/40'
                    }`}
                  >
                    <div className="font-bold text-xs sm:text-sm">Trả phí (Paid)</div>
                    <div className="text-[11px] text-muted-foreground">Đặt giá niêm yết</div>
                  </div>
                </div>

                {pricingMode === 'paid' && (
                  <div className="pt-2 space-y-1.5 animate-in fade-in slide-in-from-top-1 duration-200">
                    <Label htmlFor="price" className="text-xs font-semibold">Giá bán niêm yết (VND)</Label>
                    <div className="relative">
                      <Input
                        id="price"
                        type="number"
                        min={1000}
                        step={1000}
                        value={priceAmountMinor}
                        onChange={(e) => setPriceAmountMinor(Number(e.target.value))}
                        className="h-10 text-xs sm:text-sm rounded-xl font-bold pr-16"
                        required
                      />
                      <span className="absolute right-3.5 top-1/2 -translate-y-1/2 text-xs font-bold text-muted-foreground">VND</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Version & Tags */}
              <div className="grid gap-4 sm:grid-cols-2 pt-2 border-t">
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
                2. Phân loại Môn học & Metadata
              </CardTitle>
              <CardDescription className="text-xs">
                Giúp hệ thống phân loại chính xác tài liệu cho người học.
              </CardDescription>
            </CardHeader>

            <CardContent className="p-4 sm:p-5 space-y-4">
              {/* Category Quick Presets */}
              <div className="space-y-2">
                <Label htmlFor="primary-category" className="text-xs font-semibold">Danh mục môn học chính</Label>
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
                  <Label htmlFor="custom-category" className="text-xs font-semibold">Tên danh mục tùy chỉnh</Label>
                  <Input
                    id="custom-category"
                    placeholder="Ví dụ: Âm nhạc, Đố vui, Lịch sử..."
                    value={customCategory}
                    onChange={(e) => setCustomCategory(e.target.value)}
                    className="h-10 text-xs sm:text-sm rounded-xl"
                    required
                  />
                </div>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="subcategory" className="text-xs font-semibold">Trình độ / Danh mục phụ</Label>
                <Input
                  id="subcategory"
                  placeholder="Ví dụ: N3, IELTS 6.5, HSK4, ReactJS, Sơ cấp..."
                  value={subcategory}
                  onChange={(e) => setSubcategory(e.target.value)}
                  className="h-10 text-xs sm:text-sm rounded-xl"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="target-audience" className="text-xs font-semibold">Đối tượng học phù hợp</Label>
                <Input
                  id="target-audience"
                  placeholder="Ví dụ: Người mới bắt đầu, Học sinh, Sinh viên IT, Người đi làm..."
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
                  disabled={!sourceDeckId || !title.trim() || !description.trim() || publishMutation.isPending}
                >
                  Xuất bản Bộ thẻ ngay
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </form>
    </Page>
  )
}

export function MarketplacePublishNoteTypePage() {
  const navigate = useNavigate()
  const [sourceNoteTypeId, setSourceNoteTypeId] = useState<string>('')
  const [title, setTitle] = useState('')
  const [previewText, setPreviewText] = useState('')
  const [description, setDescription] = useState('')
  const [pricingMode, setPricingMode] = useState<'free' | 'paid'>('free')
  const [priceAmountMinor, setPriceAmountMinor] = useState<number>(10000)
  const [version, setVersion] = useState('1.0.0')
  const [tags, setTags] = useState('')
  const [changelog, setChangelog] = useState('')
  const [primaryCategory, setPrimaryCategory] = useState('Templates')

  const noteTypesQuery = useQuery({
    queryKey: ['my-note-types-for-publish'],
    queryFn: () => appApi.get<{ items: SimpleNoteType[] }>('/note-types'),
  })

  const publishMutation = useMutation({
    mutationFn: () =>
      appApi.mutate(`/api/note-types/${sourceNoteTypeId}/publish`, 'POST', {
        title,
        preview_text: previewText,
        description,
        pricing_mode: pricingMode,
        price_amount_minor: pricingMode === 'paid' ? priceAmountMinor : 0,
        version,
        tags: tags ? tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
        changelog,
        primary_category: primaryCategory,
      }),
    onSuccess: () => {
      toast.success('Đã xuất bản Loại thẻ lên Marketplace thành công!')
      navigate('/marketplace/note-types')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  if (noteTypesQuery.isPending) return <PageLoading label="Đang tải loại thẻ của bạn…" />

  const noteTypes = noteTypesQuery.data?.items || []

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
              Chia sẻ Loại thẻ (Note Type) vào Marketplace
            </h1>
            <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed max-w-3xl">
              Đóng gói thiết kế mẫu thẻ (Cloze, Từ vựng song ngữ, Code Snippets, Q&A...) và cấu hình trường dữ liệu để chia sẻ cho cộng đồng.
            </p>
          </div>

          <Button variant="outline" asChild className="h-9 px-3.5 text-xs font-semibold rounded-xl shrink-0 self-start sm:self-center">
            <Link to="/marketplace/note-types">
              Quay lại NoteTypes
            </Link>
          </Button>
        </div>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          publishMutation.mutate()
        }}
        className="grid gap-6 lg:grid-cols-3 items-start"
      >
        <Card className="lg:col-span-2 shadow-xs rounded-2xl border-border/80 bg-card/90 backdrop-blur-sm overflow-hidden">
          <CardHeader className="p-4 sm:p-6 pb-3 border-b border-border/40 bg-muted/20">
            <CardTitle className="text-base sm:text-lg font-bold">
              Thông tin Mẫu loại thẻ
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 sm:p-6 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="source-nt" className="text-xs font-semibold">Chọn Loại thẻ cần xuất bản <span className="text-destructive">*</span></Label>
              <NativeSelect
                id="source-nt"
                value={sourceNoteTypeId}
                onChange={(e) => {
                  setSourceNoteTypeId(e.target.value)
                  const found = noteTypes.find((nt) => nt.id === e.target.value)
                  if (found && !title) setTitle(found.name)
                }}
                className="h-10 text-xs sm:text-sm rounded-xl font-medium"
                required
              >
                <NativeSelectOption value="">-- Chọn loại thẻ từ tài khoản --</NativeSelectOption>
                {noteTypes.map((nt) => (
                  <NativeSelectOption key={nt.id} value={nt.id}>
                    {nt.name}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="nt-title" className="text-xs font-semibold">Tiêu đề hiển thị <span className="text-destructive">*</span></Label>
              <Input
                id="nt-title"
                placeholder="Ví dụ: Cloze Deletion Chuẩn Anki, Mẫu Từ vựng Đa ngữ..."
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="h-10 text-xs sm:text-sm rounded-xl font-medium"
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="nt-desc" className="text-xs font-semibold">Mô tả mẫu thẻ <span className="text-destructive">*</span></Label>
              <Textarea
                id="nt-desc"
                rows={5}
                placeholder="Mô tả chi tiết cấu trúc field, thiết kế CSS và trường hợp sử dụng phù hợp…"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="text-xs sm:text-sm rounded-xl leading-relaxed"
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="nt-preview" className="text-xs font-semibold">Xem trước ngắn (Preview Text)</Label>
              <Input
                id="nt-preview"
                placeholder="1 dòng tóm tắt thiết kế mẫu thẻ"
                value={previewText}
                onChange={(e) => setPreviewText(e.target.value)}
                className="h-10 text-xs sm:text-sm rounded-xl"
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="nt-pricing" className="text-xs font-semibold">Mô hình giá</Label>
                <NativeSelect
                  id="nt-pricing"
                  value={pricingMode}
                  onChange={(e) => setPricingMode(e.target.value as 'free' | 'paid')}
                  className="h-10 text-xs sm:text-sm rounded-xl"
                >
                  <NativeSelectOption value="free">Miễn phí (Free)</NativeSelectOption>
                  <NativeSelectOption value="paid">Trả phí (Paid)</NativeSelectOption>
                </NativeSelect>
              </div>

              {pricingMode === 'paid' && (
                <div className="space-y-1.5">
                  <Label htmlFor="nt-price" className="text-xs font-semibold">Giá bán (VND)</Label>
                  <Input
                    id="nt-price"
                    type="number"
                    min={1000}
                    step={1000}
                    value={priceAmountMinor}
                    onChange={(e) => setPriceAmountMinor(Number(e.target.value))}
                    className="h-10 text-xs sm:text-sm rounded-xl font-bold"
                    required
                  />
                </div>
              )}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
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
                <Label htmlFor="nt-category" className="text-xs font-semibold">Danh mục</Label>
                <Input
                  id="nt-category"
                  placeholder="Templates, Vocabulary, Cloze..."
                  value={primaryCategory}
                  onChange={(e) => setPrimaryCategory(e.target.value)}
                  className="h-10 text-xs sm:text-sm rounded-xl"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="nt-tags" className="text-xs font-semibold">Tags</Label>
              <Input
                id="nt-tags"
                placeholder="cloze, grammar, kanji, english"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                className="h-10 text-xs sm:text-sm rounded-xl"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="nt-changelog" className="text-xs font-semibold">Changelog</Label>
              <Textarea
                id="nt-changelog"
                rows={2}
                placeholder="Ghi chú cập nhật mẫu thẻ…"
                value={changelog}
                onChange={(e) => setChangelog(e.target.value)}
                className="text-xs sm:text-sm rounded-xl"
              />
            </div>

            <div className="pt-3 border-t">
              <Button
                type="submit"
                size="lg"
                className="w-full h-11 font-bold text-sm rounded-xl shadow-md bg-primary hover:bg-primary/90 text-primary-foreground"
                disabled={!sourceNoteTypeId || !title.trim() || !description.trim() || publishMutation.isPending}
              >
                Xuất bản Loại thẻ ngay
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>
    </Page>
  )
}
