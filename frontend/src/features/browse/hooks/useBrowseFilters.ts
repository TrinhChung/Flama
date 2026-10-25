import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BROWSE_SEARCH_MAX_LENGTH, BROWSE_SORT_FIELDS, isBrowseStatusFilter, type BrowseSortBy, type BrowseSortDir, type BrowseStatusFilter } from '../types'
import { parseDeckIdParam } from '../utils/browseParams'

function savedPerPage() {
  const value = Number(localStorage.getItem('flama_browse_per_page'))
  return [20, 50, 100, 200, 500].includes(value) ? value : 100
}

function positiveInteger(raw: string | null, fallback: number, max = Number.MAX_SAFE_INTEGER) {
  const value = parseDeckIdParam(raw)
  return value !== null && value <= max ? value : fallback
}

/** URL owns the request state from the first render, including Back/Forward. */
export function useBrowseFilters() {
  const [params, setParams] = useSearchParams()
  const [defaultPerPage] = useState(savedPerPage)
  const selectedDeckId = parseDeckIdParam(params.get('deck_id'))
  const page = positiveInteger(params.get('page'), 1)
  const perPage = positiveInteger(params.get('per_page'), defaultPerPage, 500)
  const debouncedQuery = (params.get('q') || '').trim().slice(0, BROWSE_SEARCH_MAX_LENGTH)
  const rawStatus = params.get('status') || 'all'
  const statusFilter: BrowseStatusFilter = isBrowseStatusFilter(rawStatus) ? rawStatus : 'all'
  const rawSort = params.get('sort_by')
  const sortBy: BrowseSortBy = BROWSE_SORT_FIELDS.find((field) => field === rawSort) || 'due'
  const sortDir: BrowseSortDir = params.get('sort_dir') === 'desc' ? 'desc' : 'asc'
  const [deckSearch, setDeckSearch] = useState('')
  const [queryText, setQueryText] = useState(debouncedQuery)

  const updateParams = useCallback((values: Record<string, string | null>, resetPage = false, replace = false) => {
    setParams((current) => {
      const next = new URLSearchParams(current)
      Object.entries(values).forEach(([key, value]) => value === null ? next.delete(key) : next.set(key, value))
      if (resetPage) next.set('page', '1')
      if (!next.has('per_page')) next.set('per_page', String(perPage))
      return next
    }, { replace })
  }, [setParams, perPage])

  const setPage = useCallback((value: number | ((previous: number) => number)) => {
    const next = typeof value === 'function' ? value(page) : value
    if (Number.isSafeInteger(next) && next > 0 && next !== page) updateParams({ page: String(next) })
  }, [page, updateParams])

  const setSelectedDeckId = useCallback((id: number | null) => {
    if (id !== selectedDeckId) updateParams({ deck_id: id === null ? null : String(id) }, true)
  }, [selectedDeckId, updateParams])

  const handlePerPageChange = useCallback((value: number) => {
    if (!Number.isInteger(value) || value < 1 || value > 500) return
    localStorage.setItem('flama_browse_per_page', String(value))
    updateParams({ per_page: String(value) }, true)
  }, [updateParams])

  const setStatusFilter = useCallback((value: BrowseStatusFilter) => updateParams({ status: value }, true), [updateParams])
  const handleSortChange = useCallback((field: BrowseSortBy) => {
    updateParams({ sort_by: field, sort_dir: field === sortBy && sortDir === 'asc' ? 'desc' : 'asc' }, true)
  }, [sortBy, sortDir, updateParams])

  useEffect(() => { setQueryText(debouncedQuery) }, [debouncedQuery])
  useEffect(() => {
    const next = queryText.trim().slice(0, BROWSE_SEARCH_MAX_LENGTH)
    if (next === debouncedQuery) return
    const timer = window.setTimeout(() => updateParams({ q: next || null }, true, true), 400)
    return () => window.clearTimeout(timer)
  }, [queryText, debouncedQuery, updateParams])

  const handleResetDeckFilter = useCallback(() => { setSelectedDeckId(null); setDeckSearch('') }, [setSelectedDeckId])
  return { selectedDeckId, setSelectedDeckId, deckSearch, setDeckSearch, queryText, setQueryText, debouncedQuery, statusFilter, setStatusFilter, sortBy, sortDir, page, setPage, perPage, handlePerPageChange, handleSortChange, handleResetDeckFilter }
}
