import { useState } from 'react'
import { ArrowLeft, Check, Sparkles, Upload } from 'lucide-react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { Page, PageHeader } from '@/shared/components/Page'
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
  const [primaryCategory, setPrimaryCategory] = useState('JLPT')
  const [subcategory, setSubcategory] = useState('N3')
  const [targetAudience, setTargetAudience] = useState('Intermediate')

  const decksQuery = useQuery({
    queryKey: ['my-decks-for-publish'],
    queryFn: () => appApi.get<{ items: SimpleDeck[] }>('/decks'),
  })

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
        primary_category: primaryCategory,
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

  return (
    <Page>
      <PageHeader
        title="Chia sẻ Bộ thẻ vào Marketplace"
        description="Giải thích bộ thẻ dùng để học gì, phù hợp trình độ nào, và thiết lập thông tin hiển thị."
        actions={
          <Button variant="outline" asChild>
            <Link to="/marketplace/decks">
              <ArrowLeft className="mr-1.5 size-4" /> Quay lại Marketplace
            </Link>
          </Button>
        }
      />

      <form
        onSubmit={(e) => {
          e.preventDefault()
          publishMutation.mutate()
        }}
        className="grid gap-6 lg:grid-cols-3"
      >
        <Card className="lg:col-span-2 shadow-xs">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Sparkles className="size-5 text-primary" /> Thông tin Niêm yết (Listing Basics)
            </CardTitle>
            <CardDescription>
              Thông tin này sẽ hiển thị trực tiếp cho người học xem trên Marketplace.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="source-deck">Chọn Bộ thẻ cần chia sẻ</Label>
              <NativeSelect
                id="source-deck"
                value={sourceDeckId}
                onChange={(e) => {
                  setSourceDeckId(e.target.value)
                  const found = decks.find((d) => String(d.id) === e.target.value)
                  if (found && !title) setTitle(found.name)
                }}
                required
              >
                <NativeSelectOption value="">-- Chọn bộ thẻ --</NativeSelectOption>
                {decks.map((d) => (
                  <NativeSelectOption key={d.id} value={String(d.id)}>
                    {d.name} {d.card_count ? `(${d.card_count} thẻ)` : ''}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>

            <div className="space-y-2">
              <Label htmlFor="title">Tiêu đề Listing</Label>
              <Input
                id="title"
                placeholder="Ví dụ: N3 Kanji Luyện đọc chuẩn JLPT"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="preview">Xem trước ngắn (Preview Text)</Label>
              <Input
                id="preview"
                placeholder="1 dòng mô tả ngắn để learner scan nhanh"
                value={previewText}
                onChange={(e) => setPreviewText(e.target.value)}
                maxLength={160}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Mô tả chi tiết</Label>
              <Textarea
                id="description"
                rows={6}
                placeholder="Nói rõ mục tiêu học, đối tượng phù hợp, cách dùng deck và điểm đặc biệt…"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                required
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="pricing">Mô hình giá</Label>
                <NativeSelect
                  id="pricing"
                  value={pricingMode}
                  onChange={(e) => setPricingMode(e.target.value as 'free' | 'paid')}
                >
                  <NativeSelectOption value="free">Miễn phí (Free)</NativeSelectOption>
                  <NativeSelectOption value="paid">Trả phí (Paid)</NativeSelectOption>
                </NativeSelect>
              </div>

              {pricingMode === 'paid' && (
                <div className="space-y-2">
                  <Label htmlFor="price">Giá bán (VND)</Label>
                  <Input
                    id="price"
                    type="number"
                    min={1000}
                    step={1000}
                    value={priceAmountMinor}
                    onChange={(e) => setPriceAmountMinor(Number(e.target.value))}
                    required
                  />
                </div>
              )}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="version">Phiên bản</Label>
                <Input
                  id="version"
                  value={version}
                  onChange={(e) => setVersion(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="tags">Tags (phân cách bởi dấu phẩy)</Label>
                <Input
                  id="tags"
                  placeholder="kanji, n3, minna"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="changelog">Changelog (Nhật ký thay đổi)</Label>
              <Textarea
                id="changelog"
                rows={2}
                placeholder="Ghi chú nếu có cập nhật nội dung mới…"
                value={changelog}
                onChange={(e) => setChangelog(e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        {/* Taxonomy Metadata Sidebar */}
        <div className="space-y-6">
          <Card className="shadow-xs">
            <CardHeader>
              <CardTitle className="text-base">Phân loại Metadata</CardTitle>
              <CardDescription>Giúp learner lọc nhanh học liệu</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="primary-category">Danh mục chính</Label>
                <NativeSelect
                  id="primary-category"
                  value={primaryCategory}
                  onChange={(e) => setPrimaryCategory(e.target.value)}
                >
                  <NativeSelectOption value="JLPT">JLPT</NativeSelectOption>
                  <NativeSelectOption value="Kaiwa">Giao tiếp (Kaiwa)</NativeSelectOption>
                  <NativeSelectOption value="Grammar">Ngữ pháp</NativeSelectOption>
                  <NativeSelectOption value="Vocabulary">Từ vựng</NativeSelectOption>
                  <NativeSelectOption value="General">Khác</NativeSelectOption>
                </NativeSelect>
              </div>

              <div className="space-y-2">
                <Label htmlFor="subcategory">Danh mục phụ / Trình độ</Label>
                <Input
                  id="subcategory"
                  placeholder="Ví dụ: N5, N4, N3, N2, N1"
                  value={subcategory}
                  onChange={(e) => setSubcategory(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="target-audience">Đối tượng phù hợp</Label>
                <Input
                  id="target-audience"
                  placeholder="Ví dụ: Người mới bắt đầu, Sơ cấp..."
                  value={targetAudience}
                  onChange={(e) => setTargetAudience(e.target.value)}
                />
              </div>

              <div className="pt-4">
                <Button
                  type="submit"
                  className="w-full gap-2"
                  disabled={!sourceDeckId || !title.trim() || !description.trim() || publishMutation.isPending}
                >
                  <Upload className="size-4" />
                  Xuất bản Bộ thẻ
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
    <Page>
      <PageHeader
        title="Chia sẻ Loại thẻ (Note Type) vào Marketplace"
        description="Đóng gói mẫu thiết kế thẻ và cấu hình field để chia sẻ cho cộng đồng."
        actions={
          <Button variant="outline" asChild>
            <Link to="/marketplace/note-types">
              <ArrowLeft className="mr-1.5 size-4" /> Quay lại NoteTypes
            </Link>
          </Button>
        }
      />

      <form
        onSubmit={(e) => {
          e.preventDefault()
          publishMutation.mutate()
        }}
        className="grid gap-6 lg:grid-cols-3"
      >
        <Card className="lg:col-span-2 shadow-xs">
          <CardHeader>
            <CardTitle className="text-lg">Thông tin loại thẻ</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="source-nt">Chọn Loại thẻ cần xuất bản</Label>
              <NativeSelect
                id="source-nt"
                value={sourceNoteTypeId}
                onChange={(e) => {
                  setSourceNoteTypeId(e.target.value)
                  const found = noteTypes.find((nt) => nt.id === e.target.value)
                  if (found && !title) setTitle(found.name)
                }}
                required
              >
                <NativeSelectOption value="">-- Chọn loại thẻ --</NativeSelectOption>
                {noteTypes.map((nt) => (
                  <NativeSelectOption key={nt.id} value={nt.id}>
                    {nt.name}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>

            <div className="space-y-2">
              <Label htmlFor="nt-title">Tiêu đề hiển thị</Label>
              <Input
                id="nt-title"
                placeholder="Ví dụ: Cloze Deletion Chuẩn Anki"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="nt-desc">Mô tả mẫu thẻ</Label>
              <Textarea
                id="nt-desc"
                rows={5}
                placeholder="Mô tả cấu trúc field và cách hiển thị của mẫu thẻ…"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="nt-preview">Xem trước ngắn (Preview Text)</Label>
              <Input
                id="nt-preview"
                placeholder="1 dòng mô tả ngắn về mẫu thẻ"
                value={previewText}
                onChange={(e) => setPreviewText(e.target.value)}
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="nt-pricing">Mô hình giá</Label>
                <NativeSelect
                  id="nt-pricing"
                  value={pricingMode}
                  onChange={(e) => setPricingMode(e.target.value as 'free' | 'paid')}
                >
                  <NativeSelectOption value="free">Miễn phí (Free)</NativeSelectOption>
                  <NativeSelectOption value="paid">Trả phí (Paid)</NativeSelectOption>
                </NativeSelect>
              </div>

              {pricingMode === 'paid' && (
                <div className="space-y-2">
                  <Label htmlFor="nt-price">Giá bán (VND)</Label>
                  <Input
                    id="nt-price"
                    type="number"
                    min={1000}
                    step={1000}
                    value={priceAmountMinor}
                    onChange={(e) => setPriceAmountMinor(Number(e.target.value))}
                    required
                  />
                </div>
              )}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="nt-version">Phiên bản</Label>
                <Input
                  id="nt-version"
                  value={version}
                  onChange={(e) => setVersion(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="nt-category">Danh mục</Label>
                <Input
                  id="nt-category"
                  value={primaryCategory}
                  onChange={(e) => setPrimaryCategory(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="nt-tags">Tags</Label>
              <Input
                id="nt-tags"
                placeholder="cloze, grammar, kanji"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="nt-changelog">Changelog</Label>
              <Textarea
                id="nt-changelog"
                rows={2}
                placeholder="Ghi chú thay đổi mấu thẻ…"
                value={changelog}
                onChange={(e) => setChangelog(e.target.value)}
              />
            </div>

            <div className="pt-2">
              <Button
                type="submit"
                className="w-full gap-2"
                disabled={!sourceNoteTypeId || !title.trim() || !description.trim() || publishMutation.isPending}
              >
                <Check className="size-4" /> Xuất bản Loại thẻ
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>
    </Page>
  )
}
