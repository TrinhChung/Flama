import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Search, Sliders, Trash2, Plus, AlertTriangle } from 'lucide-react'
import type { useBrowseState } from '../hooks/useBrowseState'

export interface BrowseToolbarProps {
  browse: ReturnType<typeof useBrowseState>
}

export function BrowseToolbar({ browse }: BrowseToolbarProps) {
  const { t } = useTranslation('browse')
  const {
    queryText,
    setQueryText,
    statusFilter,
    setStatusFilter,
    selectedCards,
    selectedDeck,
    bulkDeleteMutation,
    handleStartCreateCard,
  } = browse

  return (
    <div className="flex flex-col sm:flex-row gap-2.5 p-3 border-b border-border/60 bg-background shrink-0">
      {/* Search Bar Input */}
      <div className="relative flex-1">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
        <Input
          placeholder={t('toolbar.search_placeholder')}
          value={queryText}
          onChange={(e) => setQueryText(e.target.value)}
          className="pl-9 h-9 rounded-xl text-xs sm:text-sm bg-muted/50"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {/* Add Card Button */}
        <Button
          type="button"
          size="sm"
          onClick={handleStartCreateCard}
          className="h-8 rounded-lg text-xs font-bold gap-1 bg-primary text-primary-foreground hover:opacity-95 shadow-xs shrink-0"
        >
          <Plus className="size-3.5" />
          <span>{t('toolbar.add_card')}</span>
        </Button>

        {/* Status filter dropdown mapping */}
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-semibold">
          <Sliders className="size-3.5 text-muted-foreground" />
          <NativeSelect
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-8 py-0 pl-2 pr-6 text-xs rounded-lg bg-muted/50"
          >
            <option value="all">{t('toolbar.status_filter.all')}</option>
            <option value="new">{t('toolbar.status_filter.new')}</option>
            <option value="learning">{t('toolbar.status_filter.learning')}</option>
            <option value="review">{t('toolbar.status_filter.review')}</option>
          </NativeSelect>
        </div>

        {/* Selected Deck indicator when no individual cards are ticked */}
        {selectedCards.length === 0 && selectedDeck && (
          <div className="flex items-center gap-1.5 animate-in fade-in slide-in-from-right-3">
            <Badge variant="outline" className="text-xs font-semibold px-2.5 py-1 rounded-lg gap-1.5 bg-muted/40 border-border/80 text-foreground">
              <span className="text-muted-foreground font-normal">{t('toolbar.selected_deck')}</span>
              <span className="font-bold text-foreground truncate max-w-36 sm:max-w-60">{selectedDeck.name}</span>
              <span className="text-muted-foreground font-medium">{t('toolbar.cards_count', { count: selectedDeck.counts?.total ?? 0 })}</span>
            </Badge>

            {selectedDeck.has_mixed_note_types ? (
              <Badge
                variant="outline"
                className="text-[11px] font-semibold text-amber-600 dark:text-amber-400 bg-amber-500/10 border-amber-500/30 gap-1 px-2 py-0.5"
                title={t('toolbar.mixed_note_types_tooltip', { types: selectedDeck.note_type_names?.join(', ') || '' })}
              >
                <AlertTriangle className="size-3 shrink-0" />
                <span>{t('toolbar.mixed_note_types', { count: selectedDeck.note_type_names?.length || selectedDeck.note_type_ids?.length || 2 })}</span>
              </Badge>
            ) : selectedDeck.note_type_name ? (
              <Badge
                variant="outline"
                className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/30 px-2 py-0.5"
              >
                <span>{t('toolbar.template_badge', { name: selectedDeck.note_type_name })}</span>
              </Badge>
            ) : null}
          </div>
        )}

        {/* Selected cards Bulk actions */}
        {selectedCards.length > 0 && (
          <div className="flex items-center gap-1.5 animate-in fade-in slide-in-from-right-3">
            <Badge variant="secondary" className="text-xs font-semibold px-2 py-0.5 rounded-md">
              {t('toolbar.selected_cards_count', { count: selectedCards.length })}
            </Badge>

            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                if (window.confirm(t('toolbar.confirm_bulk_delete', { count: selectedCards.length }))) {
                  bulkDeleteMutation.mutate(selectedCards)
                }
              }}
              disabled={bulkDeleteMutation.isPending}
              className="h-8 rounded-lg text-xs gap-1.5 text-destructive hover:bg-destructive/10 hover:text-destructive border-destructive/30 bg-background"
            >
              <Trash2 className="size-3.5 shrink-0" />
              <span>{t('toolbar.delete_selected', { count: selectedCards.length })}</span>
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
