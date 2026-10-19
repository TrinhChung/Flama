import { useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Check,
  CheckCircle,
  Download,
  History,
  Info,
  Loader2,
  Settings2,
  Share2,
  ShieldCheck,
  SlidersHorizontal,
} from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { AmbientBackground } from '@/components/ambient-background'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CardPreviewPanel } from '@/entities/flashcard'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import {
  fetchMarketTemplate,
  installMarketTemplate,
  previewMarketTemplate,
  templateMarketQueryKeys,
} from '../api/templateMarketApi'
import { PublishTemplateDialog } from '../components/PublishTemplateDialog'
import type { MarketTemplateDetail } from '../model/types'

function formatDate(value: string | null, locale: string) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString(locale)
}

export function TemplateMarketDetailPage() {
  const { id = '' } = useParams<{ id: string }>()
  const { t, i18n } = useTranslation('marketplace')
  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'
  const queryClient = useQueryClient()
  const [previewSide, setPreviewSide] = useState<'front' | 'back'>('front')
  const [manageOpen, setManageOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  const detailQuery = useQuery({
    queryKey: templateMarketQueryKeys.detail(id),
    queryFn: ({ signal }) => fetchMarketTemplate(id, signal),
    enabled: Boolean(id),
  })
  const previewQuery = useQuery({
    queryKey: templateMarketQueryKeys.preview(id),
    queryFn: () => previewMarketTemplate(id),
    enabled: Boolean(id) && detailQuery.isSuccess,
  })
  const installMutation = useMutation({
    mutationFn: () => installMarketTemplate(id),
    onSuccess: (result) => {
      const checkoutUrl = result.order?.active_attempt?.checkout_url
      if (result.payment_required && checkoutUrl) {
        window.location.href = checkoutUrl
        return
      }
      void queryClient.invalidateQueries({ queryKey: templateMarketQueryKeys.all })
      void queryClient.invalidateQueries({ queryKey: ['card-template'] })
      toast.success(result.already_installed ? t('templates.detail.toast_already') : t('templates.detail.toast_installed'))
    },
    onError: (error: Error) => toast.error(error.message || t('templates.detail.error_install')),
  })

  const handleCopyLink = () => {
    void navigator.clipboard?.writeText(window.location.href)
    setCopied(true)
    toast.success(t('notetype_detail.toast_copied', { defaultValue: 'Đã sao chép liên kết!' }))
    window.setTimeout(() => setCopied(false), 2000)
  }

  if (detailQuery.isPending) return <Page><PageLoading label={t('templates.loading')} /></Page>
  if (detailQuery.error || !detailQuery.data) {
    return <Page><PageError error={detailQuery.error || new Error(t('templates.detail.not_found'))} /></Page>
  }
  const item = detailQuery.data
  const authorName = item.author.username || t('card.community_author', { defaultValue: 'Cộng đồng Flama' })

  return (
    <Page className="space-y-4 sm:space-y-6 relative px-2.5 sm:px-6 lg:px-8 py-3 sm:py-6">
      <AmbientBackground intensity="subtle" />
      <PageHeader
        title={item.name}
        description={item.description || t('templates.no_desc')}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="h-8 sm:h-9 px-3 sm:px-3.5 text-xs font-semibold rounded-xl" onClick={handleCopyLink}>
              {copied ? <Check className="mr-1.5 size-3.5 text-emerald-500" /> : <Share2 className="mr-1.5 size-3.5 text-primary" />}
              {t('common.share', { defaultValue: 'Chia sẻ' })}
            </Button>
            <Button variant="outline" size="sm" asChild className="group h-8 sm:h-9 px-3 sm:px-3.5 text-xs font-semibold rounded-xl">
              <Link to="/marketplace/templates">
                <ArrowLeft className="mr-1 sm:mr-1.5 size-3.5 group-hover:-translate-x-0.5 transition-transform" />
                {t('common.back', { defaultValue: 'Quay lại' })}
              </Link>
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 sm:gap-5 lg:grid-cols-[1fr_340px]">
        <div className="space-y-4 sm:space-y-5 min-w-0">
          <Card className="border-border/80 bg-card shadow-xs rounded-2xl">
            <CardHeader className="space-y-3 p-4 sm:p-6 pb-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Badge variant="secondary" className="px-2.5 py-0.5 text-xs font-bold rounded-md">
                  {item.primary_category || t('card.general_category', { defaultValue: 'Chung' })}
                </Badge>
                <PriceChip item={item} />
              </div>
              <CardTitle className="text-2xl font-black tracking-tight text-foreground sm:text-3xl leading-tight">{item.name}</CardTitle>
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <div className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px] ring-1 ring-primary/20">
                  {authorName.charAt(0).toUpperCase()}
                </div>
                {item.author.username ? (
                  <Link to={`/profile/${item.author.username}`} className="font-semibold text-foreground hover:text-primary">{authorName}</Link>
                ) : <span className="font-semibold text-foreground">{authorName}</span>}
                {!item.is_listed ? <Badge variant="outline" className="text-[10px]">{t('templates.detail.badge_unlisted')}</Badge> : null}
              </div>
            </CardHeader>
            <CardContent className="p-5 sm:p-6 pt-0 space-y-4">
              <p className="text-xs sm:text-sm leading-relaxed text-muted-foreground whitespace-pre-line">{item.description || t('templates.no_desc')}</p>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <Stat icon={<Download className="size-3.5 text-primary" />} label={t('templates.detail.downloads')} value={item.install_count.toLocaleString(locale)} />
                <Stat icon={<SlidersHorizontal className="size-3.5 text-primary" />} label={t('templates.inputs_title')} value={String(item.input_count)} />
                <Stat icon={<History className="size-3.5 text-primary" />} label={t('templates.detail.version')} value={item.version_label || '—'} className="col-span-2 sm:col-span-1" />
              </div>
            </CardContent>
          </Card>

          <div className="block lg:hidden">
            <ActionCard item={item} pending={installMutation.isPending} onInstall={() => installMutation.mutate()} onManage={() => setManageOpen(true)} />
          </div>

          <CardPreviewPanel
            cardId={`market-template-preview-${id}`}
            side={previewSide}
            onSideChange={setPreviewSide}
            frontPayload={previewQuery.data?.front_renderer_payload}
            backPayload={previewQuery.data?.back_renderer_payload}
            frontHtml={previewQuery.data?.front_html}
            backHtml={previewQuery.data?.back_html}
            scope="market_template_preview"
            scopeId={id}
            isLoading={previewQuery.isPending}
            error={previewQuery.error?.message ?? null}
            title={t('templates.detail.preview_title')}
            subtitle={t('templates.detail.preview_subtitle')}
            containerHeightClass="h-[clamp(20rem,50vh,32rem)] min-h-[250px]"
          />

          <Card className="border-border shadow-xs rounded-2xl">
            <CardHeader className="p-4 sm:p-5 pb-3">
              <div className="flex items-center gap-2">
                <SlidersHorizontal className="size-4 text-primary" />
                <CardTitle className="text-base font-bold">{t('templates.inputs_title')}</CardTitle>
              </div>
              <p className="text-xs text-muted-foreground">{t('templates.detail.inputs_desc')}</p>
            </CardHeader>
            <CardContent className="p-4 sm:p-5 pt-0">
              {item.inputs.length ? (
                <div className="flex flex-wrap gap-2">
                  {item.inputs.map((input) => (
                    <Badge key={input.key} variant="secondary" className="px-3 py-1.5 text-xs font-bold border border-border/60 rounded-xl">
                      {input.label}
                      <span className="ml-1 font-mono text-[10px] font-normal text-muted-foreground">{input.key} · {input.type}</span>
                    </Badge>
                  ))}
                </div>
              ) : <p className="text-xs text-muted-foreground">{t('templates.detail.no_inputs')}</p>}
            </CardContent>
          </Card>

          {item.recent_releases.length ? (
            <Card className="border-border shadow-xs rounded-2xl">
              <CardHeader className="p-4 sm:p-5 pb-3">
                <div className="flex items-center gap-2">
                  <History className="size-4 text-primary" />
                  <CardTitle className="text-base font-bold">{t('templates.detail.releases_title')}</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="p-4 sm:p-5 pt-0 space-y-2">
                {item.recent_releases.map((release) => (
                  <div key={release.id} className="flex items-start justify-between gap-3 rounded-xl border border-border/70 bg-muted/20 p-3 text-xs">
                    <div className="min-w-0">
                      <p className="font-bold text-foreground">v{release.version_label}</p>
                      {release.change_note ? <p className="mt-0.5 text-muted-foreground line-clamp-2">{release.change_note}</p> : null}
                    </div>
                    <span className="shrink-0 text-muted-foreground tabular-nums">{formatDate(release.published_at, locale)}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : null}
        </div>

        <aside className="hidden lg:block">
          <div className="sticky top-20 space-y-4">
            <ActionCard item={item} pending={installMutation.isPending} onInstall={() => installMutation.mutate()} onManage={() => setManageOpen(true)} />
          </div>
        </aside>
      </div>

      {item.is_owner ? (
        <PublishTemplateDialog
          open={manageOpen}
          onOpenChange={(open) => {
            setManageOpen(open)
            if (!open) void queryClient.invalidateQueries({ queryKey: templateMarketQueryKeys.detail(id) })
          }}
          templateId={item.id}
        />
      ) : null}
    </Page>
  )
}

function PriceChip({ item }: { item: MarketTemplateDetail }) {
  const { t } = useTranslation('marketplace')
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-extrabold border ${
      item.pricing_mode === 'free'
        ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30'
        : 'bg-primary/10 text-primary border-primary/30'
    }`}>
      {item.pricing_mode === 'free' ? t('card.free', { defaultValue: 'Miễn phí' }) : item.price_display}
    </span>
  )
}

function Stat({ icon, label, value, className = '' }: { icon: ReactNode; label: string; value: string; className?: string }) {
  return (
    <div className={`rounded-xl border border-border/80 bg-muted/30 p-3.5 sm:p-4 text-center ${className}`}>
      <div className="flex items-center justify-center gap-1 text-xs font-semibold text-muted-foreground">{icon}<span>{label}</span></div>
      <div className="mt-1 font-extrabold text-base text-foreground tabular-nums">{value}</div>
    </div>
  )
}

function ActionCard({ item, pending, onInstall, onManage }: {
  item: MarketTemplateDetail
  pending: boolean
  onInstall: () => void
  onManage: () => void
}) {
  const { t } = useTranslation('marketplace')
  const needsPayment = item.pricing_mode === 'paid' && !item.is_purchased
  return (
    <Card className="border-primary/30 bg-primary/5 shadow-xs rounded-2xl p-4 sm:p-5 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-lg font-black text-foreground">
          {item.pricing_mode === 'free' ? t('card.free', { defaultValue: 'Miễn phí' }) : item.price_display}
        </span>
        {item.is_purchased ? <Badge variant="outline" className="text-[10px] text-emerald-600 border-emerald-500/40">{t('templates.detail.badge_purchased')}</Badge> : null}
      </div>

      {item.is_owner ? (
        <div className="space-y-2">
          <Button className="w-full h-10 font-bold text-xs rounded-xl" onClick={onManage}>
            <Settings2 className="mr-1.5 size-4" />{t('templates.detail.btn_manage')}
          </Button>
          <Button variant="outline" className="w-full h-10 text-xs font-semibold rounded-xl" asChild>
            <Link to={`/card-templates/${encodeURIComponent(item.id)}`}>{t('templates.detail.btn_edit_template')}</Link>
          </Button>
        </div>
      ) : item.is_installed ? (
        <div className="space-y-2">
          <Button variant="outline" className="w-full h-10 font-bold text-xs border-emerald-500/40 text-emerald-600 dark:text-emerald-400 rounded-xl" disabled>
            <CheckCircle className="mr-1.5 size-4" />{t('templates.in_library')}
          </Button>
          <Button className="w-full h-10 font-bold text-xs rounded-xl" asChild>
            <Link to={`/card-templates/${encodeURIComponent(item.installed_template_id || '')}`}>{t('templates.detail.btn_open_library')}</Link>
          </Button>
          <p className="text-[11px] text-muted-foreground">{t('templates.detail.apply_hint')}</p>
        </div>
      ) : (
        <Button className="w-full h-11 font-bold text-sm shadow-xs rounded-xl" onClick={onInstall} disabled={pending || (!item.is_listed && !item.is_purchased)}>
          {pending ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Download className="mr-2 size-4" />}
          {pending
            ? (needsPayment ? t('detail.creating_payment', { defaultValue: 'Đang tạo thanh toán…' }) : t('templates.detail.installing'))
            : (needsPayment ? t('templates.detail.btn_buy', { price: item.price_display }) : t('templates.detail.btn_install'))}
        </Button>
      )}

      <div className="space-y-1.5 border-t border-border/60 pt-3 text-[11px] text-muted-foreground">
        <p className="flex items-start gap-1.5"><ShieldCheck className="mt-0.5 size-3 shrink-0 text-primary" />{t('templates.detail.rule_updates')}</p>
        <p className="flex items-start gap-1.5"><Info className="mt-0.5 size-3 shrink-0 text-primary" />{t('templates.detail.rule_no_resale')}</p>
      </div>
    </Card>
  )
}
