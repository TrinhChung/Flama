import { Layers, Search } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { AnkiDeckTreeView } from '../AnkiDeckTreeView'

interface AnkiDeckSelectCardProps {
  decks: string[]
  deckSearch: string
  setDeckSearch: (val: string) => void
  selectedDecks: string[]
  setSelectedDecks: React.Dispatch<React.SetStateAction<string[]>>
  deckNoteCounts: Record<string, number>
}

export function AnkiDeckSelectCard({
  decks,
  deckSearch,
  setDeckSearch,
  selectedDecks,
  setSelectedDecks,
  deckNoteCounts,
}: AnkiDeckSelectCardProps) {
  const { t } = useTranslation('import')

  return (
    <Card className="border-border/80 shadow-xs rounded-2xl overflow-hidden">
      <CardHeader className="p-4 sm:p-5 pb-3 border-b bg-card/40">
        <CardTitle className="text-sm font-semibold flex items-center justify-between flex-wrap gap-2">
          <span className="flex items-center gap-2">
            <Layers className="size-4 text-primary shrink-0" />{' '}
            {t('anki_sync.decks_tab.select_title', { defaultValue: '1. Chọn Deck Anki đồng bộ' })}
          </span>
          <span className="text-xs text-muted-foreground font-normal">
            {t('anki_sync.decks_tab.selected_count', {
              count: selectedDecks.length,
              defaultValue: `Đã chọn ${selectedDecks.length} deck`,
            })}
          </span>
        </CardTitle>
        <CardDescription className="text-xs">
          Chọn danh mục bộ thẻ Anki bạn muốn nhập hoặc đồng bộ lên Flama.
        </CardDescription>
      </CardHeader>
      <CardContent className="p-4 sm:p-5 pt-4 space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <Input
            value={deckSearch}
            onChange={(e) => setDeckSearch(e.target.value)}
            placeholder={t('anki_sync.decks_tab.search_placeholder', { defaultValue: 'Tìm kiếm bộ thẻ Anki...' })}
            className="pl-9 text-xs h-9"
          />
        </div>

        <AnkiDeckTreeView
          decks={decks}
          searchQuery={deckSearch}
          selectedDecks={selectedDecks}
          deckNoteCounts={deckNoteCounts}
          onSelectDeck={(deckName) => {
            if (selectedDecks.includes(deckName)) {
              setSelectedDecks(selectedDecks.filter((item) => item !== deckName))
            } else {
              setSelectedDecks([deckName])
            }
          }}
        />
      </CardContent>
    </Card>
  )
}
