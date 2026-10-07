import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { StatisticsConfig, StatisticsFilters } from '../types'

export function useStatisticsFilters(configData?: StatisticsConfig) {
  const [searchParams, setSearchParams] = useSearchParams()

  const urlDeckIdParam = searchParams.get('deck_id')
  const urlScopeParam = searchParams.get('scope')

  const [filters, setFilters] = useState<StatisticsFilters>(() => ({
    scope: urlScopeParam === 'collection' ? 'collection' : 'deck',
    deckId: urlDeckIdParam ? Number(urlDeckIdParam) : null,
    historyRange: '12m',
    futureRange: '30',
    backlog: true,
  }))

  useEffect(() => {
    if (configData && filters.deckId === null && filters.scope === 'deck') {
      const fallbackDeckId = urlDeckIdParam ? Number(urlDeckIdParam) : configData.initial_deck_id
      setFilters((current) => ({ ...current, deckId: fallbackDeckId }))
    }
  }, [configData, filters.deckId, filters.scope, urlDeckIdParam])

  const updateFiltersAndUrl = useCallback(
    (updater: (prev: StatisticsFilters) => StatisticsFilters) => {
      setFilters((prev) => {
        const next = updater(prev)
        const nextParams = new URLSearchParams(searchParams)
        if (next.scope === 'collection') {
          nextParams.set('scope', 'collection')
          nextParams.delete('deck_id')
        } else {
          nextParams.delete('scope')
          if (next.deckId) {
            nextParams.set('deck_id', String(next.deckId))
          } else {
            nextParams.delete('deck_id')
          }
        }
        setSearchParams(nextParams, { replace: true })
        return next
      })
    },
    [searchParams, setSearchParams],
  )

  return {
    filters,
    setFilters,
    updateFiltersAndUrl,
  }
}
