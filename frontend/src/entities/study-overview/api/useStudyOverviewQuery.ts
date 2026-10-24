import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { fetchStudyOverview, studyOverviewQueryKey } from './studyOverviewApi'

/** Yearly heatmap, streaks and today's totals for the signed-in learner. */
export function useStudyOverviewQuery(
  year: number,
  { keepPreviousYear = false }: { keepPreviousYear?: boolean } = {},
) {
  return useQuery({
    queryKey: studyOverviewQueryKey(year),
    queryFn: () => fetchStudyOverview(year),
    // Switching year keeps the previous grid on screen instead of collapsing to a skeleton.
    placeholderData: keepPreviousYear ? keepPreviousData : undefined,
  })
}
