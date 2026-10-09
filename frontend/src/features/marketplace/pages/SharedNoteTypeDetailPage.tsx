import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  Award,
  Check,
  CheckCircle,
  Download,
  Edit3,
  EyeOff,
  Globe,
  Layers,
  Loader2,
  Palette,
  Share2,
  Star,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { CardPreviewPanel } from '@/entities/flashcard'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { SharedNoteTypeSidebar } from '../components/notetype-detail/SharedNoteTypeSidebar'
import { SharedNoteTypeReviews } from '../components/notetype-detail/SharedNoteTypeReviews'

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
  const { t, i18n } = useTranslation('marketplace')
  const numberLocale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  const [previewSide, setPreviewSide] = useState<'front' | 'back'>('front')
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('')
  const [isCopied, setIsCopied] = useState(false)

  // Rating state
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
  const firstTemplateId = noteType?.templates?.[0]?.id

  useEffect(() => {
    if (firstTemplateId && !selectedTemplateId) {
      setSelectedTemplateId(firstTemplateId)
    }
  }, [firstTemplateId, selectedTemplateId])

  // Template Preview Query
  const previewQuery = useQuery({
    queryKey: ['shared-note-type-preview', id, selectedTemplateId],
    // The preview endpoint renders server-side and only accepts POST.
    queryFn: () =>
      appApi.mutate<PreviewResponse>(
        `/api/shared/note-types/${id}/templates/${selectedTemplateId}/preview`,
        'POST'
      ),
    enabled: Boolean(id && selectedTemplateId),
  })

  // Install Mutation
  const installMutation = useMutation({
    mutationFn: () => appApi.mutate(`/api/shared/note-types/${id}/install`, 'POST'),
    onSuccess: (data: any) => {
      if (data?.payment_required && data?.order?.active_attempt?.checkout_url) {
        window.location.href = data.order.active_attempt.checkout_url
        return
      }
      queryClient.invalidateQueries({ queryKey: ['shared-note-type-detail', id] })
      queryClient.invalidateQueries({ queryKey: ['note-types'] })
      toast.success(
        t('detail.install_notetype_success', 'Cài đặt Note Type thành công! Mẫu đã được lưu vào thư viện của bạn.')
      )
    },
    onError: (err: any) => {
      toast.error(err?.message || t('common.error', 'Không thể cài đặt loại thẻ này.'))
    },
  })

  // Save/Bookmark Mutation
  const saveMutation = useMutation({
    mutationFn: (currentlySaved: boolean) =>
      appApi.mutate(
        `/api/shared/note-types/${id}/save`,
        currentlySaved ? 'DELETE' : 'POST'
      ),
    onSuccess: (_, currentlySaved) => {
      queryClient.invalidateQueries({ queryKey: ['shared-note-type-detail', id] })
      toast.success(
        currentlySaved
          ? t('notetype_detail.toast_unsaved', 'Đã bỏ lưu loại thẻ')
          : t('notetype_detail.toast_saved', 'Đã lưu loại thẻ')
      )
    },
    onError: (err: any) => {
      toast.error(err?.message || t('common.error', 'Không thể cập nhật trạng thái lưu.'))
    },
  })

  // Rate Mutation
  const rateMutation = useMutation({
    mutationFn: () =>
      appApi.mutate(`/api/shared/note-types/${id}/rate`, 'POST', {
        rating: ratingScore,
        comment: ratingComment.trim() || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shared-note-type-detail', id] })
      setSubmitSuccess(
        t('detail.reviews.success_toast', 'Đã gửi đánh giá thành công! Cảm ơn đóng góp của bạn.')
      )
      setSubmitError(null)
      setRatingComment('')
    },
    onError: (err: any) => {
      setSubmitError(err?.message || t('common.error', 'Không thể gửi đánh giá. Vui lòng thử lại.'))
    },
  })

  // Publish Status Mutation for Creator
  const publishStatusMutation = useMutation({
    mutationFn: (newStatus: 'private' | 'published') =>
      appApi.mutate(`/api/creator/note-types/${id}/publish-status`, 'PATCH', {
        publish_status: newStatus,
      }),
    onSuccess: (_, newStatus) => {
      queryClient.invalidateQueries({ queryKey: ['shared-note-type-detail', id] })
      toast.success(
        newStatus === 'private'
          ? t('notetype_detail.toast_revoked', 'Đã thu hồi loại thẻ khỏi Marketplace.')
          : t('notetype_detail.toast_republished', 'Đã xuất bản lại loại thẻ lên Marketplace.')
      )
    },
    onError: (err: any) => {
      toast.error(err?.message || t('common.error', 'Không thể cập nhật trạng thái xuất bản.'))
    },
  })

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href)
    setIsCopied(true)
    toast.success(t('notetype_detail.toast_copied', 'Đã sao chép liên kết!'))
    setTimeout(() => setIsCopied(false), 2000)
  }

  if (noteTypeQuery.isPending) {
    return (
      <Page>
        <PageLoading label={t('notetype_detail.loading', 'Đang tải thông tin cấu trúc thẻ…')} />
      </Page>
    )
  }

  if (noteTypeQuery.isError || !noteType) {
    return (
      <Page>
        <PageError error={noteTypeQuery.error || new Error(t('notetype_detail.not_found', 'Không tìm thấy cấu trúc thẻ'))} />
      </Page>
    )
  }

  const titleName = noteType.title || noteType.name || t('card.no_title', 'Cấu trúc thẻ không tên')
  const authorName =
    noteType.author_profile?.username || noteType.author?.username || t('card.community_author', 'Cộng đồng Flama')
  const tagsList = noteType.display_tags || noteType.tags || []
  const fields = noteType.field_defs || []
  const effectiveStar = hoverScore !== null ? hoverScore : ratingScore

  return (
    <Page className="space-y-4 sm:space-y-6 relative px-2.5 sm:px-6 lg:px-8 py-3 sm:py-6">
      <AmbientBackground intensity="subtle" />

      <PageHeader
        title={titleName}
        description={noteType.preview_text || noteType.description || t('notetype_detail.header_desc', 'Chi tiết cấu trúc thẻ trên marketplace Flama.')}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="h-8 sm:h-9 px-3 sm:px-3.5 text-xs font-semibold rounded-xl"
              onClick={handleCopyLink}
            >
              {isCopied ? <Check className="mr-1.5 size-3.5 text-emerald-500" /> : <Share2 className="mr-1.5 size-3.5 text-primary" />}
              {isCopied ? t('notetype_detail.toast_copied', 'Đã chép link') : t('common.share', 'Chia sẻ')}
            </Button>
            <Button variant="outline" size="sm" asChild className="group h-8 sm:h-9 px-3 sm:px-3.5 text-xs font-semibold rounded-xl">
              <Link to="/marketplace/note-types">
                <ArrowLeft className="mr-1 sm:mr-1.5 size-3.5 group-hover:-translate-x-0.5 transition-transform" />
                {t('common.back', 'Quay lại')}
              </Link>
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 sm:gap-5 lg:grid-cols-[1fr_340px]">
        {/* Main Left Content */}
        <div className="space-y-4 sm:space-y-5">
          {/* Main Card */}
          <Card className="border-border/80 bg-card shadow-xs rounded-2xl">
            <CardHeader className="space-y-3 p-4 sm:p-6 pb-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary" className="px-2.5 py-0.5 text-xs font-bold rounded-md">
                    {noteType.primary_category || t('marketplace.tab_notetypes', 'Loại thẻ')}
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
                  {noteType.price_display || t('card.free', 'Miễn phí')}
                </span>
              </div>

              <CardTitle className="text-2xl font-black tracking-tight text-foreground sm:text-3xl leading-tight">
                {titleName}
              </CardTitle>

              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                {noteType.author_profile?.username || noteType.author?.username ? (
                  <Link
                    to={`/profile/${noteType.author_profile?.username || noteType.author?.username}`}
                    className="flex items-center gap-1.5 hover:text-primary transition-colors group/author"
                  >
                    <div className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px] ring-1 ring-primary/20 group-hover/author:ring-primary">
                      {authorName.charAt(0).toUpperCase()}
                    </div>
                    <span className="font-semibold text-foreground group-hover/author:text-primary">{authorName}</span>
                  </Link>
                ) : (
                  <div className="flex items-center gap-1.5">
                    <div className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px]">
                      {authorName.charAt(0).toUpperCase()}
                    </div>
                    <span className="font-semibold text-foreground">{authorName}</span>
                  </div>
                )}
                <span>•</span>
                <span className="flex items-center gap-1 font-medium text-emerald-600 dark:text-emerald-400">
                  <CheckCircle className="size-3.5" /> Flama Marketplace
                </span>
              </div>
            </CardHeader>

            <CardContent className="p-5 sm:p-6 pt-0 space-y-4">
              <p className="text-xs sm:text-sm leading-relaxed text-muted-foreground font-normal">
                {noteType.description || t('card.no_desc_notetype', 'Chưa có mô tả chi tiết cho loại thẻ này.')}
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
                    <span>{t('detail.author.rating', 'Đánh giá')}</span>
                  </div>
                  <div className="mt-1 flex items-center justify-center gap-1 font-extrabold text-base text-foreground">
                    <span className="tabular-nums">{noteType.rating_avg.toFixed(1)}</span>
                    <span className="text-xs font-normal text-muted-foreground tabular-nums">({noteType.rating_count})</span>
                  </div>
                </div>

                <div className="rounded-xl border border-border/80 bg-muted/30 p-3.5 sm:p-4 text-center transition-all hover:bg-muted/50">
                  <div className="flex items-center justify-center gap-1 text-xs font-semibold text-muted-foreground">
                    <Download className="size-3.5 text-primary" />
                    <span>{t('card.install_unit', 'Lượt cài')}</span>
                  </div>
                  <div className="mt-1 font-extrabold text-base text-foreground tabular-nums">
                    {noteType.install_count.toLocaleString(numberLocale)}
                  </div>
                </div>

                <div className="rounded-xl border border-border/80 bg-muted/30 p-3.5 sm:p-4 text-center transition-all hover:bg-muted/50 col-span-2 sm:col-span-1">
                  <div className="flex items-center justify-center gap-1 text-xs font-semibold text-muted-foreground">
                    <Layers className="size-3.5 text-primary" />
                    <span>{t('notetype_detail.field_col_name', 'Trường')}</span>
                  </div>
                  <div className="mt-1 font-extrabold text-base text-foreground tabular-nums">
                    {fields.length} {t('notetype_detail.fields_unit', 'trường')}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Mobile-Only Quick Action Card */}
          <div className="block lg:hidden">
            <Card className="border-primary/30 bg-primary/5 shadow-xs rounded-2xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-foreground">
                  {noteType.pricing_mode === 'free' ? t('card.free', 'Miễn phí') : noteType.price_display}
                </span>
                <Badge variant="outline" className="text-xs font-semibold">
                  {noteType.install_count.toLocaleString(numberLocale)} {t('card.install_unit', 'lượt cài')}
                </Badge>
              </div>

              {noteType.is_owner ? (
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-10 text-xs font-bold rounded-xl"
                    asChild
                  >
                    <Link to={`/marketplace/note-types/publish?id=${noteType.id}&edit=1`}>
                      <Edit3 className="mr-1.5 size-3.5 text-primary" /> {t('notetype_detail.btn_edit_info', 'Sửa thông tin')}
                    </Link>
                  </Button>
                  {noteType.publish_status === 'published' || noteType.publish_status === 'unlisted' ? (
                    <Button
                      variant="destructive"
                      size="sm"
                      className="h-10 text-xs font-bold rounded-xl"
                      onClick={() => {
                        if (
                          window.confirm(
                            t('notetype_detail.confirm_revoke', 'Bạn có chắc chắn muốn thu hồi loại thẻ này khỏi Marketplace?')
                          )
                        ) {
                          publishStatusMutation.mutate('private')
                        }
                      }}
                      disabled={publishStatusMutation.isPending}
                    >
                      <EyeOff className="mr-1.5 size-3.5" /> {t('notetype_detail.btn_revoke', 'Thu hồi')}
                    </Button>
                  ) : (
                    <Button
                      variant="default"
                      size="sm"
                      className="h-10 text-xs font-bold rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white"
                      onClick={() => publishStatusMutation.mutate('published')}
                      disabled={publishStatusMutation.isPending}
                    >
                      <Globe className="mr-1.5 size-3.5" /> {t('notetype_detail.btn_republish', 'Xuất bản lại')}
                    </Button>
                  )}
                </div>
              ) : noteType.is_installed ? (
                <Button className="w-full h-10 font-bold text-xs border-emerald-500/40 text-emerald-600 dark:text-emerald-400 rounded-xl" variant="outline" disabled>
                  <CheckCircle className="mr-1.5 size-4" /> {t('notetype_detail.btn_installed', 'Đã cài đặt cấu trúc thẻ')}
                </Button>
              ) : (
                <Button
                  className="w-full h-11 font-bold text-sm shadow-xs bg-primary hover:bg-primary/90 text-primary-foreground rounded-xl"
                  onClick={() => installMutation.mutate()}
                  disabled={installMutation.isPending}
                >
                  {installMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 size-4 animate-spin" />
                      {noteType.pricing_mode === 'paid' ? t('detail.creating_payment', 'Đang tạo thanh toán…') : t('detail.installing', 'Đang cài đặt cấu trúc thẻ…')}
                    </>
                  ) : (
                    <>
                      <Download className="mr-2 size-4" />
                      {noteType.pricing_mode === 'paid' ? t('notetype_detail.btn_buy', 'Mua Cấu trúc thẻ') : t('notetype_detail.btn_install', 'Tải xuống & Cài đặt')}
                    </>
                  )}
                </Button>
              )}
            </Card>
          </div>

          {/* Live Preview Section */}
          <CardPreviewPanel
            cardId={`note-type-preview-${id}`}
            side={previewSide}
            onSideChange={setPreviewSide}
            templates={templates.map((tmpl) => ({ id: tmpl.id, name: tmpl.name }))}
            selectedTemplateId={selectedTemplateId || undefined}
            onSelectTemplate={setSelectedTemplateId}
            frontPayload={previewQuery.data?.front_renderer_payload}
            backPayload={previewQuery.data?.back_renderer_payload}
            frontHtml={previewQuery.data?.front_html}
            backHtml={previewQuery.data?.back_html}
            scope="shared_note_type_preview"
            scopeId={id}
            isLoading={previewQuery.isPending}
            title={t('notetype_detail.title_preview', 'Xem trước Cấu trúc thẻ (Live Previewer)')}
            subtitle={t('detail.preview.subtitle', 'Mô phỏng hiển thị mặt trước và mặt sau dựa trên giao diện thẻ')}
            containerHeightClass="h-[clamp(20rem,50vh,32rem)] min-h-[250px]"
          />

          {/* Fields Structure Card */}
          <Card className="border-border shadow-xs rounded-2xl">
            <CardHeader className="p-4 sm:p-5 pb-3">
              <div className="flex items-center gap-2">
                <Layers className="size-4 text-primary" />
                <CardTitle className="text-base font-bold">
                  {t('notetype_detail.fields_list_title', 'Danh sách trường thông tin (Fields)')}
                </CardTitle>
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

          {/* Attached Card Templates Relationship Card */}
          {templates.length > 0 ? (
            <Card className="border-border shadow-xs rounded-2xl">
              <CardHeader className="p-4 sm:p-5 pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Palette className="size-4 text-primary" />
                    <CardTitle className="text-base font-bold">
                      {t('notetype_detail.templates_title', { defaultValue: 'Giao diện thẻ đi kèm (Card Templates)' })}
                    </CardTitle>
                  </div>
                  <Badge variant="secondary" className="text-xs font-semibold">
                    {templates.length} {t('notetype_detail.template_unit', { defaultValue: 'giao diện' })}
                  </Badge>
                </div>
                <CardDescription className="text-xs text-muted-foreground mt-1">
                  {t('notetype_detail.templates_desc', {
                    defaultValue: 'Mỗi cấu trúc thẻ có thể chứa một hoặc nhiều giao diện hiển thị (Card Templates) độc lập.',
                  })}
                </CardDescription>
              </CardHeader>
              <CardContent className="p-4 sm:p-5 pt-0">
                <div className="grid gap-2.5 sm:grid-cols-2">
                  {templates.map((tmpl, idx) => (
                    <div
                      key={tmpl.id}
                      className={`flex items-center justify-between p-3 sm:p-3.5 rounded-xl border transition-all ${
                        tmpl.id === selectedTemplateId
                          ? 'border-primary/50 bg-primary/5 ring-1 ring-primary/20 shadow-2xs'
                          : 'border-border/80 bg-muted/20 hover:bg-muted/40'
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div
                          className={`flex size-8 shrink-0 items-center justify-center rounded-lg transition-colors ${
                            tmpl.id === selectedTemplateId
                              ? 'bg-primary text-primary-foreground shadow-2xs'
                              : 'bg-primary/10 text-primary'
                          }`}
                        >
                          <Layers className="size-4" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <p className="text-xs font-bold text-foreground truncate">{tmpl.name}</p>
                            <span className="text-[10px] text-muted-foreground font-mono">#{idx + 1}</span>
                          </div>
                          <p className="text-[11px] text-muted-foreground truncate">
                            {tmpl.id === selectedTemplateId
                              ? t('notetype_detail.template_active_preview', { defaultValue: 'Đang xem trước' })
                              : t('notetype_detail.template_available', { defaultValue: 'Giao diện hiển thị' })}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0 ml-2">
                        {tmpl.id !== selectedTemplateId ? (
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-7 px-2.5 text-[11px] font-semibold text-primary hover:text-primary hover:bg-primary/10 rounded-lg shrink-0 cursor-pointer"
                            onClick={() => setSelectedTemplateId(tmpl.id)}
                          >
                            {t('notetype_detail.btn_select_preview', { defaultValue: 'Xem' })}
                          </Button>
                        ) : (
                          <Badge variant="default" className="text-[10px] px-2 py-0.5 rounded-md font-semibold">
                            {t('notetype_detail.badge_previewing', { defaultValue: 'Đang xem' })}
                          </Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : null}

          {/* Reviews Card */}
          <SharedNoteTypeReviews
            canRate={noteType.can_rate}
            ratingScore={ratingScore}
            setRatingScore={setRatingScore}
            hoverScore={hoverScore}
            setHoverScore={setHoverScore}
            effectiveStar={effectiveStar}
            ratingComment={ratingComment}
            setRatingComment={setRatingComment}
            submitError={submitError}
            submitSuccess={submitSuccess}
            rateMutation={rateMutation}
            recentReviews={noteType.recent_reviews}
          />
        </div>

        {/* Sidebar */}
        <SharedNoteTypeSidebar
          id={id!}
          isOwner={noteType.is_owner}
          isInstalled={noteType.is_installed}
          pricingMode={noteType.pricing_mode}
          priceDisplay={noteType.price_display}
          installCount={noteType.install_count}
          publishStatus={noteType.publish_status}
          isSaved={noteType.is_saved}
          isCopied={isCopied}
          authorName={authorName}
          onInstall={() => installMutation.mutate()}
          isInstallPending={installMutation.isPending}
          onSave={() => saveMutation.mutate(noteType.is_saved)}
          isSavePending={saveMutation.isPending}
          onCopyLink={handleCopyLink}
          onUpdatePublishStatus={(status) => publishStatusMutation.mutate(status)}
          isPublishStatusPending={publishStatusMutation.isPending}
        />
      </div>
    </Page>
  )
}
