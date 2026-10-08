import { HelpCircle, Layers, NotebookTabs } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { ContextHelpButton } from '@/features/guide'
import { AnkiConnectionBar } from '../components/AnkiConnectionBar'
import { AnkiSyncTab } from '../components/AnkiSyncTab'
import { AnkiNoteTypeSyncTab } from '../components/AnkiNoteTypeSyncTab'
import { AnkiCorsGuideTab } from '../components/AnkiCorsGuideTab'
import { useAnkiSyncPage } from '../hooks/useAnkiSyncPage'

export function AnkiSyncPage() {
  const { t } = useTranslation('import')
  const {
    activeTab,
    setActiveTab,
    endpoint,
    connectionStatus,
    ankiVersion,
    connectionError,
    isCheckingConn,
    checkAnkiConnection,
    handleEndpointChange,
    bootstrapQuery,
    optionsQuery,
    noteTypeOptions,
  } = useAnkiSyncPage()

  if (optionsQuery.isPending || bootstrapQuery.isPending) {
    return <PageLoading label={t('anki_sync.loading_config')} />
  }
  if (optionsQuery.error) {
    return <Page><PageError error={optionsQuery.error} /></Page>
  }

  return (
    <Page className="w-full max-w-6xl px-3 sm:px-6 lg:px-8 py-3 space-y-4 sm:space-y-6">
      <PageHeader
        title={t('anki_sync.page_title', { defaultValue: 'Đồng bộ Anki Desktop (AnkiConnect)' })}
        description={t('anki_sync.page_desc', { defaultValue: 'Nhập và đồng bộ bộ thẻ (Deck), loại thẻ (NoteType), nội dung HTML, hình ảnh và âm thanh trực tiếp từ Anki Desktop lên Flama.' })}
        actions={
          <ContextHelpButton
            guidePath="/guide/import-sync/anki-connect-sync"
            guideTitle="Hướng dẫn đồng bộ AnkiConnect"
            troubleshootPath="/guide/troubleshooting/anki-sync"
            troubleshootTitle="Khắc phục lỗi kết nối Anki"
            label={t('anki_sync.help_btn', { defaultValue: 'Hướng dẫn kết nối' })}
          />
        }
      />

      {/* Shared Connection Status Header Bar */}
      <AnkiConnectionBar
        endpoint={endpoint}
        onEndpointChange={handleEndpointChange}
        connectionStatus={connectionStatus}
        ankiVersion={ankiVersion}
        connectionError={connectionError}
        isCheckingConn={isCheckingConn}
        onCheckConnection={checkAnkiConnection}
        onOpenGuide={() => setActiveTab('guide')}
      />

      {/* Sub-tab navigation bar with horizontal scrolling for mobile */}
      <div className="flex items-center border-b border-border/80 gap-2 sm:gap-6 overflow-x-auto whitespace-nowrap scrollbar-none pb-0.5">
        <button
          type="button"
          onClick={() => setActiveTab('decks')}
          className={`pb-2.5 text-xs sm:text-sm font-bold border-b-2 transition-all flex items-center gap-2 shrink-0 cursor-pointer ${
            activeTab === 'decks'
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Layers className="size-4" /> {t('anki_sync.tabs.decks', { defaultValue: '1. Bộ Thẻ & Thẻ' })}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('note_types')}
          className={`pb-2.5 text-xs sm:text-sm font-bold border-b-2 transition-all flex items-center gap-2 shrink-0 cursor-pointer ${
            activeTab === 'note_types'
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <NotebookTabs className="size-4" /> {t('anki_sync.tabs.notetypes', { defaultValue: '2. Loại Thẻ (NoteTypes)' })}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('guide')}
          className={`pb-2.5 text-xs sm:text-sm font-bold border-b-2 transition-all flex items-center gap-2 shrink-0 cursor-pointer ${
            activeTab === 'guide'
              ? 'border-amber-500 text-amber-600 dark:text-amber-400'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <HelpCircle className="size-4 text-amber-500" /> {t('anki_sync.tabs.guide', { defaultValue: '3. Hướng dẫn CORS' })}
        </button>
      </div>

      {activeTab === 'decks' ? (
        <AnkiSyncTab
          noteTypeOptions={noteTypeOptions}
          flamaUserId={Number(bootstrapQuery.data?.user?.id || 0)}
          endpoint={endpoint}
          connectionStatus={connectionStatus}
          ankiVersion={ankiVersion}
        />
      ) : activeTab === 'note_types' ? (
        <AnkiNoteTypeSyncTab
          noteTypeOptions={noteTypeOptions}
          endpoint={endpoint}
          connectionStatus={connectionStatus}
          ankiVersion={ankiVersion}
        />
      ) : (
        <AnkiCorsGuideTab />
      )}
    </Page>
  )
}

