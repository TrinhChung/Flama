import { Link } from 'react-router-dom'
import { useTranslation, Trans } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Check, Copy, ExternalLink, KeyRound, ShieldAlert } from 'lucide-react'

interface YomitanCreateTokenCardProps {
  name: string
  setName: (name: string) => void
  expiry: string
  setExpiry: (expiry: string) => void
  isPending: boolean
  onCreate: () => void
  issuedConnectUrl: string | null
  copied: string | null
  onCopy: (label: string, value: string) => void
}

export function YomitanCreateTokenCard({
  name,
  setName,
  expiry,
  setExpiry,
  isPending,
  onCreate,
  issuedConnectUrl,
  copied,
  onCopy,
}: YomitanCreateTokenCardProps) {
  const { t } = useTranslation('settings')

  return (
    <Card className="shadow-2xs">
      <CardHeader className="p-4 sm:p-6">
        <CardTitle className="text-base sm:text-lg font-bold">{t('yomitan.form.title')}</CardTitle>
        <CardDescription className="text-xs sm:text-sm">
          <Trans
            i18nKey="yomitan.form.description"
            t={t}
            components={{
              link: (
                <Link
                  to="/guide/integrations/yomitan"
                  className="text-primary font-medium hover:underline inline-flex items-center gap-0.5"
                >
                  {t('yomitan.form.guide_link_text')}{' '}
                  <ExternalLink className="size-3 inline" />
                </Link>
              ),
            }}
          />
        </CardDescription>
      </CardHeader>
      <CardContent className="p-4 sm:p-6 pt-0 space-y-5 sm:space-y-6">
        <div className="grid gap-4 md:grid-cols-[1fr_240px_auto] md:items-end">
          <div className="space-y-2">
            <Label htmlFor="connect-token-name" className="text-xs font-semibold">
              {t('yomitan.form.name_label')}
            </Label>
            <Input
              id="connect-token-name"
              value={name}
              maxLength={120}
              placeholder={t('yomitan.form.name_placeholder')}
              className="h-10 text-sm"
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="connect-token-expiry" className="text-xs font-semibold">
              {t('yomitan.form.expiry_label')}
            </Label>
            <NativeSelect
              id="connect-token-expiry"
              className="w-full h-10 text-sm"
              value={expiry}
              onChange={(event) => setExpiry(event.target.value)}
            >
              <NativeSelectOption value="30">{t('yomitan.form.expiry_30')}</NativeSelectOption>
              <NativeSelectOption value="90">{t('yomitan.form.expiry_90')}</NativeSelectOption>
              <NativeSelectOption value="180">{t('yomitan.form.expiry_180')}</NativeSelectOption>
              <NativeSelectOption value="365">{t('yomitan.form.expiry_365')}</NativeSelectOption>
              <NativeSelectOption value="none">{t('yomitan.form.expiry_none')}</NativeSelectOption>
            </NativeSelect>
          </div>
          <Button
            size="lg"
            className="w-full md:w-auto h-10 font-semibold shadow-2xs"
            disabled={!name.trim() || isPending}
            onClick={onCreate}
          >
            <KeyRound className="mr-2 size-4" /> {t('yomitan.form.submit_btn')}
          </Button>
        </div>

        <Alert className="border-sky-500/30 bg-sky-50/50 dark:bg-sky-950/20 p-3.5 sm:p-4">
          <ShieldAlert className="size-4 text-sky-600 dark:text-sky-400 shrink-0 mt-0.5" />
          <div>
            <AlertTitle className="text-sky-900 dark:text-sky-200 text-xs sm:text-sm font-semibold">
              {t('yomitan.form.config_alert_title')}
            </AlertTitle>
            <AlertDescription className="mt-1 text-xs text-sky-800 dark:text-sky-300 leading-relaxed space-y-1">
              <p>
                <Trans
                  i18nKey="yomitan.form.config_alert_text"
                  t={t}
                  components={{
                    bold: <strong />,
                  }}
                />
              </p>
              <p className="text-[11px] text-muted-foreground">
                <Trans
                  i18nKey="yomitan.form.config_alert_ref"
                  t={t}
                  components={{
                    link1: (
                      <Link
                        to="/guide/integrations/yomitan"
                        className="text-primary hover:underline font-medium"
                      />
                    ),
                    link2: (
                      <Link
                        to="/guide/integrations/yomitan-markers"
                        className="text-primary hover:underline font-medium"
                      />
                    ),
                  }}
                />
              </p>
            </AlertDescription>
          </div>
        </Alert>

        {issuedConnectUrl ? (
          <Alert className="border-amber-500/50 bg-amber-50 dark:bg-amber-950/30 p-3.5 sm:p-4">
            <ShieldAlert className="size-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div className="space-y-2.5 w-full min-w-0">
              <AlertTitle className="text-amber-900 dark:text-amber-200 font-bold text-xs sm:text-sm">
                {t('yomitan.form.issued_warning_title')}
              </AlertTitle>
              <AlertDescription className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pt-1">
                <code className="min-w-0 flex-1 break-all rounded-lg border bg-background p-3 text-xs font-mono select-all overflow-x-auto max-h-32">
                  {issuedConnectUrl}
                </code>
                <Button
                  variant="default"
                  className="w-full sm:w-auto shrink-0 bg-amber-600 hover:bg-amber-700 text-white h-10 font-semibold"
                  onClick={() => onCopy('connect-url', issuedConnectUrl)}
                >
                  {copied === 'connect-url' ? (
                    <Check className="mr-2 size-4 text-white" />
                  ) : (
                    <Copy className="mr-2 size-4" />
                  )}
                  {copied === 'connect-url' ? t('yomitan.form.copied_btn') : t('yomitan.form.copy_btn')}
                </Button>
              </AlertDescription>
            </div>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  )
}
