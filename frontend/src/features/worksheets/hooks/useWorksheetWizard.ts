import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { fetchDeckWorksheetMeta } from '../api'
import type { DeckWorksheetMeta, WorksheetFieldMapping } from '../types'
import type { WizardStepId } from '../config/wizardSteps'
import {
  defaultTemplateIdFor,
  hasMixedNoteTypes,
  resolveStudioSetup,
  STANDALONE_DEFAULT_TEMPLATE_ID,
} from '../utils/worksheetMeta'
import { saveWorksheetPreset } from '../utils/worksheetStorage'
import { useWorksheetStudio, type WorksheetScope } from './useWorksheetStudio'

export interface UseWorksheetWizardProps {
  deckId?: number | null
  deckName?: string
  initialCardIds?: (string | number)[]
  selectionKind?: 'card' | 'note'
  initialStep?: WizardStepId
}

function initialStepFor(deckId: number | null, initialStep?: WizardStepId): WizardStepId {
  return initialStep || (deckId ? 'mapping' : 'deck')
}

/** Deck → mapping → template → studio flow, including deck metadata loading. */
export function useWorksheetWizard({ deckId, deckName, initialCardIds, selectionKind, initialStep }: UseWorksheetWizardProps) {
  const [currentDeckId, setCurrentDeckId] = useState<number | null>(deckId || null)
  const [isStandalone, setIsStandalone] = useState<boolean>(!deckId)
  const [wizardStep, setWizardStep] = useState<WizardStepId>(() => initialStepFor(deckId || null, initialStep))
  const [isLoadingMeta, setIsLoadingMeta] = useState(false)
  const [meta, setMeta] = useState<DeckWorksheetMeta | null>(null)
  const [selectedNoteTypeId, setSelectedNoteTypeId] = useState<string>('')
  const [scope, setScope] = useState<WorksheetScope>('all')
  const [limitCount, setLimitCount] = useState<number>(20)

  const studio = useWorksheetStudio({
    wizardStep,
    currentDeckId,
    deckName,
    initialCardIds,
    selectionKind,
    meta,
    initialTemplateId: defaultTemplateIdFor(deckId),
    selectedNoteTypeId,
    scope,
    limitCount,
  })

  const activeNoteType = useMemo(() => {
    if (!meta?.note_types) return null
    return (
      meta.note_types.find((nt) => String(nt.id) === String(selectedNoteTypeId)) ||
      meta.note_types[0]
    )
  }, [meta, selectedNoteTypeId])

  const availableFields = useMemo(() => activeNoteType?.fields || [], [activeNoteType])
  const isMixedDeck = hasMixedNoteTypes(meta)
  const deckLabel = meta?.deck_name || deckName || 'Bộ thẻ'

  // Metadata the deck picker already fetched; the loader effect must not refetch it.
  const acceptedMetaDeckIdRef = useRef<number | null>(null)

  const applyMeta = (data: DeckWorksheetMeta, setupDeckId: number | null, setupDeckName?: string) => {
    setMeta(data)
    const setup = resolveStudioSetup(data, {
      deckId: setupDeckId,
      deckName: setupDeckName,
      baseOptions: studio.getLayoutOptions(),
    })
    if (setup.noteTypeId) setSelectedNoteTypeId(setup.noteTypeId)
    studio.applySetup(setup)
  }

  // Follow deck/step props that change while the studio stays open.
  useEffect(() => {
    const nextDeckId = deckId || null
    setCurrentDeckId(nextDeckId)
    setIsStandalone(!nextDeckId)
    setWizardStep(initialStepFor(nextDeckId, initialStep))
  }, [deckId, initialStep])

  // Load deck worksheet meta on open or when currentDeckId changes
  useEffect(() => {
    studio.resetPreview()
    setScope(initialCardIds && initialCardIds.length > 0 ? 'selected' : 'all')

    const alreadyLoaded = Boolean(currentDeckId) && acceptedMetaDeckIdRef.current === currentDeckId
    acceptedMetaDeckIdRef.current = null
    if (alreadyLoaded) {
      setIsLoadingMeta(false)
      return
    }

    let cancelled = false
    setIsLoadingMeta(true)
    fetchDeckWorksheetMeta(currentDeckId)
      .then((data) => {
        if (cancelled) return
        applyMeta(data, currentDeckId, deckName)
        // A mixed deck cannot be mapped: send the user back to the deck picker.
        if (currentDeckId && hasMixedNoteTypes(data)) {
          setWizardStep('deck')
        }
      })
      .catch((err) => {
        if (cancelled) return
        toast.error('Không thể tải thông tin bộ thẻ: ' + String(err.message || err))
      })
      .finally(() => {
        if (!cancelled) setIsLoadingMeta(false)
      })

    return () => {
      cancelled = true
    }
    // Reload only when the deck changes; `studio` and `applyMeta` are recreated every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentDeckId, deckName, initialCardIds])

  const selectDeck = (newDeckId: number, newMeta: DeckWorksheetMeta) => {
    acceptedMetaDeckIdRef.current = newDeckId
    setCurrentDeckId(newDeckId)
    setIsStandalone(false)
    applyMeta(newMeta, newDeckId)
    setWizardStep('mapping')
  }

  const selectStandalone = () => {
    setCurrentDeckId(null)
    setIsStandalone(true)
    studio.setSelectedTemplateId(STANDALONE_DEFAULT_TEMPLATE_ID)
    setWizardStep('template')
  }

  /** Stepper navigation; the mapping step needs a single-note-type deck. */
  const goToStep = (step: WizardStepId) => {
    if (step === 'mapping' && (!currentDeckId || isMixedDeck)) return
    setWizardStep(step)
  }

  const savePreset = (fieldMapping: WorksheetFieldMapping) => {
    if (!activeNoteType) return
    saveWorksheetPreset(activeNoteType.id, {
      fieldMapping,
      templateId: studio.selectedTemplateId,
      layoutOptions: studio.layoutOptions,
    })
  }

  const confirmMapping = (newMapping: WorksheetFieldMapping) => {
    studio.setFieldMapping(newMapping)
    savePreset(newMapping)
    setWizardStep('template')
  }

  const confirmTemplate = () => {
    savePreset(studio.fieldMapping)
    setWizardStep('studio')
  }

  const backFromTemplate = () => setWizardStep(isStandalone ? 'deck' : 'mapping')

  return {
    studio,
    currentDeckId,
    isStandalone,
    wizardStep,
    setWizardStep,
    goToStep,
    isLoadingMeta,
    meta,
    deckLabel,
    isMixedDeck,
    activeNoteType,
    availableFields,
    selectedNoteTypeId,
    setSelectedNoteTypeId,
    scope,
    setScope,
    limitCount,
    setLimitCount,
    initialCardIds,
    selectDeck,
    selectStandalone,
    confirmMapping,
    confirmTemplate,
    backFromTemplate,
  }
}

export type WorksheetWizardState = ReturnType<typeof useWorksheetWizard>
