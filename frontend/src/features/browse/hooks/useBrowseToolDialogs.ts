import { useState } from 'react'

export function useBrowseToolDialogs() {
  const [isLocalAudioModalOpen, setIsLocalAudioModalOpen] = useState(false)
  const [isStrokeModalOpen, setIsStrokeModalOpen] = useState(false)
  const [strokeModalMode, setStrokeModalMode] = useState<'single' | 'batch'>('batch')
  const [strokeModalCardId, setStrokeModalCardId] = useState<string | null>(null)
  const [localAudioEngineId, setLocalAudioEngineId] = useState<'voicevox' | 'kokoro'>('voicevox')
  const [localAudioDefaultVoiceId, setLocalAudioDefaultVoiceId] = useState<string | undefined>(undefined)
  const [localAudioTargetCardIds, setLocalAudioTargetCardIds] = useState<string[]>([])
  // Worksheet Generator Modal State
  const [isWorksheetModalOpen, setIsWorksheetModalOpen] = useState(false)
  const [worksheetTargetDeckId, setWorksheetTargetDeckId] = useState<number | null>(null)
  const [worksheetTargetCardIds, setWorksheetTargetCardIds] = useState<string[] | undefined>(undefined)


  return { isLocalAudioModalOpen, setIsLocalAudioModalOpen, isStrokeModalOpen, setIsStrokeModalOpen, strokeModalMode, setStrokeModalMode, strokeModalCardId, setStrokeModalCardId, localAudioEngineId, setLocalAudioEngineId, localAudioDefaultVoiceId, setLocalAudioDefaultVoiceId, localAudioTargetCardIds, setLocalAudioTargetCardIds, isWorksheetModalOpen, setIsWorksheetModalOpen, worksheetTargetDeckId, setWorksheetTargetDeckId, worksheetTargetCardIds, setWorksheetTargetCardIds }
}
