import { useEffect, useState } from 'react'
import { useQuotaUserSearchQuery } from '../api/quotasApi'

const SEARCH_DEBOUNCE_MS = 300

/** Debounced user lookup for granting a per-user quota. */
export function useQuotaUserSearch() {
  const [input, setInput] = useState('')
  const [term, setTerm] = useState('')

  useEffect(() => {
    const timer = window.setTimeout(() => setTerm(input.trim()), SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [input])

  const query = useQuotaUserSearchQuery(term)

  return {
    input,
    setInput,
    term,
    results: term.length >= 2 ? query.data ?? [] : [],
    isSearching: query.isFetching,
    reset: () => {
      setInput('')
      setTerm('')
    },
  }
}
