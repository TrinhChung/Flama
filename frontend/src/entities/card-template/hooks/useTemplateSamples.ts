import { useEffect, useMemo, useState } from 'react'
import type { TemplateSampleField, TemplateSampleValue, TemplateSampleValues } from '../model/previewSamples'

type Entry = { type: string; value: TemplateSampleValue }
type State = { scope: string; entries: Record<string, Entry> }

/** Ephemeral overrides: changing resource/type cannot reuse a previous sample. */
export function useTemplateSamples(scope: string, fields: ReadonlyArray<TemplateSampleField>) {
  const [state, setState] = useState<State>({ scope, entries: {} })
  const signature = JSON.stringify(fields.map(({ key, type }) => [key, type]))
  const types = useMemo(() => new Map<string, string>(JSON.parse(signature)), [signature])
  const values: TemplateSampleValues = useMemo(() => Object.assign(Object.create(null), Object.fromEntries(
    Object.entries(state.scope === scope ? state.entries : {}).filter(([key, entry]) => types.get(key) === entry.type).map(([key, entry]) => [key, entry.value]),
  )), [state, scope, types])

  useEffect(() => {
    const currentTypes = new Map<string, string>(JSON.parse(signature))
    setState((previous) => {
      if (previous.scope !== scope) return { scope, entries: {} }
      const entries = Object.fromEntries(Object.entries(previous.entries).filter(([key, entry]) => currentTypes.get(key) === entry.type))
      return Object.keys(entries).length === Object.keys(previous.entries).length ? previous : { scope, entries }
    })
  }, [scope, signature])

  return {
    values,
    setValue: (key: string, value: TemplateSampleValue) => {
      const type = types.get(key)
      if (!type) return
      setState((previous) => ({ scope, entries: { ...(previous.scope === scope ? previous.entries : {}), [key]: { type, value } } }))
    },
    reset: () => setState({ scope, entries: {} }),
  }
}
