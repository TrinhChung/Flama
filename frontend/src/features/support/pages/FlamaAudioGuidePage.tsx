import { useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faArrowRight,
  faArrowUpRightFromSquare,
  faBolt,
  faBookOpen,
  faCircleCheck,
  faCircleQuestion,
  faCircleXmark,
  faDesktop,
  faDownload,
  faRotateRight,
  faShieldHalved,
  faSliders,
  faTriangleExclamation,
  faVolumeHigh,
  faWrench,
} from '@fortawesome/free-solid-svg-icons'
import { LoaderCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { resolveBackendUrl } from '@/config/env'
import { ContextHelpButton } from '@/features/guide'
import { flamaAudioClient } from '@/lib/flamaAudioClient'
import { Page, PageHeader } from '@/shared/components/Page'

export function FlamaAudioGuidePage() {
  const { t } = useTranslation('support')
  const [serviceStatus, setServiceStatus] = useState<
    'unchecked' | 'checking' | 'online' | 'offline'
  >('unchecked')
  const downloadUrl = resolveBackendUrl('/api/download/flama-audio')
  const checksumUrl = resolveBackendUrl('/api/download/flama-audio.sha256')

  const handleCheckConnection = async () => {
    setServiceStatus('checking')
    try {
      await flamaAudioClient.getHealth()
      setServiceStatus('online')
      toast.success(t('toast.audio_connected'))
    } catch {
      setServiceStatus('offline')
      toast.error(t('toast.audio_offline'))
    }
  }

  return (
    <Page className="max-w-5xl space-y-7">
      <PageHeader
        title={t('audio_guide.title')}
        description={t('audio_guide.description')}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              asChild
              variant="default"
              size="sm"
              className="gap-2 font-bold rounded-xl shadow-xs"
            >
              <a href={downloadUrl} target="_blank" rel="noopener noreferrer" download>
                <FontAwesomeIcon icon={faDownload} className="text-xs" />
                <span>{t('audio_guide.download_btn')}</span>
              </a>
            </Button>
            <Button
              asChild
              variant="outline"
              size="sm"
              className="gap-2 font-semibold rounded-xl"
            >
              <a href={checksumUrl} target="_blank" rel="noopener noreferrer" download>
                <FontAwesomeIcon icon={faShieldHalved} className="text-xs" />
                <span>{t('audio_guide.sha256_btn')}</span>
              </a>
            </Button>
            <ContextHelpButton
              guidePath="/guide/audio/flama-audio"
              guideTitle={t('audio_guide.context_help_guide_title', 'Cẩm nang Flama Audio Desktop')}
              troubleshootPath="/guide/troubleshooting/flama-audio"
              troubleshootTitle={t('audio_guide.context_help_troubleshoot_title', 'Khắc phục sự cố không nghe thấy tiếng')}
              label={t('audio_guide.docs_btn')}
            />
          </div>
        }
      />

      {/* Download Warning Alert */}
      <div className="flex items-start gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-amber-900 dark:text-amber-200">
        <FontAwesomeIcon
          icon={faTriangleExclamation}
          className="size-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5"
        />
        <div className="space-y-1 text-xs leading-relaxed">
          <h4 className="font-bold text-sm text-amber-800 dark:text-amber-300">
            {t('audio_guide.warning_title')}
          </h4>
          <p className="text-amber-800/90 dark:text-amber-200/90">
            {t('audio_guide.warning_desc')}
          </p>
          <div className="flex flex-wrap items-center gap-1.5 pt-0.5 text-[11px] font-medium text-amber-900 dark:text-amber-100">
            <span className="px-2 py-0.5 rounded-md bg-amber-500/20">
              {t('audio_guide.warning_steps.s1')}
            </span>
            <span>&rarr;</span>
            <span className="px-2 py-0.5 rounded-md bg-amber-500/20">
              {t('audio_guide.warning_steps.s2')}
            </span>
            <span>&rarr;</span>
            <span className="px-2 py-0.5 rounded-md bg-amber-500/20">
              {t('audio_guide.warning_steps.s3')}
            </span>
            <span>&rarr;</span>
            <span className="px-2 py-0.5 rounded-md bg-amber-500/20">
              {t('audio_guide.warning_steps.s4')}
            </span>
          </div>
        </div>
      </div>

      {/* Connection Test Banner */}
      <Card className="rounded-2xl border border-border/80 bg-card shadow-xs overflow-hidden">
        <CardContent className="flex flex-wrap items-center justify-between gap-4 p-4 sm:p-5">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary shrink-0">
              <FontAwesomeIcon icon={faDesktop} className="text-base" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-sm sm:text-base text-foreground">
                  {t('audio_guide.service_status.title')}
                </h3>
                {serviceStatus === 'online' && (
                  <Badge
                    variant="outline"
                    className="bg-emerald-500/10 text-emerald-600 border-emerald-500/30 text-[11px] font-semibold gap-1"
                  >
                    <FontAwesomeIcon icon={faCircleCheck} className="text-[10px]" />
                    {t('audio_guide.service_status.connected')}
                  </Badge>
                )}
                {serviceStatus === 'offline' && (
                  <Badge
                    variant="outline"
                    className="bg-rose-500/10 text-rose-600 border-rose-500/30 text-[11px] font-semibold gap-1"
                  >
                    <FontAwesomeIcon icon={faCircleXmark} className="text-[10px]" />
                    {t('audio_guide.service_status.offline')}
                  </Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {t('audio_guide.service_status.port_info')}
                {serviceStatus === 'offline' && (
                  <span className="ml-2 text-rose-600 dark:text-rose-400 font-medium">
                    &bull; {t('audio_guide.service_status.troubleshoot_hint')}{' '}
                    <Link
                      to="/guide/troubleshooting/flama-audio"
                      className="underline hover:text-rose-700"
                    >
                      {t('audio_guide.service_status.troubleshoot_link')}
                    </Link>
                  </span>
                )}
              </p>
            </div>
          </div>

          <Button
            size="sm"
            variant="outline"
            onClick={handleCheckConnection}
            disabled={serviceStatus === 'checking'}
            className="gap-2 text-xs rounded-xl font-semibold shrink-0"
          >
            {serviceStatus === 'checking' ? (
              <LoaderCircle className="size-3.5 animate-spin text-primary" />
            ) : (
              <FontAwesomeIcon icon={faRotateRight} className="text-xs text-primary" />
            )}
            <span>{t('audio_guide.service_status.check_btn')}</span>
          </Button>
        </CardContent>
      </Card>

      {/* Feature Highlights Grid */}
      <div className="grid gap-4 sm:gap-5 md:grid-cols-3">
        <Card className="rounded-2xl border border-border/80 bg-card hover:border-primary/50 hover:shadow-md transition-all">
          <CardHeader className="p-4 sm:p-5 pb-2">
            <div className="size-9 rounded-xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center mb-2">
              <FontAwesomeIcon icon={faBolt} className="text-sm" />
            </div>
            <CardTitle className="text-sm sm:text-base font-bold text-foreground">
              {t('audio_guide.features.unlimited.title')}
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground">
              {t('audio_guide.features.unlimited.desc')}
            </CardDescription>
          </CardHeader>
        </Card>

        <Card className="rounded-2xl border border-border/80 bg-card hover:border-primary/50 hover:shadow-md transition-all">
          <CardHeader className="p-4 sm:p-5 pb-2">
            <div className="size-9 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-2">
              <FontAwesomeIcon icon={faShieldHalved} className="text-sm" />
            </div>
            <CardTitle className="text-sm sm:text-base font-bold text-foreground">
              {t('audio_guide.features.pair.title')}
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground">
              {t('audio_guide.features.pair.desc')}
            </CardDescription>
          </CardHeader>
        </Card>

        <Card className="rounded-2xl border border-border/80 bg-card hover:border-primary/50 hover:shadow-md transition-all">
          <CardHeader className="p-4 sm:p-5 pb-2">
            <div className="size-9 rounded-xl bg-amber-500/10 text-amber-600 flex items-center justify-center mb-2">
              <FontAwesomeIcon icon={faSliders} className="text-sm" />
            </div>
            <CardTitle className="text-sm sm:text-base font-bold text-foreground">
              {t('audio_guide.features.engines.title')}
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground">
              {t('audio_guide.features.engines.desc')}
            </CardDescription>
          </CardHeader>
        </Card>
      </div>

      {/* Step by Step Setup Guide */}
      <Card className="rounded-2xl border border-border/80 bg-card shadow-xs overflow-hidden">
        <CardHeader className="bg-muted/30 p-4 sm:p-5 border-b border-border/70">
          <CardTitle className="text-sm sm:text-base font-bold text-foreground flex items-center gap-2">
            <FontAwesomeIcon icon={faVolumeHigh} className="text-primary text-sm" />
            <span>{t('audio_guide.steps.title')}</span>
          </CardTitle>
          <CardDescription className="text-xs text-muted-foreground">
            {t('audio_guide.steps.subtitle')}
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 space-y-5">
          <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
            {/* Step 1 */}
            <div className="rounded-xl border border-border/60 bg-muted/20 p-3.5 space-y-2">
              <div className="flex items-center gap-2">
                <span className="inline-flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold shrink-0">
                  1
                </span>
                <h4 className="font-bold text-xs sm:text-sm text-foreground">
                  {t('audio_guide.steps.s1_title')}
                </h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {t('audio_guide.steps.s1_desc')}
              </p>
            </div>

            {/* Step 2 */}
            <div className="rounded-xl border border-border/60 bg-muted/20 p-3.5 space-y-2">
              <div className="flex items-center gap-2">
                <span className="inline-flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold shrink-0">
                  2
                </span>
                <h4 className="font-bold text-xs sm:text-sm text-foreground">
                  {t('audio_guide.steps.s2_title')}
                </h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {t('audio_guide.steps.s2_desc')}
              </p>
            </div>

            {/* Step 3 */}
            <div className="rounded-xl border border-border/60 bg-muted/20 p-3.5 space-y-2">
              <div className="flex items-center gap-2">
                <span className="inline-flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold shrink-0">
                  3
                </span>
                <h4 className="font-bold text-xs sm:text-sm text-foreground">
                  {t('audio_guide.steps.s3_title')}
                </h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {t('audio_guide.steps.s3_desc')}
              </p>
            </div>

            {/* Step 4 */}
            <div className="rounded-xl border border-border/60 bg-muted/20 p-3.5 space-y-2">
              <div className="flex items-center gap-2">
                <span className="inline-flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold shrink-0">
                  4
                </span>
                <h4 className="font-bold text-xs sm:text-sm text-foreground">
                  {t('audio_guide.steps.s4_title')}
                </h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {t('audio_guide.steps.s4_desc')}
              </p>
            </div>
          </div>

          {/* Action Navigation Banner */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3.5 rounded-2xl border border-primary/30 bg-primary/5 p-4 sm:p-5">
            <div className="space-y-0.5 text-center sm:text-left">
              <h4 className="font-bold text-sm text-foreground flex items-center justify-center sm:justify-start gap-2">
                <FontAwesomeIcon icon={faDesktop} className="text-primary text-xs" />
                <span>{t('audio_guide.callout.title')}</span>
              </h4>
              <p className="text-xs text-muted-foreground">
                {t('audio_guide.callout.desc')}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto justify-center">
              <Button asChild size="sm" className="gap-2 font-bold rounded-xl shadow-xs">
                <Link to="/audio/deck-generator">
                  <span>{t('audio_guide.callout.open_studio')}</span>
                  <FontAwesomeIcon icon={faArrowRight} className="text-xs" />
                </Link>
              </Button>
              <Button
                asChild
                variant="outline"
                size="sm"
                className="gap-1.5 font-semibold rounded-xl"
              >
                <Link to="/browse">
                  <span>{t('audio_guide.callout.browse_cards')}</span>
                  <FontAwesomeIcon
                    icon={faArrowUpRightFromSquare}
                    className="text-[10px] opacity-70"
                  />
                </Link>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Troubleshooting & FAQ */}
      <Card className="rounded-2xl border border-border/80 bg-card shadow-xs overflow-hidden">
        <CardHeader className="bg-muted/30 p-4 sm:p-5 border-b border-border/70">
          <CardTitle className="text-sm sm:text-base font-bold text-foreground flex items-center gap-2">
            <FontAwesomeIcon icon={faCircleQuestion} className="text-primary text-sm" />
            <span>{t('audio_guide.faq.title')}</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 space-y-4 text-xs text-muted-foreground leading-relaxed">
          <div className="space-y-1">
            <h5 className="font-bold text-foreground text-xs sm:text-sm flex items-center gap-2">
              <FontAwesomeIcon
                icon={faCircleCheck}
                className="text-emerald-500 text-xs shrink-0"
              />
              <span>{t('audio_guide.faq.q1')}</span>
            </h5>
            <p className="pl-5 text-muted-foreground">
              {t('audio_guide.faq.a1')}{' '}
              <Link
                to="/guide/troubleshooting/flama-audio"
                className="text-primary font-semibold hover:underline inline-flex items-center gap-1"
              >
                {t('audio_guide.service_status.troubleshoot_link')}{' '}
                <FontAwesomeIcon
                  icon={faArrowUpRightFromSquare}
                  className="text-[9px]"
                />
              </Link>
            </p>
          </div>

          <div className="space-y-1">
            <h5 className="font-bold text-foreground text-xs sm:text-sm flex items-center gap-2">
              <FontAwesomeIcon
                icon={faCircleCheck}
                className="text-emerald-500 text-xs shrink-0"
              />
              <span>{t('audio_guide.faq.q2')}</span>
            </h5>
            <p className="pl-5 text-muted-foreground">{t('audio_guide.faq.a2')}</p>
          </div>

          {/* Quick Hub Links */}
          <div className="pt-2 border-t border-border/60">
            <p className="text-[11px] font-semibold text-foreground mb-2">
              {t('audio_guide.faq.related_docs')}
            </p>
            <div className="grid gap-2 sm:grid-cols-3">
              <Link
                to="/guide/audio/batch-generation"
                className="flex items-center gap-2 p-2.5 rounded-xl border border-border/70 bg-muted/20 hover:border-primary/50 hover:bg-primary/5 transition-all text-xs font-semibold text-foreground"
              >
                <FontAwesomeIcon
                  icon={faBookOpen}
                  className="text-primary text-xs shrink-0"
                />
                <span className="truncate">{t('audio_guide.faq.batch_link')}</span>
              </Link>
              <Link
                to="/guide/audio/cloud-tts-keys"
                className="flex items-center gap-2 p-2.5 rounded-xl border border-border/70 bg-muted/20 hover:border-primary/50 hover:bg-primary/5 transition-all text-xs font-semibold text-foreground"
              >
                <FontAwesomeIcon
                  icon={faSliders}
                  className="text-primary text-xs shrink-0"
                />
                <span className="truncate">{t('audio_guide.faq.cloud_link')}</span>
              </Link>
              <Link
                to="/guide/troubleshooting/flama-audio"
                className="flex items-center gap-2 p-2.5 rounded-xl border border-border/70 bg-muted/20 hover:border-primary/50 hover:bg-primary/5 transition-all text-xs font-semibold text-foreground"
              >
                <FontAwesomeIcon
                  icon={faWrench}
                  className="text-amber-500 text-xs shrink-0"
                />
                <span className="truncate">
                  {t('audio_guide.faq.troubleshoot_link')}
                </span>
              </Link>
            </div>
          </div>
        </CardContent>
      </Card>
    </Page>
  )
}
