import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Layers, Plus } from 'lucide-react'
import type { useBrowseState } from '../hooks/useBrowseState'
import { useBrowseEditorResize } from '../hooks/useBrowseEditorResize'
import { BrowseCardCreateForm } from './BrowseCardCreateForm'
import { BrowseCardEditForm } from './BrowseCardEditForm'

interface BrowseCardEditorProps {
  browse: ReturnType<typeof useBrowseState>
}

export function BrowseCardEditor({ browse }: BrowseCardEditorProps) {
  const { t } = useTranslation('browse')
  const {
    activeCardId,
    isCreatingCard,
    cardDetailQuery,
    handleStartCreateCard,
    mobileTab,
  } = browse

  const { editorWidth, isMobile, handleMouseDown } = useBrowseEditorResize()

  if (!activeCardId && !isCreatingCard) {
    return (
      <div
        style={{ width: `${editorWidth}px` }}
        className="hidden lg:flex border-l border-border/60 flex-col items-center justify-center p-8 bg-card shrink-0 text-center relative"
      >
        {/* Resize Handle */}
        <div
          className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-primary/60 hover:w-1.5 transition-all bg-border/20 z-50"
          onMouseDown={handleMouseDown}
        />
        <Layers className="size-10 text-muted-foreground opacity-60 mb-2.5" />
        <h3 className="font-bold text-sm text-foreground">{t('editor.empty_title')}</h3>
        <p className="text-xs text-muted-foreground max-w-48 mt-1 leading-relaxed">
          {t('editor.empty_desc')}
        </p>
        <Button
          size="sm"
          className="mt-4 text-xs font-semibold rounded-lg gap-1.5 bg-primary text-primary-foreground hover:opacity-95 shadow-xs"
          onClick={handleStartCreateCard}
        >
          <Plus className="size-3.5" />
          <span>{t('editor.add_new_card')}</span>
        </Button>
      </div>
    )
  }

  if (isCreatingCard) {
    return (
      <BrowseCardCreateForm
        browse={browse}
        isMobile={isMobile}
        editorWidth={editorWidth}
        onMouseDownResize={handleMouseDown}
      />
    )
  }

  if (cardDetailQuery.isPending) {
    return (
      <div
        style={{ width: isMobile ? '100%' : `${editorWidth}px` }}
        className={`border-l border-border/60 p-4 space-y-4 shrink-0 bg-card relative flex flex-col h-full ${
          mobileTab === 'editor' ? 'flex' : 'hidden lg:flex'
        }`}
      >
        {/* Resize Handle */}
        <div
          className="hidden lg:block absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-primary/60 hover:w-1.5 transition-all bg-border/20 z-50"
          onMouseDown={handleMouseDown}
        />
        <div className="animate-pulse space-y-3">
          <div className="h-6 bg-muted rounded w-2/3" />
          <div className="h-4 bg-muted rounded w-1/3" />
          <div className="space-y-4 pt-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="space-y-1.5">
                <div className="h-3 bg-muted rounded w-1/4" />
                <div className="h-16 bg-muted rounded-xl" />
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <BrowseCardEditForm
      key={activeCardId}
      browse={browse}
      isMobile={isMobile}
      editorWidth={editorWidth}
      onMouseDownResize={handleMouseDown}
    />
  )
}
