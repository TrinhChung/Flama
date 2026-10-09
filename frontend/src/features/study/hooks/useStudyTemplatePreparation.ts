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
  return Boolean(target && entry.field_defs.some((field: StudyTemplateFieldDef) => field.id === target && field.field_type === input.type))
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
    setAvailability(null); setPreset(null); setIsLoading(false); setIsSaving(false); setError(null)
    return () => { generation.current += 1; controllerRef.current?.abort() }
  }, [deckId])

  const savedBindings = useCallback((source: StudyTemplatePreset | null, compositionId: string) => (
    source && !source.stale_compositions.includes(compositionId) && Object.hasOwn(source.input_bindings, compositionId)
      ? source.input_bindings[compositionId] : undefined
  ), [])

  const selectionOf = useCallback((
    choices: StudyTemplateInputsResponse, source: StudyTemplatePreset | null, compositionId: string,
  ): StudyTemplateSelection => {
    const entry = choices.template_inputs[compositionId]
    const saved = savedBindings(source, compositionId)
    if (!entry || saved === undefined) return Object.freeze({ compositionId })
    return Object.freeze({ compositionId, inputBindings: Object.freeze({ ...mappingFor(entry, saved).inputBindings }) })
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
      // Only an ambiguous deck needs the picker; a single template starts right away.
      const autoSelection = choices.compositions.length === 1
        ? selectionOf(choices, preferences, choices.compositions[0].composition_id) : null
      return { availability: choices, autoSelection }
    } catch (caught) {
      if (isCurrent()) setError(caught)
      throw caught
    } finally {
      signal?.removeEventListener('abort', abort)
      if (isCurrent()) setIsLoading(false)
    }
  }, [deckId, selectionOf])

  const mappingOf = useCallback((compositionId: string): StudyTemplateMapping | null => {
    const entry = availability?.template_inputs[compositionId]
    return entry ? mappingFor(entry, savedBindings(preset, compositionId)) : null
  }, [availability, preset, savedBindings])

  const selectionFor = useCallback((compositionId: string): StudyTemplateSelection => (
    availability ? selectionOf(availability, preset, compositionId) : Object.freeze({ compositionId })
  ), [availability, preset, selectionOf])

  /** Persist (or with `null`, forget) one template's map; other templates keep
   * theirs. Resolves to the selection a new session should open with. */
  const saveBindings = useCallback(async (compositionId: string, bindings: TemplateBindings | null): Promise<StudyTemplateSelection | null> => {
    if (!deckId || !availability || saving.current) return null
    const entry = availability.template_inputs[compositionId]
    if (!entry) return null
    const requestGeneration = generation.current
    const isCurrent = () => generation.current === requestGeneration && currentDeckRef.current === deckId
    const kept: Record<string, TemplateBindings> = {}
    for (const choice of availability.compositions) {
      const other = choice.composition_id
      const saved = savedBindings(preset, other)
      const otherEntry = availability.template_inputs[other]
      if (other !== compositionId && saved !== undefined && otherEntry) kept[other] = mappingFor(otherEntry, saved).inputBindings
    }
    if (bindings) kept[compositionId] = mappingFor(entry, bindings).inputBindings
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
        ? Object.freeze({ compositionId, inputBindings: Object.freeze({ ...kept[compositionId] }) })
        : Object.freeze({ compositionId })
    } catch (caught) {
      if (isCurrent()) setError(caught)
      return null
    } finally {
      saving.current = false
      if (isCurrent()) setIsSaving(false)
    }
  }, [availability, deckId, preset, savedBindings])

  return {
    availability, preset, isLoading, isSaving, error,
    load, mappingOf, selectionFor, saveBindings,
  }
}

export type StudyTemplatePreparationState = ReturnType<typeof useStudyTemplatePreparation>
