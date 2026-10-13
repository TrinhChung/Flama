import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  ArrowRight,
  BookOpen,
  Download,
  ExternalLink,
  HelpCircle,
  Smartphone,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { YomitanMarkersExplorer } from '@/features/guide/components/YomitanMarkersExplorer'

export function YomitanGuideTab() {
  const { t } = useTranslation('settings')

  return (
    <div className="space-y-8">
      {/* 1. Official Extension Download Links */}
      <Card className="border-border/60 shadow-2xs">
        <CardHeader className="p-4 sm:p-5 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-primary/10 text-primary shrink-0">
              <Download className="size-4 sm:size-4.5" />
            </div>
            <div>
              <CardTitle className="text-base sm:text-lg font-bold">
                {t('yomitan.guide_tab.download_title')}
              </CardTitle>
              <CardDescription className="text-xs sm:text-sm">
                {t('yomitan.guide_tab.download_desc')}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-0">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <a
              href="https://chromewebstore.google.com/detail/yomitan/likgccmbimfdjeeajfakonmlclifcnik"
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
                    Chrome / Edge / Brave
                  </span>
                  <ExternalLink className="size-3 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
                  {t('yomitan.guide_tab.chrome_desc')}
                </p>
              </div>
            </a>

            <a
              href="https://addons.mozilla.org/en-US/firefox/addon/yomitan/"
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-start gap-3 p-3.5 rounded-xl border border-border/60 bg-muted/20 hover:bg-muted/50 hover:border-primary/40 transition-all shadow-2xs"
            >
              <div className="p-2 rounded-lg bg-orange-500/10 text-orange-600 dark:text-orange-400 shrink-0 group-hover:scale-105 transition-transform">
                <GlobeIcon className="size-4.5" />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                    Mozilla Firefox
                  </span>
                  <ExternalLink className="size-3 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
                  {t('yomitan.guide_tab.firefox_desc')}
                </p>
              </div>
            </a>

            <a
              href="https://github.com/themoeway/yomitan"
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
                    {t('yomitan.guide_tab.github_title')}
                  </span>
                  <ExternalLink className="size-3 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
                  {t('yomitan.guide_tab.github_desc')}
                </p>
              </div>
            </a>
          </div>
        </CardContent>
      </Card>

      {/* 2. Embedded 55 Field Markers Explorer */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <h3 className="text-base sm:text-lg font-bold text-foreground">
              {t('yomitan.guide_tab.markers_title')}
            </h3>
            <p className="text-xs sm:text-sm text-muted-foreground">
              {t('yomitan.guide_tab.markers_desc')}
            </p>
          </div>
          <Link
            to="/guide/integrations/yomitan-markers"
            className="text-xs text-primary hover:underline font-medium inline-flex items-center gap-1 shrink-0"
          >
            <span>{t('yomitan.guide_tab.markers_link')}</span>
            <ArrowRight className="size-3" />
          </Link>
        </div>

        {/* Embedded YomitanMarkersExplorer */}
        <YomitanMarkersExplorer />
      </div>

      {/* 3. Mobile Guide: Kiwi Browser & Firefox Android */}
      <Card className="border-border/60 shadow-2xs">
        <CardHeader className="p-4 sm:p-5 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400 shrink-0">
              <Smartphone className="size-4 sm:size-4.5" />
            </div>
            <div>
              <CardTitle className="text-base sm:text-lg font-bold">
                {t('yomitan.guide_tab.mobile_title')}
              </CardTitle>
              <CardDescription className="text-xs sm:text-sm">
                {t('yomitan.guide_tab.mobile_desc')}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-0">
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 pt-1">
            <div className="p-3.5 rounded-xl border border-border/50 bg-muted/20 space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-[10px] font-bold">
                  1
                </span>
                <span className="text-xs font-semibold text-foreground">{t('yomitan.guide_tab.step1_title')}</span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {t('yomitan.guide_tab.step1_desc')}
              </p>
            </div>

            <div className="p-3.5 rounded-xl border border-border/50 bg-muted/20 space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-[10px] font-bold">
                  2
                </span>
                <span className="text-xs font-semibold text-foreground">{t('yomitan.guide_tab.step2_title')}</span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {t('yomitan.guide_tab.step2_desc')}
              </p>
            </div>

            <div className="p-3.5 rounded-xl border border-border/50 bg-muted/20 space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-[10px] font-bold">
                  3
                </span>
                <span className="text-xs font-semibold text-foreground">{t('yomitan.guide_tab.step3_title')}</span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {t('yomitan.guide_tab.step3_desc')}
              </p>
            </div>

            <div className="p-3.5 rounded-xl border border-border/50 bg-muted/20 space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-[10px] font-bold">
                  4
                </span>
                <span className="text-xs font-semibold text-foreground">{t('yomitan.guide_tab.step4_title')}</span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {t('yomitan.guide_tab.step4_desc')}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 4. Troubleshooting & In-depth Documentation Links */}
      <Card className="border-border/60 shadow-2xs">
        <CardHeader className="p-4 sm:p-5 pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0">
                <HelpCircle className="size-4 sm:size-4.5" />
              </div>
              <div>
                <CardTitle className="text-base sm:text-lg font-bold">
                  {t('yomitan.guide_tab.troubleshoot_title')}
                </CardTitle>
                <CardDescription className="text-xs sm:text-sm">
                  {t('yomitan.guide_tab.troubleshoot_desc')}
                </CardDescription>
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-0">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Link
              to="/guide/integrations/yomitan"
              className="group flex items-start gap-3 p-3.5 rounded-xl border border-border/60 bg-muted/20 hover:bg-muted/50 hover:border-primary/40 transition-all shadow-2xs"
            >
              <div className="p-2 rounded-lg bg-primary/10 text-primary shrink-0 group-hover:scale-105 transition-transform">
                <BookOpen className="size-4" />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                    {t('yomitan.docs.card1_title', 'Cài đặt & Tải Yomitan')}
                  </span>
                  <ArrowRight className="size-3 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  {t('yomitan.docs.card1_desc', 'Từng bước cài đặt extension trên Chrome/Firefox và cấu hình Server URL.')}
                </p>
              </div>
            </Link>

            <Link
              to="/guide/troubleshooting/yomitan"
              className="group flex items-start gap-3 p-3.5 rounded-xl border border-border/60 bg-muted/20 hover:bg-muted/50 hover:border-primary/40 transition-all shadow-2xs"
            >
              <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0 group-hover:scale-105 transition-transform">
                <HelpCircle className="size-4" />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                    {t('yomitan.docs.card3_title', 'Di động & Xử lý sự cố')}
                  </span>
                  <ArrowRight className="size-3 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  {t('yomitan.docs.card3_desc', 'Hướng dẫn dùng trên Kiwi Browser, Firefox Android và sửa lỗi kết nối.')}
                </p>
              </div>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function GlobeIcon({ className }: { className?: string }) {
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
      <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
      <path d="M2 12h20" />
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
