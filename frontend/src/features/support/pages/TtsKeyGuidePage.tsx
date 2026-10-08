import { useState } from 'react'
import {
  AudioLines,
  Check,
  Copy,
  ExternalLink,
  HelpCircle,
  ShieldCheck,
  Zap,
} from 'lucide-react'
import { useTranslation, Trans } from 'react-i18next'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Page, PageHeader } from '@/shared/components/Page'

export function TtsKeyGuidePage() {
  const { t } = useTranslation('support')
  const [copiedKeyUrl, setCopiedKeyUrl] = useState(false)

  const voicevoxApiUrl = 'https://su-shiki.com/api/'

  const handleCopyUrl = (url: string) => {
    void navigator.clipboard.writeText(url)
    setCopiedKeyUrl(true)
    toast.success(t('toast.copied', { name: 'URL' }))
    setTimeout(() => setCopiedKeyUrl(false), 2000)
  }

  return (
    <Page className="max-w-5xl space-y-8">
      <PageHeader
        title={t('tts_guide.title')}
        description={t('tts_guide.description')}
        actions={
          <Button asChild variant="outline" className="gap-2">
            <Link to="/browse">
              <AudioLines className="size-4 text-primary" />
              <span>{t('tts_guide.to_browse')}</span>
            </Link>
          </Button>
        }
      />

      {/* Overview Alert */}
      <Alert className="border-border/80 bg-muted/30">
        <AudioLines className="size-5 text-foreground/80" />
        <AlertTitle className="text-base font-bold text-foreground">
          {t('tts_guide.alert_title')}
        </AlertTitle>
        <AlertDescription className="mt-1 text-xs text-muted-foreground leading-relaxed">
          {t('tts_guide.alert_desc')}
        </AlertDescription>
      </Alert>

      {/* Main Guide Step: VoiceVox (Default & Primary) */}
      <Card className="border-2 border-primary/30 shadow-md">
        <CardHeader className="bg-gradient-to-r from-primary/10 via-amber-500/10 to-transparent pb-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground font-black text-lg shadow-sm">
                1
              </div>
              <div>
                <CardTitle className="text-xl font-bold flex items-center gap-2">
                  <span>VoiceVox (TTS Quest API)</span>
                  <Badge variant="default" className="bg-primary text-primary-foreground text-[10px]">
                    {t('tts_guide.voicevox.badge')}
                  </Badge>
                </CardTitle>
                <CardDescription className="text-xs">
                  {t('tts_guide.voicevox.desc')}
                </CardDescription>
              </div>
            </div>
            <a
              href={voicevoxApiUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-xs font-semibold text-primary-foreground shadow-xs transition hover:opacity-90"
            >
              <span>{t('tts_guide.voicevox.open_page')}</span>
              <ExternalLink className="size-3.5" />
            </a>
          </div>
        </CardHeader>
        <CardContent className="space-y-6 pt-6">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-xl border bg-card p-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center rounded-md bg-primary/10 px-2.5 py-1 text-xs font-bold text-primary shrink-0">
                  {t('tts_guide.step_badge', { step: 1, defaultValue: 'Bước 1' })}
                </span>
                <h4 className="font-semibold text-sm">
                  {t('tts_guide.voicevox.step1_title')}
                </h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {t('tts_guide.voicevox.step1_desc')}
              </p>
              <div className="flex items-center gap-1.5 pt-1">
                <code className="rounded bg-muted px-2 py-1 text-[11px] font-mono text-foreground truncate max-w-[200px]">
                  {voicevoxApiUrl}
                </code>
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7 shrink-0"
                  onClick={() => handleCopyUrl(voicevoxApiUrl)}
                  title={t('feedback.copy_code_tooltip')}
                >
                  {copiedKeyUrl ? (
                    <Check className="size-3.5 text-emerald-500" />
                  ) : (
                    <Copy className="size-3.5" />
                  )}
                </Button>
              </div>
            </div>

            <div className="rounded-xl border bg-card p-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center rounded-md bg-primary/10 px-2.5 py-1 text-xs font-bold text-primary shrink-0">
                  {t('tts_guide.step_badge', { step: 2, defaultValue: 'Bước 2' })}
                </span>
                <h4 className="font-semibold text-sm">
                  {t('tts_guide.voicevox.step2_title')}
                </h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {t('tts_guide.voicevox.step2_desc')}
              </p>
            </div>

            <div className="rounded-xl border bg-card p-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center rounded-md bg-primary/10 px-2.5 py-1 text-xs font-bold text-primary shrink-0">
                  {t('tts_guide.step_badge', { step: 3, defaultValue: 'Bước 3' })}
                </span>
                <h4 className="font-semibold text-sm">
                  {t('tts_guide.voicevox.step3_title')}
                </h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {t('tts_guide.voicevox.step3_desc')}
              </p>
            </div>
          </div>

          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-900 dark:text-amber-200 space-y-1">
            <div className="font-bold flex items-center gap-1.5">
              <Zap className="size-4 text-amber-600 dark:text-amber-400 shrink-0" />
              <span>{t('tts_guide.voicevox.points_alert_title')}</span>
            </div>
            <p className="leading-relaxed">
              {t('tts_guide.voicevox.points_alert_desc')}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Additional Providers Grid */}
      <div className="space-y-4">
        <h3 className="text-lg font-bold tracking-tight text-foreground flex items-center gap-2">
          <AudioLines className="size-5 text-primary" />
          <span>{t('tts_guide.other_services')}</span>
        </h3>

        <div className="grid gap-6 md:grid-cols-3">
          {/* OpenAI TTS */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <Badge variant="outline" className="text-[10px]">
                  {t('tts_guide.openai.badge')}
                </Badge>
                <a
                  href="https://platform.openai.com/api-keys"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-primary hover:underline flex items-center gap-1 font-semibold"
                >
                  <span>{t('tts_guide.openai.link')}</span>
                  <ExternalLink className="size-3" />
                </a>
              </div>
              <CardTitle className="text-base font-bold mt-2">
                {t('tts_guide.openai.title')}
              </CardTitle>
              <CardDescription className="text-xs">
                {t('tts_guide.openai.desc')}
              </CardDescription>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground space-y-2 pt-0">
              <ol className="list-decimal pl-4 space-y-1.5">
                <li>
                  <Trans
                    i18nKey="tts_guide.openai.step1"
                    ns="support"
                    components={{ strong: <strong /> }}
                    defaults="Đăng nhập tài khoản tại <strong>platform.openai.com</strong>."
                  />
                </li>
                <li>
                  <Trans
                    i18nKey="tts_guide.openai.step2"
                    ns="support"
                    components={{ strong: <strong /> }}
                    defaults="Vào mục <strong>API Keys</strong> &gt; Chọn <strong>Create new secret key</strong>."
                  />
                </li>
                <li>
                  <Trans
                    i18nKey="tts_guide.openai.step3"
                    ns="support"
                    components={{ code: <code /> }}
                    defaults="Sao chép chuỗi Key bắt đầu bằng <code>sk-...</code> và lưu an toàn."
                  />
                </li>
              </ol>
            </CardContent>
          </Card>

          {/* ElevenLabs */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <Badge variant="outline" className="text-[10px]">
                  {t('tts_guide.elevenlabs.badge')}
                </Badge>
                <a
                  href="https://elevenlabs.io"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-primary hover:underline flex items-center gap-1 font-semibold"
                >
                  <span>{t('tts_guide.elevenlabs.link')}</span>
                  <ExternalLink className="size-3" />
                </a>
              </div>
              <CardTitle className="text-base font-bold mt-2">
                {t('tts_guide.elevenlabs.title')}
              </CardTitle>
              <CardDescription className="text-xs">
                {t('tts_guide.elevenlabs.desc')}
              </CardDescription>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground space-y-2 pt-0">
              <ol className="list-decimal pl-4 space-y-1.5">
                <li>
                  <Trans
                    i18nKey="tts_guide.elevenlabs.step1"
                    ns="support"
                    components={{ strong: <strong /> }}
                    defaults="Truy cập và đăng nhập vào <strong>elevenlabs.io</strong>."
                  />
                </li>
                <li>
                  <Trans
                    i18nKey="tts_guide.elevenlabs.step2"
                    ns="support"
                    components={{ strong: <strong /> }}
                    defaults="Nhấn vào ảnh hồ sơ của bạn ở góc dưới bên trái &gt; <strong>Profile + API Key</strong>."
                  />
                </li>
                <li>
                  <Trans
                    i18nKey="tts_guide.elevenlabs.step3"
                    ns="support"
                    defaults="Nhấn biểu tượng mắt để xem và sao chép API Key cá nhân."
                  />
                </li>
              </ol>
            </CardContent>
          </Card>

          {/* Google Cloud / Gemini */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <Badge variant="outline" className="text-[10px]">
                  {t('tts_guide.google.badge')}
                </Badge>
                <a
                  href="https://aistudio.google.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-primary hover:underline flex items-center gap-1 font-semibold"
                >
                  <span>{t('tts_guide.google.link')}</span>
                  <ExternalLink className="size-3" />
                </a>
              </div>
              <CardTitle className="text-base font-bold mt-2">
                {t('tts_guide.google.title')}
              </CardTitle>
              <CardDescription className="text-xs">
                {t('tts_guide.google.desc')}
              </CardDescription>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground space-y-2 pt-0">
              <ol className="list-decimal pl-4 space-y-1.5">
                <li>
                  <Trans
                    i18nKey="tts_guide.google.step1"
                    ns="support"
                    components={{ strong: <strong /> }}
                    defaults="Truy cập <strong>aistudio.google.com</strong> hoặc Google Cloud Console."
                  />
                </li>
                <li>
                  <Trans
                    i18nKey="tts_guide.google.step2"
                    ns="support"
                    components={{ strong: <strong /> }}
                    defaults="Nhấn <strong>Get API key</strong> &gt; Chọn <strong>Create API key</strong>."
                  />
                </li>
                <li>
                  <Trans
                    i18nKey="tts_guide.google.step3"
                    ns="support"
                    defaults="Sao chép mã Key và lưu lại để sử dụng."
                  />
                </li>
              </ol>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Security & FAQ Section */}
      <Card className="bg-muted/30">
        <CardHeader>
          <CardTitle className="text-base font-bold flex items-center gap-2">
            <ShieldCheck className="size-5 text-emerald-500" />
            <span>{t('tts_guide.faq.title')}</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-xs text-muted-foreground leading-relaxed">
          <div className="space-y-1">
            <h5 className="font-semibold text-foreground text-sm flex items-center gap-1.5">
              <HelpCircle className="size-4 text-primary shrink-0" />
              <span>{t('tts_guide.faq.q1')}</span>
            </h5>
            <p className="pl-5">{t('tts_guide.faq.a1')}</p>
          </div>

          <div className="space-y-1">
            <h5 className="font-semibold text-foreground text-sm flex items-center gap-1.5">
              <HelpCircle className="size-4 text-primary shrink-0" />
              <span>{t('tts_guide.faq.q2')}</span>
            </h5>
            <p className="pl-5">{t('tts_guide.faq.a2')}</p>
          </div>
        </CardContent>
      </Card>
    </Page>
  )
}
