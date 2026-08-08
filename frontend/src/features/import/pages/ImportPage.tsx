import { useState } from 'react'
import { Layers, NotebookTabs } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { appApi } from '@/app/api'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { AnkiSyncTab } from '../components/AnkiSyncTab'
import { AnkiNoteTypeSyncTab } from '../components/AnkiNoteTypeSyncTab'

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
  decks: any[]
  note_types: NoteTypeOption[]
}

export function ImportPage() {
  const [activeTab, setActiveTab] = useState<'decks' | 'note_types'>('decks')

  const optionsQuery = useQuery<ImportOptionsResponse>({
    queryKey: ['import-options'],
    queryFn: () => appApi.get<ImportOptionsResponse>('/flashcards/import/options'),
  })

  const noteTypeOptions: NoteTypeOption[] = optionsQuery.data?.note_types || [
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

  if (optionsQuery.isPending) return <PageLoading label="Đang tải cấu hình đồng bộ..." />
  if (optionsQuery.error) return <Page><PageError error={optionsQuery.error} /></Page>

  return (
    <Page className="w-full max-w-6xl px-4 lg:px-8 py-3 space-y-6">
      <PageHeader
        title="Đồng bộ Anki Desktop (AnkiConnect)"
        description="Nhập và đồng bộ bộ thẻ (Deck), loại thẻ (NoteType), nội dung HTML, hình ảnh và âm thanh trực tiếp từ Anki Desktop lên Flama."
      />

      {/* Sub-tab navigation */}
      <div className="flex border-b border-border/80 gap-6">
        <button
          type="button"
          onClick={() => setActiveTab('decks')}
          className={`pb-3 text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${
            activeTab === 'decks'
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Layers className="size-4" /> 1. Đồng bộ Bộ Thẻ &amp; Thẻ (Anki Decks)
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('note_types')}
          className={`pb-3 text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${
            activeTab === 'note_types'
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <NotebookTabs className="size-4" /> 2. Đồng bộ Loại Thẻ (Anki NoteTypes)
        </button>
      </div>

      {activeTab === 'decks' ? (
        <AnkiSyncTab noteTypeOptions={noteTypeOptions} />
      ) : (
        <AnkiNoteTypeSyncTab noteTypeOptions={noteTypeOptions} />
      )}
    </Page>
  )
}

