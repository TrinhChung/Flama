import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  Award,
  CheckCircle,
  Download,
  Eye,
  Heart,
  Layers,
  Loader2,
  MessageSquare,
  Star,
  User,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { CardRendererFrame } from '@/features/study/components/CardRendererFrame'
import { Page, PageHeader } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'

type FieldDef = {
  name: string
  label?: string
  type?: string
}

type TemplateItem = {
  id: string
  name: string
  front_html?: string
  back_html?: string
}

type ReviewItem = {
  id?: string
  username?: string
  rating: number
  comment?: string | null
  updated_at?: string | null
}

type SharedNoteTypeDetail = {
  id: string
  name?: string
  title?: string
  description?: string | null
  preview_text?: string | null
  primary_category?: string | null
  price_display?: string
  pricing_mode?: string
  rating_avg: number
  rating_count: number
  install_count: number
  updated_at?: string
  badges?: string[]
  tags?: string[]
  display_tags?: string[]
  is_installed: boolean
  installed_note_type_id?: string | null
  is_owner: boolean
  is_saved: boolean
  can_rate: boolean
  review_submission_count?: number
  review_submissions_remaining?: number
  my_review?: ReviewItem | null
  author?: { id: number; username: string } | null
  author_profile?: {
    username?: string
    published_count?: number
  }
  field_defs?: FieldDef[]
  templates?: TemplateItem[]
  recent_reviews?: ReviewItem[]
}

type PreviewResponse = {
  front_html?: string
  back_html?: string
  front_renderer_payload?: unknown
  back_renderer_payload?: unknown
}

export function SharedNoteTypeDetailPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()

  // State
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('')
  const [previewSide, setPreviewSide] = useState<'front' | 'back'>('front')

  const [ratingScore, setRatingScore] = useState<number>(5)
  const [hoverScore, setHoverScore] = useState<number | null>(null)
  const [ratingComment, setRatingComment] = useState<string>('')
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null)

  const noteTypeQuery = useQuery({
    queryKey: ['shared-note-type-detail', id],
    queryFn: () => appApi.get<SharedNoteTypeDetail>(`/api/shared/note-types/${id}`),
    enabled: Boolean(id),
  })

  const noteType = noteTypeQuery.data
  const templates = noteType?.templates || []

  // Auto select initial template
  useEffect(() => {
    if (templates.length > 0 && !selectedTemplateId) {
      setSelectedTemplateId(templates[0].id)
    }
  }, [templates, selectedTemplateId])

  // Template Preview Query
  const previewQuery = useQuery({
    queryKey: ['shared-note-type-preview', id, selectedTemplateId],
    queryFn: () =>
      appApi.mutate<PreviewResponse>(
        `/api/shared/note-types/${id}/templates/${selectedTemplateId}/preview`,
        'POST',
        {},
      ),
    enabled: Boolean(id && selectedTemplateId),
  })

  const installMutation = useMutation({
    mutationFn: async () => {
      return appApi.mutate<{
        installed_note_type_id?: string
        already_installed?: boolean
      }>(`/api/shared/note-types/${id}/install`, 'POST')
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shared-note-type-detail', id] })
      queryClient.invalidateQueries({ queryKey: ['marketplace'] })
    },
  })

  const saveMutation = useMutation({
    mutationFn: async (isSaved: boolean) => {
      return appApi.mutate(`/api/shared/note-types/${id}/save`, isSaved ? 'DELETE' : 'POST')
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shared-note-type-detail', id] })
    },
  })

  const rateMutation = useMutation({
    mutationFn: async () => {
      setSubmitError(null)
      setSubmitSuccess(null)
      return appApi.mutate(`/api/shared/note-types/${id}/rate`, 'POST', {
        rating: ratingScore,
        comment: ratingComment.trim() || undefined,
      })
    },
    onSuccess: () => {
      setSubmitSuccess('Cảm ơn bạn đã gửi đánh giá!')
      setRatingComment('')
      queryClient.invalidateQueries({ queryKey: ['shared-note-type-detail', id] })
    },
    onError: (error: Error) => {
      setSubmitError(error.message || 'Không thể gửi đánh giá.')
    },
  })

  if (noteTypeQuery.isPending) {
    return (
      <Page>
        <PageLoading label="Đang tải loại thẻ..." />
      </Page>
    )
  }

  if (noteTypeQuery.error || !noteType) {
    return (
      <Page>
        <PageError error={noteTypeQuery.error || new Error('Không tìm thấy loại thẻ')} />
      </Page>
    )
  }

  const titleName = noteType.title || noteType.name || 'Loại thẻ không tên'
  const authorName =
    noteType.author_profile?.username || noteType.author?.username || 'Cộng đồng'
  const tagsList = noteType.display_tags || noteType.tags || []
  const fields = noteType.field_defs || []

  const effectiveStar = hoverScore !== null ? hoverScore : ratingScore

  return (
    <Page>
      <PageHeader
        title={titleName}
        description={noteType.preview_text || noteType.description || 'Chi tiết mẫu note type trên marketplace Flama.'}
        actions={
          <Button variant="outline" size="sm" asChild className="group">
            <Link to="/marketplace/note-types">
              <ArrowLeft className="mr-1.5 size-4 group-hover:-translate-x-0.5 transition-transform" />
              Quay lại Marketplace
            </Link>
          </Button>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        {/* Main Left Content */}
        <div className="space-y-6">
          {/* Main Card (Strict Theme Token Alignment) */}
          <Card className="relative overflow-hidden border-border bg-card shadow-xs">
            <CardHeader className="space-y-3 pb-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary" className="px-2.5 py-0.5 text-xs font-semibold">
                    {noteType.primary_category || 'Loại thẻ'}
                  </Badge>
                  {(noteType.badges || []).map((badge) => (
                    <Badge key={badge} variant="outline" className="text-xs">
                      <Award className="mr-1 size-3 text-primary" />
                      {badge}
                    </Badge>
                  ))}
                </div>
                <span className="text-xl font-bold text-primary">
                  {noteType.price_display || 'Miễn phí'}
                </span>
              </div>

              <CardTitle className="text-2xl font-black tracking-tight text-foreground lg:text-3xl leading-tight">
                {titleName}
              </CardTitle>

              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <div className="flex items-center gap-1.5 font-medium text-foreground">
                  <User className="size-4 text-primary" />
                  <span>{authorName}</span>
                </div>
                <span>•</span>
                <span>Xuất bản trên Flama</span>
              </div>
            </CardHeader>

            <CardContent className="space-y-5">
              <p className="text-sm leading-relaxed text-muted-foreground font-normal">
                {noteType.description || 'Chưa có mô tả chi tiết cho loại thẻ này.'}
              </p>

              {tagsList.length > 0 ? (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {tagsList.map((tag) => (
                    <Badge key={tag} variant="outline" className="text-xs text-muted-foreground">
                      #{tag}
                    </Badge>
                  ))}
                </div>
              ) : null}

              {/* Stat Cards */}
              <div className="grid grid-cols-2 gap-3 pt-2 sm:grid-cols-3">
                <div className="rounded-xl border border-border/70 bg-muted/20 p-3.5 text-center">
                  <div className="flex items-center justify-center gap-1 text-xs font-medium text-muted-foreground">
                    <Star className="size-3.5 fill-amber-400 text-amber-500" />
                    <span>Đánh giá</span>
                  </div>
                  <div className="mt-1 flex items-center justify-center gap-1 font-bold text-base text-foreground">
                    <span>{noteType.rating_avg.toFixed(1)}</span>
                    <span className="text-xs font-normal text-muted-foreground">({noteType.rating_count})</span>
                  </div>
                </div>

                <div className="rounded-xl border border-border/70 bg-muted/20 p-3.5 text-center">
                  <div className="flex items-center justify-center gap-1 text-xs font-medium text-muted-foreground">
                    <Download className="size-3.5 text-primary" />
                    <span>Cài đặt</span>
                  </div>
                  <div className="mt-1 font-bold text-base text-foreground">
                    {noteType.install_count.toLocaleString('vi-VN')}
                  </div>
                </div>

                <div className="rounded-xl border border-border/70 bg-muted/20 p-3.5 text-center">
                  <div className="flex items-center justify-center gap-1 text-xs font-medium text-muted-foreground">
                    <Layers className="size-3.5 text-primary" />
                    <span>Trường thông tin</span>
                  </div>
                  <div className="mt-1 font-bold text-base text-foreground">
                    {fields.length} trường
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Live Preview Section */}
          <Card className="border-border shadow-xs overflow-hidden">
            <CardHeader className="pb-3 border-b bg-muted/20">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-primary/10 text-primary">
                    <Eye className="size-5" />
                  </div>
                  <div>
                    <CardTitle className="text-lg font-bold">Xem trước Template (Live Preview)</CardTitle>
                    <CardDescription className="text-xs">
                      Mô phỏng hiển thị mặt trước và mặt sau dựa trên mẫu thẻ
                    </CardDescription>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {templates.length > 1 ? (
                    <NativeSelect
                      value={selectedTemplateId}
                      onChange={(e) => setSelectedTemplateId(e.target.value)}
                      className="h-8 text-xs w-36"
                    >
                      {templates.map((t) => (
                        <NativeSelectOption key={t.id} value={t.id}>
                          {t.name}
                        </NativeSelectOption>
                      ))}
                    </NativeSelect>
                  ) : null}

                  <div className="inline-flex rounded-lg border bg-card p-0.5 shadow-2xs">
                    <Button
                      size="sm"
                      variant={previewSide === 'front' ? 'default' : 'ghost'}
                      className="h-7 px-3.5 text-xs font-semibold rounded-md transition-all"
                      onClick={() => setPreviewSide('front')}
                    >
                      Mặt trước
                    </Button>
                    <Button
                      size="sm"
                      variant={previewSide === 'back' ? 'default' : 'ghost'}
                      className="h-7 px-3.5 text-xs font-semibold rounded-md transition-all"
                      onClick={() => setPreviewSide('back')}
                    >
                      Mặt sau
                    </Button>
                  </div>
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-4 bg-muted/30">
              <div className="rounded-xl border border-border bg-card p-4 min-h-[160px] max-h-[520px] overflow-y-auto w-full flex flex-col justify-start items-center relative shadow-xs">
                {previewQuery.isPending ? (
                  <div className="flex flex-col items-center justify-center p-8 space-y-2 text-muted-foreground my-auto">
                    <Loader2 className="size-6 animate-spin text-primary" />
                    <span className="text-xs">Đang tải bản xem trước template...</span>
                  </div>
                ) : previewQuery.data ? (
                  <div className="w-full">
                    <CardRendererFrame
                      cardId={`note-type-preview-${id}`}
                      revealed={previewSide === 'back'}
                      frontPayload={previewQuery.data.front_renderer_payload}
                      backPayload={previewQuery.data.back_renderer_payload}
                      frontHtml={previewQuery.data.front_html}
                      backHtml={previewQuery.data.back_html}
                      scope="shared_note_type_preview"
                      scopeId={id}
                    />
                  </div>
                ) : (
                  <EmptyState
                    title="Chưa có xem trước"
                    description="Loại thẻ này chưa có template."
                  />
                )}
              </div>
            </CardContent>
          </Card>

          {/* Fields Structure Card */}
          <Card className="border-border shadow-xs">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-bold">Danh sách trường thông tin (Fields)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {fields.map((f, idx) => (
                  <Badge key={idx} variant="secondary" className="px-3 py-1 text-xs font-medium">
                    {f.name} {f.label ? `(${f.label})` : ''}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Reviews Card */}
          <Card className="border-border shadow-xs">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-primary/10 text-primary">
                  <MessageSquare className="size-5" />
                </div>
                <CardTitle className="text-lg font-bold">Đánh giá từ cộng đồng</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {noteType.can_rate ? (
                <div className="rounded-xl border border-border bg-card p-4 space-y-3 shadow-2xs">
                  <div className="font-bold text-sm text-foreground">Gửi đánh giá của bạn</div>
                  <div className="flex items-center gap-3">
                    <div className="flex gap-1" onMouseLeave={() => setHoverScore(null)}>
                      {[1, 2, 3, 4, 5].map((star) => (
                        <button
                          key={star}
                          type="button"
                          className="p-1 transition-transform hover:scale-110 focus:outline-none cursor-pointer"
                          onMouseEnter={() => setHoverScore(star)}
                          onClick={() => setRatingScore(star)}
                        >
                          <Star
                            className={`size-6 ${
                              star <= effectiveStar
                                ? 'fill-amber-400 text-amber-500'
                                : 'text-muted-foreground/30'
                            }`}
                          />
                        </button>
                      ))}
                    </div>
                    <span className="text-sm font-bold text-foreground">
                      {effectiveStar}/5 sao
                    </span>
                  </div>

                  <Textarea
                    placeholder="Viết nhận xét của bạn..."
                    value={ratingComment}
                    onChange={(e) => setRatingComment(e.target.value)}
                    rows={3}
                  />

                  {submitError ? (
                    <p className="text-xs text-destructive font-medium">{submitError}</p>
                  ) : null}
                  {submitSuccess ? (
                    <p className="text-xs text-primary font-bold">{submitSuccess}</p>
                  ) : null}

                  <Button
                    size="sm"
                    className="font-bold"
                    onClick={() => rateMutation.mutate()}
                    disabled={rateMutation.isPending}
                  >
                    {rateMutation.isPending ? (
                      <Loader2 className="mr-1.5 size-4 animate-spin" />
                    ) : null}
                    Gửi nhận xét
                  </Button>
                </div>
              ) : null}

              <div className="space-y-3">
                {noteType.recent_reviews && noteType.recent_reviews.length > 0 ? (
                  <div className="space-y-3">
                    {noteType.recent_reviews.map((rev, i) => (
                      <div key={i} className="rounded-xl border border-border p-3.5 text-sm space-y-2 bg-card">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-xs text-foreground">
                            {rev.username || 'Học viên'}
                          </span>
                          <div className="flex items-center gap-1 font-bold text-xs text-amber-500">
                            <Star className="size-3.5 fill-amber-400" />
                            <span>{rev.rating}/5</span>
                          </div>
                        </div>
                        <p className="text-xs text-muted-foreground leading-relaxed">
                          {rev.comment || 'Không để lại lời nhắn.'}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    title="Chưa có nhận xét"
                    description="Chưa có đánh giá nào cho loại thẻ này."
                  />
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <Card className="sticky top-6 border-border shadow-xs">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-bold">Hành động</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {noteType.is_owner ? (
                <Button className="w-full font-bold" variant="secondary" disabled>
                  <CheckCircle className="mr-1.5 size-4 text-primary" />
                  Bạn là tác giả loại thẻ này
                </Button>
              ) : noteType.is_installed ? (
                <Button className="w-full font-bold" variant="outline" disabled>
                  <CheckCircle className="mr-1.5 size-4 text-primary" />
                  Đã cài đặt
                </Button>
              ) : (
                <Button
                  className="w-full font-bold text-base py-5 shadow-xs"
                  size="lg"
                  onClick={() => installMutation.mutate()}
                  disabled={installMutation.isPending}
                >
                  {installMutation.isPending ? (
                    <Loader2 className="mr-2 size-5 animate-spin" />
                  ) : (
                    <Download className="mr-2 size-5" />
                  )}
                  Tải xuống & Cài đặt
                </Button>
              )}

              {!noteType.is_owner ? (
                <Button
                  className="w-full font-semibold"
                  variant="outline"
                  size="sm"
                  onClick={() => saveMutation.mutate(noteType.is_saved)}
                  disabled={saveMutation.isPending}
                >
                  <Heart
                    className={`mr-1.5 size-4 ${
                      noteType.is_saved ? 'fill-primary text-primary' : ''
                    }`}
                  />
                  {noteType.is_saved ? 'Đã lưu' : 'Lưu loại thẻ'}
                </Button>
              ) : null}

              <div className="pt-3 border-t text-xs text-muted-foreground space-y-1.5">
                <div className="flex items-center gap-1.5">
                  <User className="size-3.5 text-primary" />
                  <span>Tác giả: <strong>{authorName}</strong></span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </Page>
  )
}
