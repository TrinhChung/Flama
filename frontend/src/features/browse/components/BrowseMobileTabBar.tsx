import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { Layers } from 'lucide-react'

export interface BrowseMobileTabBarProps {
  mobileTab: 'decks' | 'cards' | 'editor'
  setMobileTab: (tab: 'decks' | 'cards' | 'editor') => void
  activeCardId: string | null
}

export function BrowseMobileTabBar({
  mobileTab,
  setMobileTab,
  activeCardId,
}: BrowseMobileTabBarProps) {
  const { t } = useTranslation('browse')

  return (
    <div className="lg:hidden shrink-0 h-12 border-t border-border/60 bg-background/95 flex items-center justify-around z-20 sticky bottom-0">
      <button
        type="button"
        onClick={() => setMobileTab('decks')}
        className={`flex flex-col items-center justify-center flex-1 h-full text-[10px] font-bold gap-1 ${
          mobileTab === 'decks' ? 'text-primary' : 'text-muted-foreground'
        }`}
      >
        <Layers className="size-4" />
        <span>{t('mobile_tabs.decks')}</span>
      </button>

      <button
        type="button"
        onClick={() => setMobileTab('cards')}
        className={`flex flex-col items-center justify-center flex-1 h-full text-[10px] font-bold gap-1 ${
          mobileTab === 'cards' ? 'text-primary' : 'text-muted-foreground'
        }`}
      >
        <svg
          className="size-4"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <rect width="18" height="18" x="3" y="3" rx="2" />
          <path d="M3 9h18" />
          <path d="M9 21V9" />
        </svg>
        <span>{t('mobile_tabs.cards')}</span>
      </button>

      <button
        type="button"
        onClick={() => {
          if (activeCardId) {
            setMobileTab('editor')
          } else {
            toast.info(t('mobile_tabs.select_card_first'))
          }
        }}
        className={`flex flex-col items-center justify-center flex-1 h-full text-[10px] font-bold gap-1 ${
          mobileTab === 'editor' ? 'text-primary' : 'text-muted-foreground'
        } ${!activeCardId ? 'opacity-40' : ''}`}
      >
        <svg
          className="size-4"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12 20h9" />
          <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
        </svg>
        <span>{t('mobile_tabs.editor')}</span>
      </button>
    </div>
  )
}
