import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { cardTemplateQueryKeys } from '@/entities/card-template'
import { distributionApi } from '../api/distributionApi'
import type { ApplyTemplateUpdateBody } from '../model/types'

export function useTemplateSubscription(templateId: string, enabled = true) {
  const queryClient = useQueryClient()

  const subscriptionQuery = useQuery({
    queryKey: cardTemplateQueryKeys.subscription(templateId),
    queryFn: ({ signal }) => distributionApi.getSubscription(templateId, signal),
    enabled: Boolean(templateId) && enabled,
  })

  const updateSettingsMutation = useMutation({
    mutationFn: (settings: { auto_update_enabled: boolean }) =>
      distributionApi.updateSubscriptionSettings(templateId, settings),
    onSuccess: (data) => {
      queryClient.setQueryData(cardTemplateQueryKeys.subscription(templateId), data)
    },
  })

  const prepareUpdateMutation = useMutation({
    mutationFn: (body: {
      release_id: string
      expected_applied_release_id?: string
      expected_current_version_id?: string
      idempotency_key?: string
    }) => distributionApi.prepareUpdate(templateId, body),
    onSuccess: (data) => {
      queryClient.setQueryData(
        cardTemplateQueryKeys.subscription(templateId),
        (old: any) => (old ? { ...old, pending_update_json: data } : old),
      )
    },
  })

  const applyUpdateMutation = useMutation({
    mutationFn: (body: ApplyTemplateUpdateBody) =>
      distributionApi.applyUpdate(templateId, body),
    onSuccess: (data) => {
      queryClient.setQueryData(cardTemplateQueryKeys.subscription(templateId), data)
      queryClient.invalidateQueries({ queryKey: cardTemplateQueryKeys.libraryDetail(templateId) })
      queryClient.invalidateQueries({ queryKey: cardTemplateQueryKeys.templateVersions(templateId) })
    },
  })

  const resetToUpstreamMutation = useMutation({
    mutationFn: () => distributionApi.resetToUpstream(templateId),
    onSuccess: (data) => {
      queryClient.setQueryData(cardTemplateQueryKeys.subscription(templateId), data)
      queryClient.invalidateQueries({ queryKey: cardTemplateQueryKeys.libraryDetail(templateId) })
      queryClient.invalidateQueries({ queryKey: cardTemplateQueryKeys.templateVersions(templateId) })
    },
  })

  return {
    subscription: subscriptionQuery.data,
    isLoading: subscriptionQuery.isLoading,
    isError: subscriptionQuery.isError,
    error: subscriptionQuery.error,
    refetch: subscriptionQuery.refetch,
    updateSettings: updateSettingsMutation.mutateAsync,
    isUpdatingSettings: updateSettingsMutation.isPending,
    prepareUpdate: prepareUpdateMutation.mutateAsync,
    isPreparingUpdate: prepareUpdateMutation.isPending,
    applyUpdate: applyUpdateMutation.mutateAsync,
    isApplyingUpdate: applyUpdateMutation.isPending,
    resetToUpstream: resetToUpstreamMutation.mutateAsync,
    isResettingToUpstream: resetToUpstreamMutation.isPending,
  }
}
