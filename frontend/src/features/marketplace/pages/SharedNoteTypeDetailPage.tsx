import { useEffect, useState, useMemo } from 'react'
import {
  ArrowLeft,
  Award,
  Check,
  CheckCircle,
  Copy,
  Download,
  Heart,
  Layers,
  Loader2,
  MessageSquare,
  Share2,
  Star,
  User,
  EyeOff,
  Edit3,
  Globe,
  Lock,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { NoteTypeLivePreview } from '@/features/note-types/components/NoteTypeLivePreview'
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
  publish_status?: 'private' | 'published' | 'unlisted' | 'archived'
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
  const [isCopied, setIsCopied] = useState(false)

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href)
    setIsCopied(true)
    toast.success('Đã sao chép liên kết chia sẻ!')
    setTimeout(() => setIsCopied(false), 2000)
  }

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
  const templates = useMemo(() => noteType?.templates || [], [noteType?.templates])

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
        payment_required?: boolean
        order?: { id: string; active_attempt?: { checkout_url?: string } }
      }>(`/api/shared/note-types/${id}/install`, 'POST')
    },
    onSuccess: (data) => {
      if (data.payment_required && data.order) {
        const checkoutUrl = data.order.active_attempt?.checkout_url
        if (checkoutUrl) {
          window.location.href = checkoutUrl
          return
        }
        window.location.assign('/orders')
        return
      }
      queryClient.invalidateQueries({ queryKey: ['shared-note-type-detail', id] })
      queryClient.invalidateQueries({ queryKey: ['marketplace'] })
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Không thể cài đặt Note Type.')
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

  // Rating Mutation
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
  const publishStatusMutation = useMutation({
    mutationFn: async (newStatus: 'private' | 'published' | 'unlisted' | 'archived') => {
      return appApi.mutate<SharedNoteTypeDetail>(`/api/note-types/${id}/publish`, 'POST', {
        publish_status: newStatus,
      })
    },
    onSuccess: (data) => {
      toast.success(
        data.publish_status === 'private'
          ? 'Đã thu hồi loại thẻ khỏi Marketplace!'
          : 'Đã cập nhật trạng thái xuất bản loại thẻ!'
      )
      queryClient.invalidateQueries({ queryKey: ['shared-note-type-detail', id] })
      queryClient.invalidateQueries({ queryKey: ['marketplace'] })
    },
    onError: (error: Error) => {
      toast.error('Không thể cập nhật trạng thái', { description: error.message })
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
    <Page className="space-y-4 sm:space-y-6 relative px-2.5 sm:px-6 lg:px-8 py-3 sm:py-6">
      <AmbientBackground intensity="subtle" />

      <PageHeader
        title={titleName}
        description={noteType.preview_text || noteType.description || 'Chi tiết mẫu note type trên marketplace Flama.'}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="h-8 sm:h-9 px-3 sm:px-3.5 text-xs font-semibold rounded-xl"
              onClick={handleCopyLink}
            >
              {isCopied ? <Check className="mr-1.5 size-3.5 text-emerald-500" /> : <Share2 className="mr-1.5 size-3.5 text-primary" />}
              {isCopied ? 'Đã chép link' : 'Chia sẻ'}
            </Button>
            <Button variant="outline" size="sm" asChild className="group h-8 sm:h-9 px-3 sm:px-3.5 text-xs font-semibold rounded-xl">
              <Link to="/marketplace/note-types">
                <ArrowLeft className="mr-1 sm:mr-1.5 size-3.5 group-hover:-translate-x-0.5 transition-transform" />
                Quay lại
              </Link>
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 sm:gap-5 lg:grid-cols-[1fr_340px]">
        {/* Main Left Content */}
        <div className="space-y-4 sm:space-y-5">
          {/* Main Card */}
          <Card className="relative overflow-hidden border-border/40 sm:border-border/80 bg-card/90 backdrop-blur-md shadow-xs sm:shadow-sm rounded-xl sm:rounded-2xl">
            <div className="h-2 w-full bg-gradient-to-r from-primary via-orange-500 to-amber-500" />
            <CardHeader className="space-y-3 p-3.5 sm:p-6 pb-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary" className="px-2.5 py-0.5 text-xs font-bold rounded-md">
                    {noteType.primary_category || 'Loại thẻ'}
                  </Badge>
                  {(noteType.badges || []).map((badge) => (
                    <Badge key={badge} variant="outline" className="text-xs font-semibold rounded-md">
                      <Award className="mr-1 size-3 text-primary" />
                      {badge}
                    </Badge>
                  ))}
                </div>

                <span
                  className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-extrabold border ${
                    noteType.pricing_mode === 'free'
                      ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30'
                      : 'bg-primary/10 text-primary border-primary/30'
                  }`}
                >
                  {noteType.price_display || 'Miễn phí'}
                </span>
              </div>

              <CardTitle className="text-2xl font-black tracking-tight text-foreground sm:text-3xl leading-tight">
                {titleName}
              </CardTitle>

              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <div className="flex items-center gap-1.5">
                  <div className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px]">
                    {authorName.charAt(0).toUpperCase()}
                  </div>
                  <span className="font-semibold text-foreground">{authorName}</span>
                </div>
                <span>•</span>
                <span className="flex items-center gap-1 font-medium text-emerald-600 dark:text-emerald-400">
                  <CheckCircle className="size-3.5" /> Flama Marketplace
                </span>
              </div>
            </CardHeader>

            <CardContent className="p-5 sm:p-6 pt-0 space-y-4">
              <p className="text-xs sm:text-sm leading-relaxed text-muted-foreground font-normal">
                {noteType.description || 'Chưa có mô tả chi tiết cho loại thẻ này.'}
              </p>

              {tagsList.length > 0 ? (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {tagsList.map((tag) => (
                    <Badge key={tag} variant="outline" className="text-[11px] text-muted-foreground font-medium px-2.5 py-0.5 rounded-md">
                      #{tag}
                    </Badge>
                  ))}
                </div>
              ) : null}

              {/* Stat Cards */}
              <div className="grid grid-cols-2 gap-3 pt-1 sm:grid-cols-3">
                <div className="rounded-xl border border-border/80 bg-muted/30 p-3.5 sm:p-4 text-center transition-all hover:bg-muted/50">
                  <div className="flex items-center justify-center gap-1 text-xs font-semibold text-muted-foreground">
                    <Star className="size-3.5 fill-amber-400 text-amber-500" />
                    <span>Đánh giá</span>
                  </div>
                  <div className="mt-1 flex items-center justify-center gap-1 font-extrabold text-base text-foreground">
                    <span>{noteType.rating_avg.toFixed(1)}</span>
                    <span className="text-xs font-normal text-muted-foreground">({noteType.rating_count})</span>
                  </div>
                </div>

                <div className="rounded-xl border border-border/80 bg-muted/30 p-3.5 sm:p-4 text-center transition-all hover:bg-muted/50">
                  <div className="flex items-center justify-center gap-1 text-xs font-semibold text-muted-foreground">
                    <Download className="size-3.5 text-primary" />
                    <span>Lượt cài</span>
                  </div>
                  <div className="mt-1 font-extrabold text-base text-foreground">
                    {noteType.install_count.toLocaleString('vi-VN')}
                  </div>
                </div>

                <div className="rounded-xl border border-border/80 bg-muted/30 p-3.5 sm:p-4 text-center transition-all hover:bg-muted/50">
                  <div className="flex items-center justify-center gap-1 text-xs font-semibold text-muted-foreground">
                    <Layers className="size-3.5 text-primary" />
                    <span>Trường</span>
                  </div>
                  <div className="mt-1 font-extrabold text-base text-foreground">
                    {fields.length} trường
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Live Preview Section (Reusing NoteTypeLivePreview) */}
          <NoteTypeLivePreview
            cardId={`note-type-preview-${id}`}
            side={previewSide}
            onSideChange={setPreviewSide}
            templates={templates.map((t) => ({ id: t.id, name: t.name }))}
            selectedTemplateId={selectedTemplateId || undefined}
            onSelectTemplate={setSelectedTemplateId}
            frontPayload={previewQuery.data?.front_renderer_payload}
            backPayload={previewQuery.data?.back_renderer_payload}
            frontHtml={previewQuery.data?.front_html}
            backHtml={previewQuery.data?.back_html}
            scope="shared_note_type_preview"
            scopeId={id}
            isLoading={previewQuery.isPending}
            title="Xem trước Template (Live Previewer)"
            subtitle="Mô phỏng hiển thị mặt trước và mặt sau dựa trên mẫu loại thẻ"
            containerHeightClass="h-[clamp(20rem,50vh,32rem)] min-h-[250px]"
          />

          {/* Fields Structure Card */}
          <Card className="border-border shadow-xs rounded-2xl">
            <CardHeader className="p-4 sm:p-5 pb-3">
              <div className="flex items-center gap-2">
                <Layers className="size-4 text-primary" />
                <CardTitle className="text-base font-bold">Danh sách trường thông tin (Fields)</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="p-4 sm:p-5 pt-0">
              <div className="flex flex-wrap gap-2">
                {fields.map((f, idx) => (
                  <Badge key={idx} variant="secondary" className="px-3.5 py-1.5 text-xs font-bold border border-border/60 rounded-xl">
                    {f.name} {f.label ? <span className="text-muted-foreground font-normal">({f.label})</span> : ''}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Reviews Card */}
          <Card className="border-border shadow-xs rounded-2xl">
            <CardHeader className="p-4 sm:p-5 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2.5 rounded-xl bg-primary/10 text-primary">
                  <MessageSquare className="size-5" />
                </div>
                <CardTitle className="text-lg font-bold">Đánh giá từ cộng đồng</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="p-4 sm:p-5 pt-0 space-y-6">
              {noteType.can_rate ? (
                <div className="rounded-2xl border border-border/80 bg-card p-4 space-y-3 shadow-2xs">
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
                    placeholder="Viết nhận xét của bạn về thiết kế loại thẻ này..."
                    value={ratingComment}
                    onChange={(e) => setRatingComment(e.target.value)}
                    rows={3}
                    className="text-xs sm:text-sm leading-relaxed rounded-xl"
                  />

                  {submitError ? (
                    <p className="text-xs text-destructive font-medium">{submitError}</p>
                  ) : null}
                  {submitSuccess ? (
                    <p className="text-xs text-emerald-600 dark:text-emerald-400 font-bold">{submitSuccess}</p>
                  ) : null}

                  <Button
                    size="sm"
                    className="h-9 px-4 font-bold text-xs sm:text-sm shadow-2xs rounded-xl"
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
                      <div key={i} className="rounded-2xl border border-border/80 p-4 text-sm space-y-2 bg-card shadow-2xs">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className="flex size-6 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px]">
                              {(rev.username || 'H').charAt(0).toUpperCase()}
                            </div>
                            <span className="font-bold text-xs text-foreground">
                              {rev.username || 'Học viên'}
                            </span>
                          </div>
                          <div className="flex items-center gap-1 font-bold text-xs text-amber-500 bg-amber-500/10 px-2.5 py-0.5 rounded-full">
                            <Star className="size-3.5 fill-amber-400" />
                            <span>{rev.rating}/5</span>
                          </div>
                        </div>
                        <p className="text-xs text-muted-foreground leading-relaxed pl-8">
                          {rev.comment || 'Học viên không để lại lời nhắn.'}
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
          <Card className="sticky top-6 border-border shadow-xs overflow-hidden rounded-2xl">
            <div className="h-1.5 w-full bg-primary" />
            <CardHeader className="p-4 sm:p-5 pb-3">
              <CardTitle className="text-base font-bold">Hành động & Cài đặt</CardTitle>
            </CardHeader>
            <CardContent className="p-4 sm:p-5 pt-0 space-y-3">
              {noteType.is_owner ? (
                <div className="space-y-3 p-3 rounded-xl border border-primary/20 bg-primary/5 shadow-2xs">
                  <div className="flex items-center justify-between border-b border-primary/10 pb-1.5 mb-1.5">
                    <span className="text-[10px] font-black tracking-wider text-muted-foreground uppercase">Bảng điều khiển Tác giả</span>
                    <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[9px] font-extrabold text-primary">
                      Tác giả
                    </span>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground font-medium">Trạng thái chia sẻ:</span>
                      {noteType.publish_status === 'published' && (
                        <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold px-2 py-0.5 rounded-md text-[10px]">
                          <Globe className="mr-1 size-3 text-emerald-500" />
                          Đang hiển thị
                        </Badge>
                      )}
                      {noteType.publish_status === 'unlisted' && (
                        <Badge variant="outline" className="border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400 font-bold px-2 py-0.5 rounded-md text-[10px]">
                          <Globe className="mr-1 size-3 text-blue-500" />
                          Không công khai
                        </Badge>
                      )}
                      {noteType.publish_status === 'private' && (
                        <Badge variant="outline" className="border-destructive/30 bg-destructive/10 text-destructive font-bold px-2 py-0.5 rounded-md text-[10px]">
                          <Lock className="mr-1 size-3 text-destructive" />
                          Đã thu hồi (Riêng tư)
                        </Badge>
                      )}
                      {noteType.publish_status === 'archived' && (
                        <Badge variant="outline" className="border-slate-500/30 bg-slate-500/10 text-slate-500 font-bold px-2 py-0.5 rounded-md text-[10px]">
                          <Lock className="mr-1 size-3 text-slate-500" />
                          Đã lưu trữ
                        </Badge>
                      )}
                    </div>
                  </div>

                  <div className="grid gap-2 pt-1">
                    {noteType.publish_status === 'published' || noteType.publish_status === 'unlisted' ? (
                      <Button
                        variant="destructive"
                        size="sm"
                        className="w-full font-bold text-xs h-9 rounded-xl flex items-center justify-center gap-1.5"
                        onClick={() => {
                          if (
                            window.confirm(
                              'Bạn có chắc chắn muốn thu hồi loại thẻ này khỏi Marketplace?\n\nNgười dùng khác sẽ không thể tìm thấy hoặc cài đặt loại thẻ này nữa. Những người đã cài đặt trước đó vẫn có thể tiếp tục sử dụng.'
                            )
                          ) {
                            publishStatusMutation.mutate('private')
                          }
                        }}
                        disabled={publishStatusMutation.isPending}
                      >
                        <EyeOff className="size-3.5" />
                        Thu hồi loại thẻ
                      </Button>
                    ) : (
                      <Button
                        variant="default"
                        size="sm"
                        className="w-full font-bold text-xs h-9 rounded-xl flex items-center justify-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white"
                        onClick={() => {
                          publishStatusMutation.mutate('published')
                        }}
                        disabled={publishStatusMutation.isPending}
                      >
                        <Globe className="size-3.5" />
                        Xuất bản lại loại thẻ
                      </Button>
                    )}

                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full font-bold text-xs h-9 rounded-xl flex items-center justify-center gap-1.5"
                      asChild
                    >
                      <Link to={`/marketplace/note-types/publish?id=${noteType.id}&edit=1`}>
                        <Edit3 className="size-3.5 text-primary" />
                        Chỉnh sửa thông tin
                      </Link>
                    </Button>
                  </div>
                </div>
              ) : noteType.is_installed ? (
                <Button className="w-full h-10 sm:h-11 font-bold text-xs sm:text-sm border-emerald-500/40 text-emerald-600 dark:text-emerald-400 rounded-xl" variant="outline" disabled>
                  <CheckCircle className="mr-1.5 size-4" />
                  Đã cài đặt loại thẻ
                </Button>
              ) : (
                <Button
                  className="w-full h-11 sm:h-12 font-bold text-sm sm:text-base shadow-md bg-gradient-to-r from-primary to-primary/90 hover:opacity-95 text-primary-foreground rounded-xl"
                  size="lg"
                  onClick={() => installMutation.mutate()}
                  disabled={installMutation.isPending}
                >
                  {installMutation.isPending ? (
                    <Loader2 className="mr-2 size-5 animate-spin" />
                  ) : (
                    <Download className="mr-2 size-5" />
                  )}
                  {noteType.pricing_mode === 'paid' ? 'Mua Note Type' : 'Tải xuống & Cài đặt'}
                </Button>
              )}

              {!noteType.is_owner ? (
                <Button
                  className="w-full h-9 sm:h-10 font-semibold text-xs sm:text-sm rounded-xl"
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

              <Button
                className="w-full h-9 sm:h-10 font-semibold text-xs sm:text-sm rounded-xl"
                variant="ghost"
                size="sm"
                onClick={handleCopyLink}
              >
                {isCopied ? <Check className="mr-1.5 size-4 text-emerald-500" /> : <Copy className="mr-1.5 size-4 text-muted-foreground" />}
                {isCopied ? 'Đã sao chép liên kết' : 'Sao chép link chia sẻ'}
              </Button>

              <div className="pt-3 border-t border-border/60 text-xs text-muted-foreground space-y-1.5">
                <div className="flex items-center gap-2">
                  <User className="size-4 text-primary" />
                  <span>Tác giả: <strong className="text-foreground">{authorName}</strong></span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </Page>
  )
}

