import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { loadStoredBrowseTtsSettings, resetStoredBrowseTtsSettings, saveStoredBrowseTtsSettings, type BrowseTtsSettings } from '../services/ttsSettingsStorage'
import type { CardDetailResponse } from '../types'

export function useBrowseTtsSettings(effectiveCardDetail: CardDetailResponse | undefined) {
  const { t } = useTranslation('browse')
  const [initialTtsSettings] = useState(loadStoredBrowseTtsSettings)
  const effectiveNoteTypeNameRef = useRef<string | undefined>(undefined)

  const [ttsSourceField, setTtsSourceFieldState] = useState<string>(
    initialTtsSettings.sourceField || 'Word'
  )
  const setTtsSourceField = (val: string | ((prev: string) => string)) => {
    setTtsSourceFieldState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      const noteTypeName = effectiveNoteTypeNameRef.current
      const updates: Partial<BrowseTtsSettings> = { sourceField: next }
      if (noteTypeName) {
        const currentMapping = loadStoredBrowseTtsSettings().fieldMappingByNoteType || {}
        updates.fieldMappingByNoteType = {
          ...currentMapping,
          [noteTypeName]: {
            ...(currentMapping[noteTypeName] || {}),
            sourceField: next,
          },
        }
      }
      saveStoredBrowseTtsSettings(updates)
      return next
    })
  }

  const [ttsDestinationField, setTtsDestinationFieldState] = useState<string>(
    initialTtsSettings.destinationField || 'Audio'
  )
  const setTtsDestinationField = (val: string | ((prev: string) => string)) => {
    setTtsDestinationFieldState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      const noteTypeName = effectiveNoteTypeNameRef.current
      const updates: Partial<BrowseTtsSettings> = { destinationField: next }
      if (noteTypeName) {
        const currentMapping = loadStoredBrowseTtsSettings().fieldMappingByNoteType || {}
        updates.fieldMappingByNoteType = {
          ...currentMapping,
          [noteTypeName]: {
            ...(currentMapping[noteTypeName] || {}),
            destinationField: next,
          },
        }
      }
      saveStoredBrowseTtsSettings(updates)
      return next
    })
  }

  const [ttsCharacter, setTtsCharacterState] = useState<string>(initialTtsSettings.character)
  const setTtsCharacter = (val: string | ((prev: string) => string)) => {
    setTtsCharacterState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ character: next })
      return next
    })
  }

  const [ttsApiKey, setTtsApiKey] = useState(() => {
    return localStorage.getItem('flama_voicevox_api_key') || ''
  })
  const [isKeySaved, setIsKeySaved] = useState(false)
  const [isSavingKey, setIsSavingKey] = useState(false)
  const [showApiKey, setShowApiKey] = useState(false)

  const [ttsAppendAudio, setTtsAppendAudioState] = useState<boolean>(initialTtsSettings.appendAudio)
  const setTtsAppendAudio = (val: boolean | ((prev: boolean) => boolean)) => {
    setTtsAppendAudioState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ appendAudio: next })
      return next
    })
  }

  const [ttsUseOpus, setTtsUseOpusState] = useState<boolean>(initialTtsSettings.useOpus)
  const setTtsUseOpus = (val: boolean | ((prev: boolean) => boolean)) => {
    setTtsUseOpusState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ useOpus: next })
      return next
    })
  }

  const [ttsVolumeScale, setTtsVolumeScaleState] = useState<number>(initialTtsSettings.volumeScale)
  const setTtsVolumeScale = (val: number | ((prev: number) => number)) => {
    setTtsVolumeScaleState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ volumeScale: next })
      return next
    })
  }

  const [ttsPitch, setTtsPitchState] = useState<number>(initialTtsSettings.pitch)
  const setTtsPitch = (val: number | ((prev: number) => number)) => {
    setTtsPitchState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ pitch: next })
      return next
    })
  }

  const [ttsSpeed, setTtsSpeedState] = useState<number>(initialTtsSettings.speed)
  const setTtsSpeed = (val: number | ((prev: number) => number)) => {
    setTtsSpeedState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ speed: next })
      return next
    })
  }

  const [ttsIntonationScale, setTtsIntonationScaleState] = useState<number>(initialTtsSettings.intonationScale)
  const setTtsIntonationScale = (val: number | ((prev: number) => number)) => {
    setTtsIntonationScaleState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ intonationScale: next })
      return next
    })
  }

  const [ttsInitialSilence, setTtsInitialSilenceState] = useState<number>(initialTtsSettings.initialSilence)
  const setTtsInitialSilence = (val: number | ((prev: number) => number)) => {
    setTtsInitialSilenceState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ initialSilence: next })
      return next
    })
  }

  const [ttsFinalSilence, setTtsFinalSilenceState] = useState<number>(initialTtsSettings.finalSilence)
  const setTtsFinalSilence = (val: number | ((prev: number) => number)) => {
    setTtsFinalSilenceState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ finalSilence: next })
      return next
    })
  }

  const ttsSourceFieldRef = useRef(ttsSourceField)
  ttsSourceFieldRef.current = ttsSourceField
  const ttsDestinationFieldRef = useRef(ttsDestinationField)
  ttsDestinationFieldRef.current = ttsDestinationField

  useEffect(() => {
    effectiveNoteTypeNameRef.current = effectiveCardDetail?.note?.note_type_name || undefined
    if (effectiveCardDetail?.fields && effectiveCardDetail.fields.length > 0) {
      const fields = effectiveCardDetail.fields
      const sourceFieldNames = fields
        .filter((field) => !['image', 'audio', 'diagram'].includes(String(field.field_type || '').toLowerCase()))
        .map((field) => field.name)
      const audioFieldNames = fields
        .filter((field) => String(field.field_type || '').toLowerCase() === 'audio')
        .map((field) => field.name)

      const noteTypeName = effectiveCardDetail.note?.note_type_name || undefined
      const storedSettings = loadStoredBrowseTtsSettings()
      const noteTypeMapping = noteTypeName ? storedSettings.fieldMappingByNoteType?.[noteTypeName] : undefined

      const currentSource = ttsSourceFieldRef.current
      if (currentSource && sourceFieldNames.includes(currentSource)) {
        // Keep current selected source field
      } else if (noteTypeMapping?.sourceField && sourceFieldNames.includes(noteTypeMapping.sourceField)) {
        setTtsSourceField(noteTypeMapping.sourceField)
      } else if (storedSettings.sourceField && sourceFieldNames.includes(storedSettings.sourceField)) {
        setTtsSourceField(storedSettings.sourceField)
      } else {
        const sourcePriority = [
          'Reading', 'reading',
          'Word', 'word',
          'Expression', 'expression',
          'Kanji', 'kanji',
          'Hanzi', 'hanzi',
          'Simplified', 'simplified',
          'Traditional', 'traditional',
          'Front', 'front',
          'Vocab', 'vocab',
          'Vocabulary', 'vocabulary',
          'Term', 'term',
          'Text', 'text',
        ]
        let foundSource = ''
        for (const p of sourcePriority) {
          const match = sourceFieldNames.find((f) => f.toLowerCase() === p.toLowerCase())
          if (match) {
            foundSource = match
            break
          }
        }
        setTtsSourceField(foundSource || (sourceFieldNames.length > 0 ? sourceFieldNames[0] : ''))
      }

      const currentDest = ttsDestinationFieldRef.current
      if (currentDest && audioFieldNames.includes(currentDest)) {
        // Keep current selected destination field
      } else if (noteTypeMapping?.destinationField && audioFieldNames.includes(noteTypeMapping.destinationField)) {
        setTtsDestinationField(noteTypeMapping.destinationField)
      } else if (storedSettings.destinationField && audioFieldNames.includes(storedSettings.destinationField)) {
        setTtsDestinationField(storedSettings.destinationField)
      } else {
        const destPriority = [
          'Audio', 'audio',
          'AudioReading', 'audioreading',
          'Sound', 'sound',
          'AudioWord', 'audioword',
          'Pronunciation', 'pronunciation',
          'Voice', 'voice',
        ]
        let foundDest = ''
        for (const p of destPriority) {
          const match = audioFieldNames.find((f) => f.toLowerCase() === p.toLowerCase())
          if (match) {
            foundDest = match
            break
          }
        }
        setTtsDestinationField(foundDest || (audioFieldNames.length > 0 ? audioFieldNames[0] : ''))
      }
    }
  }, [effectiveCardDetail])

  // Reset VoiceVox Settings
  const handleResetTtsDefaults = () => {
    resetStoredBrowseTtsSettings()
    setTtsSourceField('Word')
    setTtsDestinationField('Audio')
    setTtsCharacterState('')
    setTtsApiKey('')
    setTtsAppendAudioState(false)
    setTtsUseOpusState(false)
    setTtsVolumeScaleState(1.0)
    setTtsPitchState(0.0)
    setTtsSpeedState(1.0)
    setTtsIntonationScaleState(1.0)
    setTtsInitialSilenceState(0.1)
    setTtsFinalSilenceState(0.1)
    toast.info(t('toasts.reset_defaults'))
  }


  return { ttsSourceField, setTtsSourceField, ttsDestinationField, setTtsDestinationField, ttsCharacter, setTtsCharacter, ttsApiKey, setTtsApiKey, isKeySaved, setIsKeySaved, isSavingKey, setIsSavingKey, showApiKey, setShowApiKey, ttsAppendAudio, setTtsAppendAudio, ttsUseOpus, setTtsUseOpus, ttsVolumeScale, setTtsVolumeScale, ttsPitch, setTtsPitch, ttsSpeed, setTtsSpeed, ttsIntonationScale, setTtsIntonationScale, ttsInitialSilence, setTtsInitialSilence, ttsFinalSilence, setTtsFinalSilence, handleResetTtsDefaults }
}
