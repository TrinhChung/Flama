import { Link } from 'react-router-dom'
import { useTranslation, Trans } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Check, Copy, ExternalLink, KeyRound, Layers, ShieldAlert } from 'lucide-react'
import type { AsbplayerTokenPreset } from '../../hooks/useAsbplayerTokenCRUD'

interface AsbplayerCreateTokenCardProps {
  name: string
  setName: (name: string) => void
  expiry: string
  setExpiry: (expiry: string) => void
  preset: AsbplayerTokenPreset
  setPreset: (preset: AsbplayerTokenPreset) => void
  isPending: boolean
  onCreate: () => void
  issuedConnectUrl: string | null
  issuedMiningKey: string | null
  onSetupMining: () => void
  isPreparingMining: boolean
  copied: string | null
  onCopy: (label: string, value: string) => void
}

export function AsbplayerCreateTokenCard({
  name,
  setName,
  expiry,
  setExpiry,
  preset,
  setPreset,
  isPending,
  onCreate,
  issuedConnectUrl,
  issuedMiningKey,
  onSetupMining,
  isPreparingMining,
  copied,
  onCopy,
}: AsbplayerCreateTokenCardProps) {
  const { t } = useTranslation('settings')

  return (
    <Card className="shadow-2xs">
      <CardHeader className="p-4 sm:p-6">
        <CardTitle className="text-base sm:text-lg font-bold">{t('asbplayer.form.title')}</CardTitle>
        <CardDescription className="text-xs sm:text-sm">
          <Trans
            i18nKey="asbplayer.form.description"
            t={t}
            components={{
              link: (
                <Link
                  to="/guide/integrations/asbplayer"
                  className="text-primary font-medium hover:underline inline-flex items-center gap-0.5"
                >
                  {t('asbplayer.form.guide_link_text')}{' '}
                  <ExternalLink className="size-3 inline" />
                </Link>
              ),
            }}
          />
        </CardDescription>
      </CardHeader>
      <CardContent className="p-4 sm:p-6 pt-0 space-y-5 sm:space-y-6">
        {/* Preset Selector */}
        <div className="space-y-2">
          <Label htmlFor="asbplayer-token-preset" className="text-xs font-semibold">
            {t('asbplayer.form.preset_label')}
          </Label>
          <NativeSelect
            id="asbplayer-token-preset"
            className="w-full h-10 text-sm"
            value={preset}
            onChange={(event) => setPreset(event.target.value as AsbplayerTokenPreset)}
          >
            <NativeSelectOption value="mining-text">
              {t('asbplayer.form.preset_text')}
            </NativeSelectOption>
            <NativeSelectOption value="mining-media">
              {t('asbplayer.form.preset_media')}
            </NativeSelectOption>
          </NativeSelect>
        </div>

        {/* Action Box: Chuẩn bị deck và model */}
        <Alert className="border-sky-500/30 bg-sky-50/50 dark:bg-sky-950/20 p-3.5 sm:p-4">
          <Layers className="size-4 text-sky-600 dark:text-sky-400 shrink-0 mt-0.5" />
          <div className="w-full min-w-0 space-y-1.5">
            <AlertTitle className="text-sky-900 dark:text-sky-200 text-xs sm:text-sm font-semibold">
              {t('asbplayer.form.setup_title')}
            </AlertTitle>
            <AlertDescription className="text-xs text-sky-800 dark:text-sky-300 leading-relaxed space-y-2">
              <p>{t('asbplayer.form.setup_desc')}</p>
              <div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={isPreparingMining}
                  onClick={onSetupMining}
                  className="h-8 text-xs font-medium border-sky-300 dark:border-sky-800 hover:bg-sky-100 dark:hover:bg-sky-900/40"
                >
                  <Layers className="mr-1.5 size-3.5" />
                  {isPreparingMining
                    ? t('asbplayer.form.setup_loading')
                    : t('asbplayer.form.setup_btn')}
                </Button>
              </div>
            </AlertDescription>
          </div>
        </Alert>

        {/* Token Name & Expiry Input Row */}
        <div className="grid gap-4 md:grid-cols-[1fr_240px_auto] md:items-end">
          <div className="space-y-2">
            <Label htmlFor="asbplayer-token-name" className="text-xs font-semibold">
              {t('asbplayer.form.name_label')}
            </Label>
            <Input
              id="asbplayer-token-name"
              value={name}
              maxLength={120}
              placeholder={t('asbplayer.form.name_placeholder')}
              className="h-10 text-sm"
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="asbplayer-token-expiry" className="text-xs font-semibold">
              {t('asbplayer.form.expiry_label')}
            </Label>
            <NativeSelect
              id="asbplayer-token-expiry"
              className="w-full h-10 text-sm"
              value={expiry}
              onChange={(event) => setExpiry(event.target.value)}
            >
              <NativeSelectOption value="30">{t('asbplayer.form.expiry_30')}</NativeSelectOption>
              <NativeSelectOption value="90">{t('asbplayer.form.expiry_90')}</NativeSelectOption>
              <NativeSelectOption value="180">{t('asbplayer.form.expiry_180')}</NativeSelectOption>
              <NativeSelectOption value="365">{t('asbplayer.form.expiry_365')}</NativeSelectOption>
              <NativeSelectOption value="none">{t('asbplayer.form.expiry_none')}</NativeSelectOption>
            </NativeSelect>
          </div>
          <Button
            size="lg"
            className="w-full md:w-auto h-10 font-semibold shadow-2xs"
            disabled={!name.trim() || isPending}
            onClick={onCreate}
          >
            <KeyRound className="mr-2 size-4" /> {t('asbplayer.form.submit_btn')}
          </Button>
        </div>

        {/* Issued Success Alert */}
        {issuedConnectUrl ? (
          <Alert className="border-amber-500/50 bg-amber-50 dark:bg-amber-950/30 p-3.5 sm:p-4">
            <ShieldAlert className="size-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div className="space-y-3 w-full min-w-0">
              <AlertTitle className="text-amber-900 dark:text-amber-200 font-bold text-xs sm:text-sm">
                {t('asbplayer.form.issued_warning')}
              </AlertTitle>

              {/* Endpoint URL */}
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-amber-900 dark:text-amber-300">
                  {t('asbplayer.form.url_label')}
                </p>
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                  <code className="min-w-0 flex-1 break-all rounded-lg border bg-background p-3 text-xs font-mono select-all overflow-x-auto max-h-32">
                    {issuedConnectUrl}
                  </code>
                  <Button
                    variant="default"
                    className="w-full sm:w-auto shrink-0 bg-amber-600 hover:bg-amber-700 text-white h-10 font-semibold"
                    onClick={() => onCopy('anki-connect-url', issuedConnectUrl)}
                  >
                    {copied === 'anki-connect-url' ? (
                      <Check className="mr-2 size-4 text-white" />
                    ) : (
                      <Copy className="mr-2 size-4" />
                    )}
                    {copied === 'anki-connect-url'
                      ? t('asbplayer.form.copied_url_btn')
                      : t('asbplayer.form.copy_url_btn')}
                  </Button>
                </div>
              </div>

              {/* API Key */}
              {issuedMiningKey ? (
                <div className="space-y-1.5 pt-1 border-t border-amber-200 dark:border-amber-900/60">
                  <p className="text-xs font-medium text-amber-900 dark:text-amber-300">
                    {t('asbplayer.form.key_label')}
                  </p>
                  <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                    <code className="min-w-0 flex-1 break-all rounded-lg border bg-background p-3 text-xs font-mono select-all overflow-x-auto max-h-32">
                      {issuedMiningKey}
                    </code>
                    <Button
                      variant="outline"
                      className="w-full sm:w-auto shrink-0 h-10 font-semibold border-amber-300 dark:border-amber-800"
                      onClick={() => onCopy('mining-key', issuedMiningKey)}
                    >
                      {copied === 'mining-key' ? (
                        <Check className="mr-2 size-4 text-primary" />
                      ) : (
                        <Copy className="mr-2 size-4" />
                      )}
                      {copied === 'mining-key'
                        ? t('asbplayer.form.copied_key_btn')
                        : t('asbplayer.form.copy_key_btn')}
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  )
}
