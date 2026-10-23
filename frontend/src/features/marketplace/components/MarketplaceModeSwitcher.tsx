import { BookOpen, Layers, Palette } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'

export type MarketplaceMode = 'decks' | 'note-types' | 'templates'

const MODES = [
  { mode: 'decks', to: '/marketplace/decks', icon: BookOpen, labelKey: 'header.tab_decks', fallback: 'Bộ Thẻ' },
  { mode: 'note-types', to: '/marketplace/note-types', icon: Layers, labelKey: 'header.tab_notetypes', fallback: 'Cấu trúc thẻ' },
  { mode: 'templates', to: '/marketplace/templates', icon: Palette, labelKey: 'header.tab_templates', fallback: 'Giao diện thẻ' },
] as const

export function MarketplaceModeSwitcher({ mode }: { mode: MarketplaceMode }) {
  const { t } = useTranslation('marketplace')
  return (
    <div data-tour="market-mode-switcher" className="inline-flex rounded-xl border border-border/80 bg-muted/40 p-0.5 sm:p-1 shadow-2xs shrink-0">
      {MODES.map(({ mode: value, to, icon: Icon, labelKey, fallback }) => (
        <Button
          key={value}
          variant={mode === value ? 'default' : 'ghost'}
          size="sm"
          asChild
          className="h-7 sm:h-8 px-2.5 sm:px-3 text-xs font-semibold rounded-lg transition-all"
        >
          <Link to={to}>
            <Icon className="mr-1 sm:mr-1.5 size-3.5 shrink-0" />
            {t(labelKey, { defaultValue: fallback })}
          </Link>
        </Button>
      ))}
    </div>
  )
}
