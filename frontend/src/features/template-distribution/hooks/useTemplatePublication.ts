import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { cardTemplateQueryKeys } from '@/entities/card-template'
import { distributionApi } from '../api/distributionApi'
import type { PublishTemplateReleaseBody } from '../model/types'

export function useTemplatePublication(templateId: string, enabled = true) {
  const queryClient = useQueryClient()

  const publicationQuery = useQuery({
    queryKey: cardTemplateQueryKeys.publication(templateId),
    queryFn: ({ signal }) => distributionApi.getPublication(templateId, signal),
    enabled: Boolean(templateId) && enabled,
  })

  const releasesQuery = useQuery({
    queryKey: cardTemplateQueryKeys.releases(templateId),
    queryFn: ({ signal }) => distributionApi.getReleases(templateId, undefined, signal),
    enabled: Boolean(templateId) && enabled,
  })

  const updateSettingsMutation = useMutation({
    mutationFn: (settings: { auto_publish_enabled: boolean }) =>
      distributionApi.updatePublicationSettings(templateId, settings),
    onSuccess: (data) => {
      queryClient.setQueryData(cardTemplateQueryKeys.publication(templateId), data)
    },
  })

  const publishReleaseMutation = useMutation({
    mutationFn: (body: PublishTemplateReleaseBody) =>
      distributionApi.publishRelease(templateId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cardTemplateQueryKeys.publication(templateId) })
      queryClient.invalidateQueries({ queryKey: cardTemplateQueryKeys.releases(templateId) })
    },
  })

  return {
    publication: publicationQuery.data,
    isLoading: publicationQuery.isLoading || releasesQuery.isLoading,
    isError: publicationQuery.isError || releasesQuery.isError,
    error: publicationQuery.error || releasesQuery.error,
    releases: releasesQuery.data?.items ?? [],
    hasMoreReleases: releasesQuery.data?.has_more ?? false,
    refetch: async () => {
      await Promise.all([publicationQuery.refetch(), releasesQuery.refetch()])
    },
    updateSettings: updateSettingsMutation.mutateAsync,
    isUpdatingSettings: updateSettingsMutation.isPending,
    publishRelease: publishReleaseMutation.mutateAsync,
    isPublishing: publishReleaseMutation.isPending,
  }
}
