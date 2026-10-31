import type { InfiniteData, QueryClient, QueryKey } from '@tanstack/react-query'

/**
 * Invalidating an infinite query refetches every loaded page one after
 * another; after many "load more" clicks that is slow. Start over from page one.
 */
export function refetchFromFirstPage(queryClient: QueryClient, queryKey: QueryKey) {
  queryClient.setQueriesData<InfiniteData<unknown, unknown>>({ queryKey }, (data) =>
    data && data.pages.length > 1
      ? { pages: data.pages.slice(0, 1), pageParams: data.pageParams.slice(0, 1) }
      : data,
  )
  return queryClient.invalidateQueries({ queryKey })
}
