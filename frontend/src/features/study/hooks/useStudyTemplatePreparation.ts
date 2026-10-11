import { useCallback, useEffect, useRef, useState } from 'react'
import {
  type TemplateBindings,
  type TemplateInputSpec,
  type StudyTemplateFieldDef,
  type StudyTemplateComposition,
  type StudyTemplatePreparationEntry,
  type StudyTemplateInputsResponse,
  type StudyTemplatePresetWrite,
  type StudyTemplatePreset,
  fetchStudyTemplateInputs,
  fetchStudyTemplatePreset,
  isTypeCompatible,
  saveStudyTemplatePreset,
} from '@/entities/card-template'

export type {
  StudyTemplateFieldDef,
  StudyTemplateComposition,
  StudyTemplatePreparationEntry,
  StudyTemplateInputsResponse,
  StudyTemplatePresetWrite,
  StudyTemplatePreset,
}
export {
  fetchStudyTemplateInputs,
  fetchStudyTemplatePreset,
  saveStudyTemplatePreset,
}

/** `inputBindings` is undefined when the learner never customised the map:
 * the server then renders with the template's own application defaults. */
export type StudyTemplateSelection = {
  compositionId: string
  inputBindings?: Readonly<TemplateBindings>
}

export type StudyTemplateMapping = {
  inputBindings: TemplateBindings
  staleInputs: string[]
  customized: boolean
}

function isValidTarget(entry: StudyTemplatePreparationEntry, input: TemplateInputSpec, target: string | null | undefined) {
  return Boolean(target && entry.field_defs.some((field: StudyTemplateFieldDef) => field.id === target && isTypeCompatible(input.type, field.field_type)))
}

/** Saved targets win; a saved target that no longer fits falls back to the
 * template default so a renamed or deleted field never blocks studying. */
export function mappingFor(entry: StudyTemplatePreparationEntry, saved?: TemplateBindings): StudyTemplateMapping {
  const staleInputs: string[] = []
  const inputBindings = Object.fromEntries(entry.input_schema.map((input: TemplateInputSpec) => {
    const fallback = isValidTarget(entry, input, entry.input_bindings[input.key]) ? entry.input_bindings[input.key] : null
    if (!saved || !Object.hasOwn(saved, input.key)) return [input.key, fallback]
    const target = saved[input.key]
    if (target === null) return [input.key, null]
    if (isValidTarget(entry, input, target)) return [input.key, target]
    staleInputs.push(input.key)
    return [input.key, fallback]
  }))
  return { inputBindings, staleInputs, customized: saved !== undefined }
}

export function useStudyTemplatePreparation(deckId: string | null) {
  const [availability, setAvailability] = useState<StudyTemplateInputsResponse | null>(null)
  const [preset, setPreset] = useState<StudyTemplatePreset | null>(null)
  const [compositionId, setCompositionId] = useState<string | null>(null)
  const [inputBindings, setInputBindings] = useState<TemplateBindings>({})
  const [staleInputs, setStaleInputs] = useState<string[]>([])
  const [remember, setRemember] = useState(true)
  const [askBeforeStudy, setAskBeforeStudy] = useState(true)
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const generation = useRef(0)
  const controllerRef = useRef<AbortController | null>(null)
  const saving = useRef(false)
  const currentDeckRef = useRef(deckId)
  currentDeckRef.current = deckId

  useEffect(() => {
    generation.current += 1
    controllerRef.current?.abort()
    saving.current = false
    setAvailability(null); setPreset(null); setCompositionId(null); setInputBindings({}); setStaleInputs([])
    setRemember(true); setAskBeforeStudy(true); setIsLoading(false); setIsSaving(false); setError(null)
    return () => { generation.current += 1; controllerRef.current?.abort() }
  }, [deckId])

  const savedBindings = useCallback((source: StudyTemplatePreset | null, id: string) => (
    source && !source.stale_compositions.includes(id) && Object.hasOwn(source.input_bindings, id)
      ? source.input_bindings[id] : undefined
  ), [])

  const selectionOf = useCallback((
    choices: StudyTemplateInputsResponse, source: StudyTemplatePreset | null, id: string,
  ): StudyTemplateSelection => {
    const entry = choices.template_inputs[id]
    const saved = savedBindings(source, id)
    if (!entry || saved === undefined) return Object.freeze({ compositionId: id })
    return Object.freeze({ compositionId: id, inputBindings: Object.freeze({ ...mappingFor(entry, saved).inputBindings }) })
  }, [savedBindings])

  const load = useCallback(async (signal?: AbortSignal) => {
    if (!deckId) return null
    const requestGeneration = ++generation.current
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    const abort = () => controller.abort()
    signal?.addEventListener('abort', abort, { once: true })
    if (signal?.aborted) controller.abort()
    const isCurrent = () => generation.current === requestGeneration && currentDeckRef.current === deckId && !controller.signal.aborted
    setIsLoading(true); setError(null)
    try {
      const [choices, preferences] = await Promise.all([
        fetchStudyTemplateInputs(deckId, controller.signal),
        // A broken preference row must never block studying with defaults.
        fetchStudyTemplatePreset(deckId, controller.signal).catch(() => null),
      ])
      if (!isCurrent()) return null
      setAvailability(choices); setPreset(preferences)
      setAskBeforeStudy(preferences?.ask_before_study ?? true)
      if (preferences !== null) {
        setRemember(true)
      }
      const localSavedId = typeof window !== 'undefined' && deckId ? window.localStorage.getItem(`flama:study_composition:${deckId}`) : null
      const savedId = preferences?.selected_compositions?.find((id: string) =>
        choices.compositions.some((choice: StudyTemplateComposition) => choice.composition_id === id && !preferences.stale_compositions?.includes(id))
      ) ?? preferences?.selected_compositions?.[0] ?? (
        localSavedId && choices.compositions.some((choice: StudyTemplateComposition) => choice.composition_id === localSavedId)
          ? localSavedId
          : null
      )
      const savedChoice = savedId && !preferences?.stale_compositions?.includes(savedId)
        ? choices.compositions.find((choice: StudyTemplateComposition) => choice.composition_id === savedId) : undefined
      const initialId = savedChoice?.composition_id ?? choices.compositions[0]?.composition_id ?? null
      setCompositionId(initialId)
      const entry = initialId ? choices.template_inputs[initialId] : undefined
      const mapping = entry ? mappingFor(entry, savedBindings(preferences, initialId!)) : { inputBindings: {}, staleInputs: [], customized: false }
      setInputBindings(mapping.inputBindings); setStaleInputs(mapping.staleInputs)

      // Single-template decks prompt before study by default.
      // Only bypass the picker when there is exactly 1 composition AND
      // the learner has explicitly set ask_before_study: false in their preset.
      const shouldAutoSelect = choices.compositions.length === 1
        && preferences?.ask_before_study === false
      const autoSelection = shouldAutoSelect
        ? selectionOf(choices, preferences, choices.compositions[0].composition_id)
        : null
      return { availability: choices, autoSelection }
    } catch (caught) {
      if (isCurrent()) setError(caught)
      throw caught
    } finally {
      signal?.removeEventListener('abort', abort)
      if (isCurrent()) setIsLoading(false)
    }
  }, [deckId, savedBindings, selectionOf])

  const selectComposition = useCallback((id: string) => {
    const entry = availability?.template_inputs[id]
    if (!entry || !availability?.compositions.some((choice: StudyTemplateComposition) => choice.composition_id === id)) return
    const mapping = mappingFor(entry, savedBindings(preset, id))
    setCompositionId(id); setInputBindings(mapping.inputBindings); setStaleInputs(mapping.staleInputs); setError(null)
  }, [availability, preset, savedBindings])

  const changeBindings = useCallback((bindings: TemplateBindings) => {
    const entry = compositionId ? availability?.template_inputs[compositionId] : undefined
    if (!entry) return
    const mapping = mappingFor(entry, bindings)
    setInputBindings(mapping.inputBindings); setStaleInputs(mapping.staleInputs); setError(null)
  }, [availability, compositionId])

  const submit = useCallback(async (): Promise<StudyTemplateSelection | null> => {
    if (!deckId || !compositionId || saving.current) return null
    const entry = availability?.template_inputs[compositionId]
    if (!entry) return null
    const requestGeneration = generation.current
    const isCurrent = () => generation.current === requestGeneration && currentDeckRef.current === deckId
    const mapped = mappingFor(entry, inputBindings)
    const selection = Object.freeze({ compositionId, inputBindings: Object.freeze({ ...mapped.inputBindings }) })

    if (typeof window !== 'undefined' && deckId) {
      try {
        if (remember) {
          window.localStorage.setItem(`flama:study_composition:${deckId}`, compositionId)
        } else {
          window.localStorage.removeItem(`flama:study_composition:${deckId}`)
        }
      } catch {
        // Local storage quota or security error ignored
      }
    }

    if (!remember) {
      return selection
    }
    saving.current = true
    setIsSaving(true); setError(null)
    try {
      const kept: Record<string, TemplateBindings> = {}
      if (availability) {
        for (const choice of availability.compositions) {
          const other = choice.composition_id
          const saved = savedBindings(preset, other)
          const otherEntry = availability.template_inputs[other]
          if (other !== compositionId && saved !== undefined && otherEntry) {
            kept[other] = mappingFor(otherEntry, saved).inputBindings
          }
        }
      }
      kept[compositionId] = { ...selection.inputBindings }
      const payload: StudyTemplatePresetWrite = {
        selected_compositions: [compositionId],
        input_bindings: kept,
        ask_before_study: askBeforeStudy,
      }
      const saved = await saveStudyTemplatePreset(deckId, payload)
      if (!isCurrent()) return null
      setPreset({ ...payload, ...saved, stale_compositions: saved?.stale_compositions ?? [] })
      return selection
    } catch (caught) {
      if (isCurrent()) {
        console.warn('Failed to save study template preset:', caught)
      }
      return selection
    } finally {
      saving.current = false
      if (isCurrent()) setIsSaving(false)
    }
  }, [askBeforeStudy, availability, compositionId, deckId, inputBindings, preset, remember, savedBindings])

  const mappingOf = useCallback((id: string): StudyTemplateMapping | null => {
    const entry = availability?.template_inputs[id]
    return entry ? mappingFor(entry, savedBindings(preset, id)) : null
  }, [availability, preset, savedBindings])

  const selectionFor = useCallback((id: string): StudyTemplateSelection => (
    availability ? selectionOf(availability, preset, id) : Object.freeze({ compositionId: id })
  ), [availability, preset, selectionOf])

  /** Persist (or with `null`, forget) one template's map; other templates keep
   * theirs. Resolves to the selection a new session should open with. */
  const saveBindings = useCallback(async (id: string, bindings: TemplateBindings | null): Promise<StudyTemplateSelection | null> => {
    if (!deckId || !availability || saving.current) return null
    const entry = availability.template_inputs[id]
    if (!entry) return null
    const requestGeneration = generation.current
    const isCurrent = () => generation.current === requestGeneration && currentDeckRef.current === deckId
    const kept: Record<string, TemplateBindings> = {}
    for (const choice of availability.compositions) {
      const other = choice.composition_id
      const saved = savedBindings(preset, other)
      const otherEntry = availability.template_inputs[other]
      if (other !== id && saved !== undefined && otherEntry) kept[other] = mappingFor(otherEntry, saved).inputBindings
    }
    if (bindings) kept[id] = mappingFor(entry, bindings).inputBindings
    const payload: StudyTemplatePresetWrite = {
      selected_compositions: Object.keys(kept),
      input_bindings: kept,
      ask_before_study: preset?.ask_before_study ?? true,
    }
    saving.current = true
    setIsSaving(true); setError(null)
    try {
      const saved = await saveStudyTemplatePreset(deckId, payload)
      if (!isCurrent()) return null
      setPreset({ ...payload, ...saved, stale_compositions: saved?.stale_compositions ?? [] })
      return bindings
        ? Object.freeze({ compositionId: id, inputBindings: Object.freeze({ ...kept[id] }) })
        : Object.freeze({ compositionId: id })
    } catch (caught) {
      if (isCurrent()) setError(caught)
      return null
    } finally {
      saving.current = false
      if (isCurrent()) setIsSaving(false)
    }
  }, [availability, deckId, preset, savedBindings])

  return {
    availability,
    preset,
    compositionId,
    inputBindings,
    staleInputs,
    remember,
    askBeforeStudy,
    isLoading,
    isSaving,
    error,
    entry: compositionId ? availability?.template_inputs[compositionId] : undefined,
    load,
    submit,
    selectComposition,
    changeBindings,
    setRemember,
    setAskBeforeStudy,
    mappingOf,
    selectionFor,
    saveBindings,
  }
}

export type StudyTemplatePreparationState = ReturnType<typeof useStudyTemplatePreparation>
