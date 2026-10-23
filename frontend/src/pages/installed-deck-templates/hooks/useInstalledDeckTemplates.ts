import { useQuery } from '@tanstack/react-query'
import { useParams, useSearchParams } from 'react-router-dom'
import { cardTemplateQueryKeys, fetchInstallTemplates } from '@/entities/card-template'

export function useInstalledDeckTemplates() {
  const { installId = '' } = useParams<{ installId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const query = useQuery({
    queryKey: cardTemplateQueryKeys.installTemplates(installId),
    queryFn: ({ signal }) => fetchInstallTemplates(installId, signal),
    enabled: Boolean(installId),
  })
  const items = query.data?.items ?? []
  const requestedId = searchParams.get('template')
  const requested = items.find((item) => item.source_template_id === requestedId)
  const selected = requested ?? items[0]

  const selectTemplate = (sourceId: string) => {
    const next = new URLSearchParams(searchParams)
    next.set('template', sourceId)
    setSearchParams(next, { replace: true })
  }

  return {
    query,
    items,
    selected,
    selectTemplate,
    requestedMissing: Boolean(requestedId && items.length && !requested),
  }
}
