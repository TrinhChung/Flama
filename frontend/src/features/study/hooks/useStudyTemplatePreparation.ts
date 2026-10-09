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

export type StudyTemplateSelection = {
  compositionId: string
  inputBindings: Readonly<TemplateBindings>
}

function mappingFor(entry: StudyTemplatePreparationEntry, saved?: TemplateBindings) {
  const source = saved === undefined ? entry.input_bindings : saved
  const staleInputs: string[] = []
  const inputBindings = Object.fromEntries(entry.input_schema.map((input: TemplateInputSpec) => {
    const target = Object.hasOwn(source, input.key) ? source[input.key] : null
    const valid = target && entry.field_defs.some((field: StudyTemplateFieldDef) => field.id === target && field.field_type === input.type)
    if (target && !valid) staleInputs.push(input.key)
    return [input.key, valid ? target : null]
  }))
  return { inputBindings, staleInputs }
}

export function useStudyTemplatePreparation(deckId: string | null) {
  const [availability, setAvailability] = useState<StudyTemplateInputsResponse | null>(null)
  const [preset, setPreset] = useState<StudyTemplatePreset | null>(null)
  const [compositionId, setCompositionId] = useState<string | null>(null)
  const [inputBindings, setInputBindings] = useState<TemplateBindings>({})
  const [staleInputs, setStaleInputs] = useState<string[]>([])
  const [remember, setRemember] = useState(false)
  const [askBeforeStudy, setAskBeforeStudy] = useState(true)
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const generation = useRef(0)
  const controllerRef = useRef<AbortController | null>(null)
  const submissionOwner = useRef<symbol | null>(null)
  const currentDeckRef = useRef(deckId)
  currentDeckRef.current = deckId

  useEffect(() => {
    generation.current += 1
    controllerRef.current?.abort()
    submissionOwner.current = null
    setAvailability(null); setPreset(null); setCompositionId(null); setInputBindings({}); setStaleInputs([])
    setRemember(false); setAskBeforeStudy(true); setIsLoading(false); setIsSaving(false); setError(null)
    return () => { generation.current += 1; controllerRef.current?.abort() }
  }, [deckId])

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
        fetchStudyTemplateInputs(deckId, controller.signal), fetchStudyTemplatePreset(deckId, controller.signal),
      ])
      if (!isCurrent()) return null
      setAvailability(choices); setPreset(preferences); setAskBeforeStudy(preferences.ask_before_study)
      const savedId = preferences.selected_compositions.length === 1 ? preferences.selected_compositions[0] : null
      const savedChoice = savedId && !preferences.stale_compositions.includes(savedId)
        ? choices.compositions.find((choice: StudyTemplateComposition) => choice.composition_id === savedId) : undefined
      const initialId = savedChoice?.composition_id ?? (choices.compositions.length === 1 ? choices.compositions[0].composition_id : null)
      setCompositionId(initialId)
      const entry = initialId ? choices.template_inputs[initialId] : undefined
      const mapping = entry ? mappingFor(entry, preferences.input_bindings[initialId!]) : { inputBindings: {}, staleInputs: [] }
      setInputBindings(mapping.inputBindings); setStaleInputs(mapping.staleInputs)
      // Invalid saved targets need user correction, even if prompts were disabled.
      const autoSelection = !preferences.ask_before_study && savedChoice && entry && mapping.staleInputs.length === 0
        ? Object.freeze({ compositionId: savedChoice.composition_id, inputBindings: Object.freeze({ ...mapping.inputBindings }) }) : null
      return { availability: choices, autoSelection }
    } catch (caught) {
      if (isCurrent()) setError(caught)
      throw caught
    } finally {
      signal?.removeEventListener('abort', abort)
      if (isCurrent()) setIsLoading(false)
    }
  }, [deckId])

  const selectComposition = useCallback((id: string) => {
    const entry = availability?.template_inputs[id]
    if (!entry || !availability?.compositions.some((choice: StudyTemplateComposition) => choice.composition_id === id)) return
    const mapping = mappingFor(entry, preset?.input_bindings[id])
    setCompositionId(id); setInputBindings(mapping.inputBindings); setStaleInputs(mapping.staleInputs); setError(null)
  }, [availability, preset])

  const changeBindings = useCallback((bindings: TemplateBindings) => {
    const entry = compositionId ? availability?.template_inputs[compositionId] : undefined
    if (!entry) return
    const mapping = mappingFor(entry, bindings)
    setInputBindings(mapping.inputBindings); setStaleInputs(mapping.staleInputs); setError(null)
  }, [availability, compositionId])

  const submit = useCallback(async (): Promise<StudyTemplateSelection | null> => {
    if (!deckId || !compositionId || submissionOwner.current) return null
    const entry = availability?.template_inputs[compositionId]
    if (!entry) return null
    const owner = Symbol('preference-submit')
    submissionOwner.current = owner
    const requestGeneration = generation.current
    const selection = Object.freeze({ compositionId, inputBindings: Object.freeze({ ...mappingFor(entry, inputBindings).inputBindings }) })
    setIsSaving(true); setError(null)
    try {
      if (remember) {
        await saveStudyTemplatePreset(deckId, {
          selected_compositions: [compositionId], input_bindings: { [compositionId]: { ...selection.inputBindings } }, ask_before_study: askBeforeStudy,
        })
      }
      return generation.current === requestGeneration && currentDeckRef.current === deckId ? selection : null
    } catch (caught) {
      if (generation.current === requestGeneration && currentDeckRef.current === deckId) setError(caught)
      return null
    } finally {
      if (submissionOwner.current === owner) submissionOwner.current = null
      if (generation.current === requestGeneration && currentDeckRef.current === deckId) setIsSaving(false)
    }
  }, [askBeforeStudy, availability, compositionId, deckId, inputBindings, remember])

  return {
    availability, compositionId, inputBindings, staleInputs, remember, askBeforeStudy, isLoading, isSaving, error,
    entry: compositionId ? availability?.template_inputs[compositionId] : undefined,
    load, submit, selectComposition, changeBindings, setRemember, setAskBeforeStudy,
  }
}

export type StudyTemplatePreparationState = ReturnType<typeof useStudyTemplatePreparation>
