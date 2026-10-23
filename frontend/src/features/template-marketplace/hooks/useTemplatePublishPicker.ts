import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { cardTemplateQueryKeys, fetchTemplateLibrary } from '@/entities/card-template'

export function usePublishTemplateSelection(open: boolean, templateId?: string) {
  const [selectedId, setSelectedId] = useState(templateId ?? '')
  useEffect(() => {
    if (open) setSelectedId(templateId ?? '')
  }, [open, templateId])
  return [selectedId, setSelectedId] as const
}

export function useTemplatePublishPicker() {
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [search])
  // "mine" excludes received copies: those can never be listed again.
  const params = useMemo(() => ({ group: 'mine' as const, compact: true, page_size: 50, ...(query ? { q: query } : {}) }), [query])
  const library = useQuery({
    queryKey: [...cardTemplateQueryKeys.library(params), 'publish-picker'],
    queryFn: ({ signal }) => fetchTemplateLibrary(params, signal),
  })
  return { search, setSearch, library }
}
