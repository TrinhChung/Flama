import { useState, useEffect, useCallback, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { appApi } from '@/app/api'
import { useBootstrap } from '@/shared/api/bootstrap'
import type { AnkiConnectStatus } from '../lib/ankiConnectClient'
import { ankiConnectClient } from '../lib/ankiConnectClient'

export type NoteField = {
  id: string
  name: string
  field_type: string
}

export type NoteTypeOption = {
  id: string
  name: string
  fields: NoteField[]
}

export type ImportOptionsResponse = {
  deck_options?: any[]
  decks?: any[]
  note_type_options?: NoteTypeOption[]
  note_types?: NoteTypeOption[]
}

export function useAnkiSyncPage() {
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

  const bootstrapQuery = useBootstrap()

  const optionsQuery = useQuery<ImportOptionsResponse>({
    queryKey: ['import-options'],
    queryFn: () => appApi.get<ImportOptionsResponse>('/flashcards/import/options'),
    enabled: Boolean(bootstrapQuery.data),
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

  return {
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
  }
}
