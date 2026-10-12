import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowRight, Bot, CheckCircle2, ChevronDown, ChevronUp, Flame, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'

const STORAGE_KEY = 'flama_intro_mcp_collapsed'

export interface McpValueIntroProps {
  onStartSetup?: () => void
  showToggle?: boolean
}

export function McpValueIntro({ onStartSetup, showToggle = true }: McpValueIntroProps) {
  const { t } = useTranslation('mcp')
  const [collapsed, setCollapsed] = useState(() => {
    if (!showToggle) return false
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true'
    } catch {
      return false
    }
  })

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev
      try {
        localStorage.setItem(STORAGE_KEY, String(next))
      } catch {
        // no-op
      }
      return next
    })
  }

  return (
    <section
      aria-label={t('page.value_intro.title')}
      className="rounded-xl border border-border/70 bg-card p-4 sm:p-5 shadow-2xs transition-all"
    >
      {/* Top Banner Bar: Title & Toggle Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pb-1">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="p-2 rounded-lg bg-primary/10 text-primary shrink-0">
            <Bot className="size-4.5 sm:size-5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm sm:text-base font-bold text-foreground tracking-tight">
                {t('page.value_intro.title')}
              </span>
              <span className="px-2 py-0.5 rounded-md text-[10px] sm:text-[11px] font-semibold bg-primary/10 text-primary border border-primary/20 shrink-0">
                {t('page.value_intro.badge')}
              </span>
            </div>
            {!collapsed && (
              <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed line-clamp-2 sm:line-clamp-none">
                {t('page.value_intro.subtitle')}
              </p>
            )}
          </div>
        </div>

        {showToggle && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={toggleCollapsed}
            className="self-start sm:self-center text-xs text-muted-foreground hover:text-foreground shrink-0 h-8 gap-1.5 px-2.5"
          >
            <span>
              {collapsed
                ? t('page.value_intro.toggle_show')
                : t('page.value_intro.toggle_hide')}
            </span>
            {collapsed ? <ChevronDown className="size-3.5" /> : <ChevronUp className="size-3.5" />}
          </Button>
        )}
      </div>

      {/* Expanded Content: Before vs After & 3-Step Flow */}
      {!collapsed && (
        <div className="mt-4 pt-4 border-t border-border/60 space-y-4">
          {/* Comparison Grid: Traditional vs Flama */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
            {/* Column 1: Traditional Isolated AI Chat */}
            <div className="rounded-lg border border-border/50 bg-muted/30 p-3.5 sm:p-4 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-foreground">
                  {t('page.value_intro.before_title')}
                </span>
                <span className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
                  {t('page.value_intro.before_badge')}
                </span>
              </div>
              <ul className="space-y-2 text-xs text-muted-foreground leading-relaxed">
                <li className="flex items-start gap-2">
                  <XCircle className="size-3.5 text-rose-500 shrink-0 mt-0.5" />
                  <span>{t('page.value_intro.before_p1')}</span>
                </li>
                <li className="flex items-start gap-2">
                  <XCircle className="size-3.5 text-rose-500 shrink-0 mt-0.5" />
                  <span>{t('page.value_intro.before_p2')}</span>
                </li>
                <li className="flex items-start gap-2">
                  <XCircle className="size-3.5 text-rose-500 shrink-0 mt-0.5" />
                  <span>{t('page.value_intro.before_p3')}</span>
                </li>
              </ul>
            </div>

            {/* Column 2: With Flama MCP */}
            <div className="rounded-lg border border-primary/25 bg-primary/[0.03] dark:bg-primary/[0.05] p-3.5 sm:p-4 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                  <Flame className="size-3.5 text-primary" />
                  {t('page.value_intro.after_title')}
                </span>
                <span className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  {t('page.value_intro.after_badge')}
                </span>
              </div>
              <ul className="space-y-2 text-xs text-foreground/90 leading-relaxed">
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="size-3.5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                  <span>{t('page.value_intro.after_p1')}</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="size-3.5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                  <span>{t('page.value_intro.after_p2')}</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="size-3.5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                  <span>{t('page.value_intro.after_p3')}</span>
                </li>
              </ul>
            </div>
          </div>

          {/* 3-Step Flow Ribbon */}
          <div className="rounded-lg border border-border/50 bg-card p-3 sm:p-3.5 space-y-2">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block">
              {t('page.value_intro.steps_label')}
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-0.5">
              <div className="flex items-center gap-2 p-2 rounded-md bg-muted/40 border border-border/40 text-xs text-foreground font-medium">
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-[10px] font-bold">1</span>
                <span className="truncate">{t('page.value_intro.step_1')}</span>
              </div>
              <div className="flex items-center gap-2 p-2 rounded-md bg-muted/40 border border-border/40 text-xs text-foreground font-medium">
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-[10px] font-bold">2</span>
                <span className="truncate">{t('page.value_intro.step_2')}</span>
              </div>
              <div className="flex items-center gap-2 p-2 rounded-md bg-muted/40 border border-border/40 text-xs text-foreground font-medium">
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-[10px] font-bold">3</span>
                <span className="truncate">{t('page.value_intro.step_3')}</span>
              </div>
            </div>
          </div>

          {/* CTA transition to Setup/Tokens tab */}
          {onStartSetup && (
            <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-3 bg-primary/[0.04] dark:bg-primary/[0.06] border border-primary/20 rounded-lg p-3 sm:p-3.5">
              <span className="text-xs text-foreground/90 font-medium">
                {t('page.tabs.overview.cta_question')}
              </span>
              <Button
                type="button"
                onClick={onStartSetup}
                className="w-full sm:w-auto h-8 text-xs font-semibold gap-1.5 shrink-0"
              >
                <span>{t('page.tabs.overview.cta_btn')}</span>
                <ArrowRight className="size-3.5" />
              </Button>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
