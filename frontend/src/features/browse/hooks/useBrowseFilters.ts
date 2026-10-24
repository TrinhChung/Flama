import { useCallback, useEffect, useState } from 'react'
import type { BrowseSortBy, BrowseSortDir, BrowseStatusFilter } from '../types'
import { parseDeckIdParam } from '../utils/browseParams'

export function useBrowseFilters(urlDeckId: string | null) {
  // Left Pane: Deck Selection & Search
  const [selectedDeckId, setSelectedDeckId] = useState<number | null>(() => parseDeckIdParam(urlDeckId))
  const [deckSearch, setDeckSearch] = useState('')

  // Center Pane: Filter, Search, Sort & Paging
  const [queryText, setQueryText] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [statusFilter, setStatusFilterState] = useState<BrowseStatusFilter>('all')
  const [sortBy, setSortBy] = useState<BrowseSortBy>('due')
  const [sortDir, setSortDir] = useState<BrowseSortDir>('asc')
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState<number>(() => {
    const saved = localStorage.getItem('flama_browse_per_page')
    if (saved) {
      const parsed = parseInt(saved, 10)
      if (!isNaN(parsed) && [20, 50, 100, 200, 500].includes(parsed)) {
        return parsed
      }
    }
    return 100
  })
  const handlePerPageChange = useCallback((newPerPage: number) => {
    setPerPage(newPerPage)
    setPage(1)
    localStorage.setItem('flama_browse_per_page', String(newPerPage))
  }, [])

  const setStatusFilter = useCallback((next: BrowseStatusFilter) => {
    setStatusFilterState(next)
    setPage(1)
  }, [])

  const handleSortChange = useCallback((field: BrowseSortBy) => {
    if (field === sortBy) {
      setSortDir((current) => (current === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(field)
      setSortDir('asc')
    }
    setPage(1)
  }, [sortBy])

  // Debounce main search query; only a changed query sends paging back to 1.
  useEffect(() => {
    const nextQuery = queryText.trim()
    if (nextQuery === debouncedQuery) return
    const timer = window.setTimeout(() => {
      setDebouncedQuery(nextQuery)
      setPage(1)
    }, 400)
    return () => window.clearTimeout(timer)
  }, [queryText, debouncedQuery])


  const handleResetDeckFilter = () => { setSelectedDeckId(null); setDeckSearch(''); setPage(1) }

  return { selectedDeckId, setSelectedDeckId, deckSearch, setDeckSearch, queryText, setQueryText, debouncedQuery, statusFilter, setStatusFilter, sortBy, sortDir, page, setPage, perPage, handlePerPageChange, handleSortChange, handleResetDeckFilter }
}
