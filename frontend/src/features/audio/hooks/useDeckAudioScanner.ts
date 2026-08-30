import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiRequest } from '@/shared/api/client'
import { scanDeckAudio } from '../services/audioScanService'
import { cleanTextForTts } from '../services/ttsTextNormalizer'
import {
  loadStoredDeckAudioStudioSettings,
  saveStoredDeckAudioStudioSettings,
  type DeckAudioStudioSettings,
} from '../services/deckAudioSettingsStorage'
import type {
  AudioDeckJob,
  AudioJobItem,
  AudioRuleConfig,
  DeckScanResponse,
  FieldMapping,
} from '../types'

import type { DeckOption } from '@/features/import/components/DeckSelectionTreeView'

export type SimpleDeck = {
  id: number
  name: string
  parent_id?: number | null
  path?: string
  counts?: { total?: number; new?: number; learn?: number; due?: number }
}

function generateId(): string {
  return `${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

export function useDeckAudioScanner(initialDeckId?: number | null) {
  const initialStudioSettings = loadStoredDeckAudioStudioSettings()
  const [selectedDeckId, setSelectedDeckId] = useState<number | null>(initialDeckId || null)
  const [isScanning, setIsScanning] = useState(false)
  const [scanData, setScanData] = useState<DeckScanResponse | null>(null)
  const [generationMode, setGenerationModeState] = useState<'missing_and_broken' | 'all'>(
    initialStudioSettings.generationMode,
  )

  const setGenerationMode = (mode: 'missing_and_broken' | 'all') => {
    setGenerationModeState(mode)
    saveStoredDeckAudioStudioSettings({ generationMode: mode })
  }

  const [rules, setRules] = useState<AudioRuleConfig[]>([])

  // 1. Fetch accessible deck list
  const decksQuery = useQuery({
    queryKey: ['browse-decks-tree'],
    queryFn: async () => {
      const res = await apiRequest<{ decks: SimpleDeck[] }>('/api/browse/decks')
      return res.decks || []
    },
  })

  const decks = useMemo(() => decksQuery.data || [], [decksQuery.data])

  const deckOptions: DeckOption[] = useMemo(() => {
    const rawDecks = decksQuery.data || []
    const deckMap = new Map<number, SimpleDeck>()
    rawDecks.forEach((d) => deckMap.set(d.id, d))

    const buildPath = (deck: SimpleDeck): string => {
      const parts = [deck.name]
      let cur = deck
      const seen = new Set<number>()
      while (cur.parent_id != null && deckMap.has(cur.parent_id) && !seen.has(cur.parent_id)) {
        seen.add(cur.parent_id)
        cur = deckMap.get(cur.parent_id)!
        parts.unshift(cur.name)
      }
      return parts.join('::')
    }

    return rawDecks.map((d) => ({
      id: d.id,
      name: d.name,
      path: d.path || buildPath(d),
      parent_id: d.parent_id,
      notes_count: d.counts?.total ?? d.counts?.due ?? 0,
    }))
  }, [decksQuery.data])

  // 2. Perform Deck Scan
  const handleScanDeck = useCallback(async (deckId: number) => {
    setIsScanning(true)
    try {
      const data = await scanDeckAudio(deckId)
      setScanData(data)

      // Initialize rules from auto-detected mappings
      const availableFields: string[] = []
      for (const nt of data.note_types || []) {
        for (const f of nt.fields || []) {
          if (f.name && !availableFields.includes(f.name)) {
            availableFields.push(f.name)
          }
        }
      }
      for (const n of data.notes || []) {
        for (const k of Object.keys(n.field_values || {})) {
          if (k && !availableFields.includes(k)) {
            availableFields.push(k)
          }
        }
      }
      for (const k of (data as any).available_fields || []) {
        if (k && !availableFields.includes(k)) {
          availableFields.push(k)
        }
      }

      const storedSettings = loadStoredDeckAudioStudioSettings()
      const effectiveVoiceId =
        storedSettings.defaultEngineId === 'kokoro'
          ? storedSettings.defaultVoiceIdKokoro
          : storedSettings.defaultVoiceIdVoicevox

      if (data.auto_mappings && data.auto_mappings.length > 0) {
        const mappings: FieldMapping[] = data.auto_mappings.map((m) => ({
          id: generateId(),
          sourceField: m.source_field,
          destinationField: m.destination_field,
        }))

        const defaultRule: AudioRuleConfig = {
          id: generateId(),
          name: 'Cấu hình âm thanh 1',
          engineId: storedSettings.defaultEngineId,
          voiceId: effectiveVoiceId,
          speed: storedSettings.speed,
          pitch: storedSettings.pitch,
          intonation: storedSettings.intonation,
          volume: storedSettings.volume,
          mappings,
        }
        setRules([defaultRule])
      } else {
        // Fallback default mapping
        const sourceField = availableFields.find((f) => ['Reading', 'Word', 'Front', 'Expression', 'Vocabulary', 'Kanji'].includes(f)) || availableFields[0] || 'Word'
        const destField = availableFields.find((f) => f.toLowerCase().includes('audio') || f.toLowerCase().includes('sound')) || availableFields[availableFields.length - 1] || 'Audio'

        const defaultRule: AudioRuleConfig = {
          id: generateId(),
          name: 'Cấu hình âm thanh 1',
          engineId: storedSettings.defaultEngineId,
          voiceId: effectiveVoiceId,
          speed: storedSettings.speed,
          pitch: storedSettings.pitch,
          intonation: storedSettings.intonation,
          volume: storedSettings.volume,
          mappings: [
            {
              id: generateId(),
              sourceField,
              destinationField: destField,
            },
          ],
        }
        setRules([defaultRule])
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Không thể quét dữ liệu Deck.')
      setScanData(null)
      setRules([])
    } finally {
      setIsScanning(false)
    }
  }, [])

  // Auto trigger scan when deck changes
  useEffect(() => {
    if (selectedDeckId) {
      handleScanDeck(selectedDeckId)
    } else {
      setScanData(null)
      setRules([])
    }
  }, [selectedDeckId, handleScanDeck])

  // Extract all unique field names in current scan
  const availableFieldNames = useMemo(() => {
    if (!scanData) return []
    const names = new Set<string>()
    for (const nt of scanData.note_types || []) {
      for (const f of nt.fields || []) {
        if (f.name) names.add(f.name)
      }
    }
    for (const n of scanData.notes || []) {
      for (const k of Object.keys(n.field_values || {})) {
        if (k) names.add(k)
      }
    }
    for (const k of (scanData as any).available_fields || []) {
      if (k) names.add(k)
    }
    return Array.from(names)
  }, [scanData])

  // Rule management helpers
  const handleAddRule = () => {
    const defaultSource = availableFieldNames.find((f) => ['Reading', 'Word', 'Front', 'Expression'].includes(f)) || availableFieldNames[0] || 'Word'
    const defaultDest = availableFieldNames.find((f) => f.toLowerCase().includes('audio') || f.toLowerCase().includes('sound')) || 'Audio'

    const storedSettings = loadStoredDeckAudioStudioSettings()
    const effectiveVoiceId =
      storedSettings.defaultEngineId === 'kokoro'
        ? storedSettings.defaultVoiceIdKokoro
        : storedSettings.defaultVoiceIdVoicevox

    const newRule: AudioRuleConfig = {
      id: generateId(),
      name: `Cấu hình âm thanh ${rules.length + 1}`,
      engineId: storedSettings.defaultEngineId,
      voiceId: effectiveVoiceId,
      speed: storedSettings.speed,
      pitch: storedSettings.pitch,
      intonation: storedSettings.intonation,
      volume: storedSettings.volume,
      mappings: [
        {
          id: generateId(),
          sourceField: defaultSource,
          destinationField: defaultDest,
        },
      ],
    }
    setRules((prev) => [...prev, newRule])
    toast.success(`Đã thêm ${newRule.name}`)
  }

  const handleRemoveRule = (ruleId: string) => {
    if (rules.length <= 1) {
      toast.warning('Phải giữ lại ít nhất 1 cấu hình âm thanh.')
      return
    }
    setRules((prev) => prev.filter((r) => r.id !== ruleId))
  }

  const handleUpdateRule = (ruleId: string, updater: Partial<AudioRuleConfig>) => {
    setRules((prev) =>
      prev.map((r) => (r.id === ruleId ? { ...r, ...updater } : r)),
    )

    // Persist preferences for future rules & scans
    const preferencesToSave: Partial<DeckAudioStudioSettings> = {}
    if (updater.engineId) {
      preferencesToSave.defaultEngineId = updater.engineId
    }
    if (updater.voiceId) {
      const activeEngine = updater.engineId || rules.find((r) => r.id === ruleId)?.engineId || 'voicevox'
      if (activeEngine === 'kokoro') {
        preferencesToSave.defaultVoiceIdKokoro = updater.voiceId
      } else {
        preferencesToSave.defaultVoiceIdVoicevox = updater.voiceId
      }
    }
    if (typeof updater.volume === 'number') preferencesToSave.volume = updater.volume
    if (typeof updater.pitch === 'number') preferencesToSave.pitch = updater.pitch
    if (typeof updater.speed === 'number') preferencesToSave.speed = updater.speed
    if (typeof updater.intonation === 'number') preferencesToSave.intonation = updater.intonation

    if (Object.keys(preferencesToSave).length > 0) {
      saveStoredDeckAudioStudioSettings(preferencesToSave)
    }
  }

  const handleAddFieldMapping = (ruleId: string) => {
    const defaultSource = availableFieldNames[0] || 'Word'
    const defaultDest = availableFieldNames.find((f) => f.toLowerCase().includes('audio')) || availableFieldNames[availableFieldNames.length - 1] || 'Audio'

    const newMapping: FieldMapping = {
      id: generateId(),
      sourceField: defaultSource,
      destinationField: defaultDest,
    }

    setRules((prev) =>
      prev.map((r) =>
        r.id === ruleId
          ? { ...r, mappings: [...r.mappings, newMapping] }
          : r,
      ),
    )
  }

  const handleRemoveFieldMapping = (ruleId: string, mappingId: string) => {
    setRules((prev) =>
      prev.map((r) => {
        if (r.id !== ruleId) return r
        if (r.mappings.length <= 1) {
          toast.warning('Mỗi cấu hình cần ít nhất 1 cặp trường.')
          return r
        }
        return {
          ...r,
          mappings: r.mappings.filter((m) => m.id !== mappingId),
        }
      }),
    )
  }

  const handleUpdateFieldMapping = (
    ruleId: string,
    mappingId: string,
    updater: Partial<FieldMapping>,
  ) => {
    setRules((prev) =>
      prev.map((r) => {
        if (r.id !== ruleId) return r
        return {
          ...r,
          mappings: r.mappings.map((m) =>
            m.id === mappingId ? { ...m, ...updater } : m,
          ),
        }
      }),
    )
  }

  // Build an AudioDeckJob ready for the queue
  const buildJobFromCurrentConfig = useCallback((): AudioDeckJob | null => {
    if (!scanData || !selectedDeckId) {
      toast.error('Chưa có dữ liệu Deck để tạo tác vụ.')
      return null
    }

    const items: AudioJobItem[] = []

    for (const note of scanData.notes) {
      for (const rule of rules) {
        for (const mapping of rule.mappings) {
          const destStatus = note.audio_status[mapping.destinationField]?.status || 'missing'

          if (generationMode === 'missing_and_broken' && destStatus === 'valid') {
            continue
          }

          const rawText = note.field_values[mapping.sourceField] || ''
          const cleanedText = cleanTextForTts(rawText, rule.engineId)

          items.push({
            id: generateId(),
            noteId: note.note_id,
            cardId: note.card_id,
            word: note.word,
            sourceField: mapping.sourceField,
            destinationField: mapping.destinationField,
            text: cleanedText,
            engineId: rule.engineId,
            voiceId: rule.voiceId,
            options: {
              speed: rule.speed,
              pitch: rule.pitch,
              intonation: rule.intonation,
              volume: rule.volume,
            },
            status: 'pending',
          })
        }
      }
    }

    if (items.length === 0) {
      toast.info('Tất cả các từ đều đã có file âm thanh chuẩn. Không có mục nào cần tạo.')
      return null
    }

    const job: AudioDeckJob = {
      id: generateId(),
      deckId: selectedDeckId,
      deckName: scanData.deck.name,
      createdAt: new Date().toISOString(),
      status: 'queued',
      rules,
      mode: generationMode,
      stats: {
        totalItems: items.length,
        completedItems: 0,
        failedItems: 0,
        skippedItems: 0,
        currentItemIndex: 0,
        progressPercent: 0,
      },
      items,
    }

    return job
  }, [scanData, selectedDeckId, rules, generationMode])

  return {
    decks,
    deckOptions,
    isDecksLoading: decksQuery.isLoading,
    selectedDeckId,
    setSelectedDeckId,
    isScanning,
    scanData,
    handleScanDeck,
    generationMode,
    setGenerationMode,
    rules,
    availableFieldNames,
    handleAddRule,
    handleRemoveRule,
    handleUpdateRule,
    handleAddFieldMapping,
    handleRemoveFieldMapping,
    handleUpdateFieldMapping,
    buildJobFromCurrentConfig,
  }
}
