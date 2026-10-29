import { useQuery } from '@tanstack/react-query'
import { getInstalledDeckUpdates } from '../api'

export function useInstalledDeckContentModel(installId: string) {
  return useQuery({
    queryKey: ['installed-deck-updates', installId],
    enabled: Boolean(installId),
    queryFn: ({ signal }) => getInstalledDeckUpdates(installId, signal),
  })
}
