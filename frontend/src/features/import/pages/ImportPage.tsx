import { useState, useEffect, useCallback, useRef } from 'react'
import { HelpCircle, Layers, NotebookTabs } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { appApi } from '@/app/api'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import type { AnkiConnectStatus } from '@/lib/ankiConnectClient'
import { ankiConnectClient } from '@/lib/ankiConnectClient'
import { AnkiConnectionBar } from '../components/AnkiConnectionBar'
import { AnkiSyncTab } from '../components/AnkiSyncTab'
import { AnkiNoteTypeSyncTab } from '../components/AnkiNoteTypeSyncTab'
import { AnkiCorsGuideTab } from '../components/AnkiCorsGuideTab'

type NoteField = {
  id: string
  name: string
  field_type: string
}

type NoteTypeOption = {
  id: string
  name: string
  fields: NoteField[]
}

type ImportOptionsResponse = {
  deck_options?: any[]
  decks?: any[]
  note_type_options?: NoteTypeOption[]
  note_types?: NoteTypeOption[]
}

export function ImportPage() {
  const [activeTab, setActiveTab] = useState<'decks' | 'note_types' | 'guide'>('decks')

  // Shared Anki Connection State
  const [endpoint, setEndpoint] = useState('http://127.0.0.1:8765')
  const [connectionStatus, setConnectionStatus] = useState<AnkiConnectStatus>('Anki is not running')
  const [ankiVersion, setAnkiVersion] = useState<number | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [isCheckingConn, setIsCheckingConn] = useState(false)
  const connectionRequestId = useRef(0)

  const checkAnkiConnection = useCallback(async () => {
    const requestId = ++connectionRequestId.current
    setIsCheckingConn(true)
    setConnectionError(null)
    const result = await ankiConnectClient.checkConnection(endpoint)
    if (requestId !== connectionRequestId.current) return
    setConnectionStatus(result.status)
    setAnkiVersion(result.version || null)
    setConnectionError(result.error || null)
    setIsCheckingConn(false)
  }, [endpoint])

  const handleEndpointChange = (nextEndpoint: string) => {
    connectionRequestId.current++
    setEndpoint(nextEndpoint)
    setConnectionStatus('Anki is not running')
    setAnkiVersion(null)
    setConnectionError(null)
    setIsCheckingConn(false)
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void checkAnkiConnection()
    }, 400)
    return () => window.clearTimeout(timer)
  }, [checkAnkiConnection])

  const bootstrapQuery = useQuery({
    queryKey: ['bootstrap'],
    queryFn: () => appApi.getBootstrap(),
  })
  const isAdmin = Boolean(bootstrapQuery.data?.user?.is_admin)

  const optionsQuery = useQuery<ImportOptionsResponse>({
    queryKey: ['import-options'],
    queryFn: () => appApi.get<ImportOptionsResponse>('/flashcards/import/options'),
    enabled: isAdmin,
  })

  const noteTypeOptions: NoteTypeOption[] =
    optionsQuery.data?.note_type_options ||
    optionsQuery.data?.note_types || [
      {
        id: 'default-vocab',
        name: 'Vocabulary Flashcard',
        fields: [
          { id: '1', name: 'Word', field_type: 'text' },
          { id: '2', name: 'Meaning', field_type: 'text' },
          { id: '3', name: 'Reading', field_type: 'text' },
          { id: '4', name: 'Example', field_type: 'text' },
          { id: '5', name: 'Audio', field_type: 'audio' },
          { id: '6', name: 'Image', field_type: 'image' },
        ],
      },
    ]

  if (bootstrapQuery.data && !isAdmin) {
    return (
      <Page>
        <PageError error={new Error('Chỉ quản trị viên (Admin) mới có quyền truy cập chức năng đồng bộ Anki.')} />
      </Page>
    )
  }

  if (optionsQuery.isPending || bootstrapQuery.isPending) return <PageLoading label="Đang tải cấu hình đồng bộ..." />
  if (optionsQuery.error) return <Page><PageError error={optionsQuery.error} /></Page>

  return (
    <Page className="w-full max-w-6xl px-3 sm:px-6 lg:px-8 py-3 space-y-4 sm:space-y-6">
      <PageHeader
        title="Đồng bộ Anki Desktop (AnkiConnect)"
        description="Nhập và đồng bộ bộ thẻ (Deck), loại thẻ (NoteType), nội dung HTML, hình ảnh và âm thanh trực tiếp từ Anki Desktop lên Flama."
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
          className={`pb-2.5 text-xs sm:text-sm font-bold border-b-2 transition-all flex items-center gap-2 shrink-0 ${
            activeTab === 'decks'
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Layers className="size-4" /> 1. Bộ Thẻ &amp; Thẻ
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('note_types')}
          className={`pb-2.5 text-xs sm:text-sm font-bold border-b-2 transition-all flex items-center gap-2 shrink-0 ${
            activeTab === 'note_types'
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <NotebookTabs className="size-4" /> 2. Loại Thẻ (NoteTypes)
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('guide')}
          className={`pb-2.5 text-xs sm:text-sm font-bold border-b-2 transition-all flex items-center gap-2 shrink-0 ${
            activeTab === 'guide'
              ? 'border-amber-500 text-amber-600 dark:text-amber-400'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <HelpCircle className="size-4 text-amber-500" /> 3. Hướng dẫn CORS
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
