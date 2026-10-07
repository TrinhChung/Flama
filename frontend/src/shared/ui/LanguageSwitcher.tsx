import { Languages, Check, ChevronDown } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

export type LanguageSwitcherProps = {
  /**
   * 'dropdown': Standard compact accessible dropdown menu (default)
   * 'toggle': Fast 1-click bilingual switch (instant VI <-> EN toggle)
   * 'icon': Minimalist ghost icon button (ideal for tight corners / mobile)
   * 'pill': Segmented switch mini VI | EN without opening a menu
   */
  variant?: 'dropdown' | 'toggle' | 'icon' | 'pill'
  /** Compact sizing */
  compact?: boolean
  /** Custom CSS classes */
  className?: string
  /** Whether to show a text label next to the language code */
  showLabel?: boolean
  /** Optional chevron down indicator (defaults to false for cleaner corner look) */
  showChevron?: boolean
}

export const LANGUAGES = [
  { code: 'vi', label: 'Tiếng Việt', flag: '🇻🇳', short: 'VI' },
  { code: 'en', label: 'English', flag: '🇬🇧', short: 'EN' },
] as const

export function LanguageSwitcher({
  variant = 'dropdown',
  compact = false,
  className,
  showLabel = false,
  showChevron = false,
}: LanguageSwitcherProps) {
  const { i18n, t } = useTranslation()
  const rawLang = i18n.resolvedLanguage || i18n.language || 'vi'
  const currentLang = rawLang.startsWith('en') ? 'en' : 'vi'
  const currentOption = LANGUAGES.find((l) => l.code === currentLang) || LANGUAGES[0]

  const handleSelectLanguage = (code: 'vi' | 'en') => {
    if (code !== currentLang) {
      void i18n.changeLanguage(code)
    }
  }

  // --- Variant: Pill (Segmented flat micro switch) ---
  if (variant === 'pill') {
    return (
      <div
        role="group"
        aria-label={t('common.language.switch_aria', 'Chuyển đổi ngôn ngữ / Switch language')}
        className={cn(
          'inline-flex items-center rounded-full border border-border/60 bg-muted/40 p-0.5',
          compact ? 'h-7' : 'h-8',
          className,
        )}
      >
        {LANGUAGES.map((item) => {
          const isActive = currentLang === item.code
          return (
            <button
              key={item.code}
              type="button"
              onClick={() => handleSelectLanguage(item.code)}
              className={cn(
                'inline-flex items-center justify-center rounded-full px-2 text-xs font-semibold transition-all duration-200 cursor-pointer',
                compact ? 'h-5.5 px-2 text-[10px]' : 'h-6.5 px-2.5 text-[11px]',
                isActive
                  ? 'bg-background text-foreground font-bold'
                  : 'text-muted-foreground hover:text-foreground',
              )}
              aria-pressed={isActive}
            >
              <span className="font-mono uppercase tracking-wider">{item.short}</span>
            </button>
          )
        })}
      </div>
    )
  }

  // --- Variant: Toggle (1-click fast flat toggle VI <-> EN) ---
  if (variant === 'toggle') {
    const nextLang = currentLang === 'vi' ? 'en' : 'vi'
    const tooltipText =
      currentLang === 'vi'
        ? t('common.language.switch_to_en', 'Chuyển sang English')
        : t('common.language.switch_to_vi', 'Chuyển sang Tiếng Việt')

    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={() => handleSelectLanguage(nextLang)}
            aria-label={tooltipText}
            className={cn(
              'group inline-flex items-center justify-center gap-1.5 rounded-full border border-border/60 bg-muted/40 px-2.5 text-xs font-medium text-muted-foreground transition-all duration-200 hover:bg-muted/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 cursor-pointer select-none active:scale-95',
              compact ? 'h-7 px-2 text-[11px] gap-1' : 'h-8',
              className,
            )}
          >
            <Languages className="size-3.5 shrink-0 text-muted-foreground transition-colors group-hover:text-foreground" />
            <span className="inline-block w-5 text-center font-semibold tracking-wider text-[11px] uppercase text-foreground">
              {currentOption.short}
            </span>
          </button>
        </TooltipTrigger>
        <TooltipContent side="bottom" sideOffset={6}>
          <p>{tooltipText}</p>
        </TooltipContent>
      </Tooltip>
    )
  }

  // --- Variant: Icon (Minimalist flat ghost icon button with dropdown) ---
  if (variant === 'icon') {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={t('common.language.switch_aria', 'Chuyển đổi ngôn ngữ / Switch language')}
            className={cn(
              'group inline-flex items-center justify-center rounded-full border border-border/60 bg-muted/40 text-muted-foreground transition-all duration-200 hover:bg-muted/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 cursor-pointer select-none',
              compact ? 'size-7' : 'size-8',
              className,
            )}
          >
            <Languages className={cn('shrink-0 transition-colors group-hover:text-foreground', compact ? 'size-3.5' : 'size-4')} />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          sideOffset={6}
          className="w-40 rounded-xl border border-border/60 bg-popover/95 p-1 backdrop-blur-md animate-in fade-in-50 zoom-in-95"
        >
          <DropdownMenuLabel className="px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">
            {t('common.language.label', 'Ngôn ngữ')}
          </DropdownMenuLabel>
          <DropdownMenuSeparator className="-mx-1 my-1" />
          {LANGUAGES.map((item) => {
            const isSelected = currentLang === item.code
            return (
              <DropdownMenuItem
                key={item.code}
                onSelect={() => handleSelectLanguage(item.code)}
                className={cn(
                  'flex items-center justify-between rounded-lg px-2.5 py-1.5 text-xs font-medium cursor-pointer transition-colors',
                  isSelected && 'bg-primary/10 text-primary font-semibold',
                )}
              >
                <span className="flex items-center gap-2">
                  <span className="text-base leading-none">{item.flag}</span>
                  <span>{item.label}</span>
                </span>
                {isSelected && <Check className="size-3.5 text-primary shrink-0" />}
              </DropdownMenuItem>
            )
          })}
        </DropdownMenuContent>
      </DropdownMenu>
    )
  }

  // --- Variant: Dropdown (Default - Clean, flat trigger matching navbar tone) ---
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={t('common.language.switch_aria', 'Chuyển đổi ngôn ngữ / Switch language')}
          className={cn(
            'group inline-flex items-center justify-center gap-1.5 rounded-full border border-border/60 bg-muted/40 px-2.5 text-xs font-medium text-muted-foreground transition-all duration-200 hover:bg-muted/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 cursor-pointer select-none',
            compact ? 'h-7 px-2 text-[11px] gap-1' : 'h-8',
            className,
          )}
        >
          <Languages className="size-3.5 shrink-0 text-muted-foreground transition-colors group-hover:text-foreground" />
          <span className="inline-block w-5 text-center font-semibold tracking-wider text-[11px] uppercase text-foreground">
            {currentOption.short}
          </span>
          {showLabel && (
            <span className="hidden sm:inline-block text-xs font-medium text-muted-foreground">
              {currentOption.label}
            </span>
          )}
          {showChevron && (
            <ChevronDown className="size-3 shrink-0 text-muted-foreground/70" />
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        sideOffset={6}
        className="w-40 rounded-xl border border-border/60 bg-popover/95 p-1 backdrop-blur-md animate-in fade-in-50 zoom-in-95"
      >
        <DropdownMenuLabel className="px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">
          {t('common.language.label', 'Ngôn ngữ')}
        </DropdownMenuLabel>
        <DropdownMenuSeparator className="-mx-1 my-1" />
        {LANGUAGES.map((item) => {
          const isSelected = currentLang === item.code
          return (
            <DropdownMenuItem
              key={item.code}
              onSelect={() => handleSelectLanguage(item.code)}
              className={cn(
                'flex items-center justify-between rounded-lg px-2.5 py-1.5 text-xs font-medium cursor-pointer transition-colors',
                isSelected && 'bg-primary/10 text-primary font-semibold',
              )}
            >
              <span className="flex items-center gap-2">
                <span className="text-base leading-none">{item.flag}</span>
                <span>{item.label}</span>
              </span>
              {isSelected && <Check className="size-3.5 text-primary shrink-0" />}
            </DropdownMenuItem>
          )
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
