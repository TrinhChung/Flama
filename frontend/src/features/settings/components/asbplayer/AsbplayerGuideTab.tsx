import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import {
  ArrowRight,
  BookOpen,
  Check,
  Copy,
  Download,
  ExternalLink,
  Globe,
  HelpCircle,
  Keyboard,
  Layers,
  Zap,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface CanonicalFieldMapping {
  asbField: string
  flamaField: string
  dataType: string
  role: string
  description: string
  isPrimary?: boolean
}

export function AsbplayerGuideTab() {
  const { t } = useTranslation('settings')
  const [copiedScheme, setCopiedScheme] = useState(false)

  const canonicalFieldMappings: CanonicalFieldMapping[] = useMemo(
    () => [
      {
        asbField: 'Sentence',
        flamaField: 'Sentence',
        dataType: 'Text',
        role: t('asbplayer.guide_tab.role_primary'),
        description: t('asbplayer.guide_tab.field_sentence_desc'),
        isPrimary: true,
      },
      {
        asbField: 'Word',
        flamaField: 'Word',
        dataType: 'Text',
        role: t('asbplayer.guide_tab.role_word'),
        description: t('asbplayer.guide_tab.field_word_desc'),
      },
      {
        asbField: 'Definition',
        flamaField: 'Definition',
        dataType: 'Text',
        role: t('asbplayer.guide_tab.role_definition'),
        description: t('asbplayer.guide_tab.field_definition_desc'),
      },
      {
        asbField: 'Image',
        flamaField: 'Image',
        dataType: 'Image (PNG/WebP)',
        role: t('asbplayer.guide_tab.role_image'),
        description: t('asbplayer.guide_tab.field_image_desc'),
      },
      {
        asbField: 'Audio',
        flamaField: 'Audio',
        dataType: 'Audio (MP3)',
        role: t('asbplayer.guide_tab.role_audio'),
        description: t('asbplayer.guide_tab.field_audio_desc'),
      },
      {
        asbField: 'Source',
        flamaField: 'Source',
        dataType: 'Text',
        role: t('asbplayer.guide_tab.role_source'),
        description: t('asbplayer.guide_tab.field_source_desc'),
      },
      {
        asbField: 'URL',
        flamaField: 'URL',
        dataType: 'Text',
        role: t('asbplayer.guide_tab.role_url'),
        description: t('asbplayer.guide_tab.field_url_desc'),
      },
    ],
    [t]
  )

  const copyMappingScheme = async () => {
    const scheme = {
      deck: 'Sentences',
      model: 'Sentence Card',
      fields: {
        Sentence: 'sentence',
        Word: 'word',
        Definition: 'definition',
        Image: 'image',
        Audio: 'audio',
        Source: 'source',
        URL: 'url',
      },
    }
    try {
      await navigator.clipboard.writeText(JSON.stringify(scheme, null, 2))
      setCopiedScheme(true)
      toast.success(t('asbplayer.guide_tab.copy_scheme_success'))
      setTimeout(() => setCopiedScheme(false), 2000)
    } catch {
      toast.error(t('asbplayer.guide_tab.copy_scheme_error'))
    }
  }

  return (
    <div className="space-y-8">
      {/* 1. Official Extension & App Download Links */}
      <Card className="border-border/60 shadow-2xs">
        <CardHeader className="p-4 sm:p-5 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-primary/10 text-primary shrink-0">
              <Download className="size-4 sm:size-4.5" />
            </div>
            <div>
              <CardTitle className="text-base sm:text-lg font-bold">
                {t('asbplayer.guide_tab.download_title')}
              </CardTitle>
              <CardDescription className="text-xs sm:text-sm">
                {t('asbplayer.guide_tab.download_desc')}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-0">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <a
              href="https://chromewebstore.google.com/detail/asbplayer/hkdedakdpjbknhbfgahflcaakhbedhdf"
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-start gap-3 p-3.5 rounded-xl border border-border/60 bg-muted/20 hover:bg-muted/50 hover:border-primary/40 transition-all shadow-2xs"
            >
              <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0 group-hover:scale-105 transition-transform">
                <ChromeIcon className="size-4.5" />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                    Chrome Web Store
                  </span>
                  <ExternalLink className="size-3 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
                  {t('asbplayer.guide_tab.chrome_desc')}
                </p>
              </div>
            </a>

            <a
              href="https://addons.mozilla.org/en-US/firefox/addon/asbplayer/"
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-start gap-3 p-3.5 rounded-xl border border-border/60 bg-muted/20 hover:bg-muted/50 hover:border-primary/40 transition-all shadow-2xs"
            >
              <div className="p-2 rounded-lg bg-orange-500/10 text-orange-600 dark:text-orange-400 shrink-0 group-hover:scale-105 transition-transform">
                <Flame className="size-4.5" />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                    Firefox Add-ons
                  </span>
                  <ExternalLink className="size-3 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
                  {t('asbplayer.guide_tab.firefox_desc')}
                </p>
              </div>
            </a>

            <a
              href="https://asbplayer.dev"
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-start gap-3 p-3.5 rounded-xl border border-border/60 bg-muted/20 hover:bg-muted/50 hover:border-primary/40 transition-all shadow-2xs"
            >
              <div className="p-2 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400 shrink-0 group-hover:scale-105 transition-transform">
                <Globe className="size-4.5" />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                    asbplayer.dev
                  </span>
                  <ExternalLink className="size-3 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
                  {t('asbplayer.guide_tab.web_player_desc')}
                </p>
              </div>
            </a>

            <a
              href="https://github.com/killergerbah/asbplayer"
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-start gap-3 p-3.5 rounded-xl border border-border/60 bg-muted/20 hover:bg-muted/50 hover:border-primary/40 transition-all shadow-2xs"
            >
              <div className="p-2 rounded-lg bg-muted text-foreground shrink-0 group-hover:scale-105 transition-transform">
                <GithubIcon className="size-4.5" />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                    {t('asbplayer.guide_tab.github_title')}
                  </span>
                  <ExternalLink className="size-3 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
                  {t('asbplayer.guide_tab.github_desc')}
                </p>
              </div>
            </a>
          </div>
        </CardContent>
      </Card>

      {/* 2. Canonical 7-Field Mapping Standard Table */}
      <Card className="border-border/60 shadow-2xs">
        <CardHeader className="p-4 sm:p-5 pb-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0">
                <Layers className="size-4 sm:size-4.5" />
              </div>
              <div>
                <CardTitle className="text-base sm:text-lg font-bold">
                  {t('asbplayer.guide_tab.mapping_title')}
                </CardTitle>
                <CardDescription className="text-xs sm:text-sm">
                  {t('asbplayer.guide_tab.mapping_desc')}
                </CardDescription>
              </div>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={copyMappingScheme}
              className="h-8 text-xs gap-1.5 shrink-0 self-start sm:self-center"
            >
              {copiedScheme ? <Check className="size-3.5 text-emerald-500" /> : <Copy className="size-3.5" />}
              <span>{copiedScheme ? t('asbplayer.guide_tab.btn_copied') : t('asbplayer.guide_tab.btn_copy_scheme')}</span>
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-0">
          <div className="overflow-x-auto rounded-xl border border-border/60 bg-card">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-border/60 bg-muted/40 text-muted-foreground font-semibold">
                  <th className="py-2.5 px-3.5 whitespace-nowrap">{t('asbplayer.guide_tab.th_asb_field')}</th>
                  <th className="py-2.5 px-3.5 whitespace-nowrap">{t('asbplayer.guide_tab.th_flama_field')}</th>
                  <th className="py-2.5 px-3.5 whitespace-nowrap">{t('asbplayer.guide_tab.th_data_type')}</th>
                  <th className="py-2.5 px-3.5 whitespace-nowrap">{t('asbplayer.guide_tab.th_role')}</th>
                  <th className="py-2.5 px-3.5">{t('asbplayer.guide_tab.th_desc')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {canonicalFieldMappings.map((field) => (
                  <tr key={field.asbField} className="hover:bg-muted/30 transition-colors">
                    <td className="py-2.5 px-3.5 font-mono font-semibold text-foreground whitespace-nowrap">
                      {field.asbField}
                    </td>
                    <td className="py-2.5 px-3.5 font-mono text-primary font-semibold whitespace-nowrap">
                      {field.flamaField}
                    </td>
                    <td className="py-2.5 px-3.5 text-muted-foreground whitespace-nowrap">
                      <span className="px-2 py-0.5 rounded-md text-[10px] bg-muted border font-medium">
                        {field.dataType}
                      </span>
                    </td>
                    <td className="py-2.5 px-3.5 whitespace-nowrap">
                      <Badge
                        variant={field.isPrimary ? 'default' : 'outline'}
                        className={`text-[10px] ${
                          field.isPrimary ? 'bg-primary text-primary-foreground font-bold' : 'text-muted-foreground'
                        }`}
                      >
                        {field.role}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-3.5 text-muted-foreground leading-relaxed">
                      {field.description}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-3 flex items-start gap-2 p-3 rounded-lg bg-primary/[0.04] border border-primary/20 text-xs text-muted-foreground">
            <Zap className="size-4 text-primary shrink-0 mt-0.5" />
            <p className="leading-relaxed">
              {t('asbplayer.guide_tab.quick_tip')}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* 3. Mining Shortcuts Guide */}
      <Card className="border-border/60 shadow-2xs">
        <CardHeader className="p-4 sm:p-5 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0">
              <Keyboard className="size-4 sm:size-4.5" />
            </div>
            <div>
              <CardTitle className="text-base sm:text-lg font-bold">
                {t('asbplayer.guide_tab.shortcuts_title')}
              </CardTitle>
              <CardDescription className="text-xs sm:text-sm">
                {t('asbplayer.guide_tab.shortcuts_desc')}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-0">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="p-3.5 rounded-xl border border-border/60 bg-muted/20 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-foreground">{t('asbplayer.guide_tab.shortcut_mine_title')}</span>
                <span className="px-2 py-0.5 rounded-md font-mono text-[11px] font-bold bg-primary/10 text-primary border border-primary/20">
                  Ctrl + Shift + X
                </span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {t('asbplayer.guide_tab.shortcut_mine_desc')}
              </p>
            </div>

            <div className="p-3.5 rounded-xl border border-border/60 bg-muted/20 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-foreground">{t('asbplayer.guide_tab.shortcut_nav_title')}</span>
                <span className="px-2 py-0.5 rounded-md font-mono text-[11px] font-bold bg-muted text-foreground border">
                  A / S / D
                </span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {t('asbplayer.guide_tab.shortcut_nav_desc')}
              </p>
            </div>

            <div className="p-3.5 rounded-xl border border-border/60 bg-muted/20 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-foreground">{t('asbplayer.guide_tab.shortcut_yomitan_title')}</span>
                <span className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  {t('asbplayer.guide_tab.shortcut_yomitan_badge')}
                </span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {t('asbplayer.guide_tab.shortcut_yomitan_desc')}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 4. Troubleshooting & Deep Documentation Links */}
      <Card className="border-border/60 shadow-2xs">
        <CardHeader className="p-4 sm:p-5 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-primary/10 text-primary shrink-0">
              <HelpCircle className="size-4 sm:size-4.5" />
            </div>
            <div>
              <CardTitle className="text-base sm:text-lg font-bold">
                {t('asbplayer.guide_tab.docs_title')}
              </CardTitle>
              <CardDescription className="text-xs sm:text-sm">
                {t('asbplayer.guide_tab.docs_desc')}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-0">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <Link
              to="/guide/integrations/asbplayer"
              className="group flex items-start gap-3 p-3.5 rounded-xl border border-border/60 bg-muted/20 hover:bg-muted/50 hover:border-primary/40 transition-all shadow-2xs"
            >
              <div className="p-2 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400 shrink-0 group-hover:scale-105 transition-transform">
                <BookOpen className="size-4" />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                    {t('asbplayer.quick_links.install', 'Cài đặt & Tải tiện ích')}
                  </span>
                  <ArrowRight className="size-3 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  {t('asbplayer.guide_tab.doc_install_desc')}
                </p>
              </div>
            </Link>

            <Link
              to="/guide/integrations/asbplayer#mapping"
              className="group flex items-start gap-3 p-3.5 rounded-xl border border-border/60 bg-muted/20 hover:bg-muted/50 hover:border-primary/40 transition-all shadow-2xs"
            >
              <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0 group-hover:scale-105 transition-transform">
                <Layers className="size-4" />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                    {t('asbplayer.quick_links.mapping', 'Cấu hình 7 trường dữ liệu')}
                  </span>
                  <ArrowRight className="size-3 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  {t('asbplayer.guide_tab.doc_mapping_desc')}
                </p>
              </div>
            </Link>

            <Link
              to="/guide/integrations/asbplayer#shortcuts"
              className="group flex items-start gap-3 p-3.5 rounded-xl border border-border/60 bg-muted/20 hover:bg-muted/50 hover:border-primary/40 transition-all shadow-2xs"
            >
              <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0 group-hover:scale-105 transition-transform">
                <Zap className="size-4" />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                    {t('asbplayer.quick_links.shortcuts', 'Phím tắt khai thác')}
                  </span>
                  <ArrowRight className="size-3 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  {t('asbplayer.guide_tab.doc_shortcuts_desc')}
                </p>
              </div>
            </Link>

            <Link
              to="/guide/troubleshooting/asbplayer"
              className="group flex items-start gap-3 p-3.5 rounded-xl border border-border/60 bg-muted/20 hover:bg-muted/50 hover:border-primary/40 transition-all shadow-2xs"
            >
              <div className="p-2 rounded-lg bg-rose-500/10 text-rose-600 dark:text-rose-400 shrink-0 group-hover:scale-105 transition-transform">
                <HelpCircle className="size-4" />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                    {t('asbplayer.guide_tab.doc_troubleshoot_title')}
                  </span>
                  <ArrowRight className="size-3 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  {t('asbplayer.guide_tab.doc_troubleshoot_desc')}
                </p>
              </div>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function Flame({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z" />
    </svg>
  )
}

function ChromeIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="4" />
      <line x1="21.17" x2="12" y1="8" />
      <line x1="3.95" x2="8.54" y1="6.06" y2="14" />
      <line x1="10.88" x2="15.46" y1="21.94" y2="14" />
    </svg>
  )
}

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
      <path d="M9 18c-4.51 2-5-2-7-2" />
    </svg>
  )
}
