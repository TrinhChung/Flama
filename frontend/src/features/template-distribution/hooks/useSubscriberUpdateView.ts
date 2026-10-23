import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { useTemplateSubscription } from './useTemplateSubscription'
import type { ConflictResolution, PendingUpdateDto } from '../model/types'

type SubscriberUpdateViewOptions = {
  templateId: string
  currentVersionId?: string | null
  onSourceChanged?: () => void
}

export function useSubscriberUpdateView({ templateId, currentVersionId, onSourceChanged }: SubscriberUpdateViewOptions) {
  const { t } = useTranslation('card_templates')
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false)
  const [activePendingUpdate, setActivePendingUpdate] = useState<PendingUpdateDto | null>(null)
  const [conflictDialogOpen, setConflictDialogOpen] = useState(false)

  const {
    subscription,
    isLoading,
    isError,
    error,
    refetch,
    updateSettings,
    isUpdatingSettings,
    prepareUpdate,
    isPreparingUpdate,
    applyUpdate,
    isApplyingUpdate,
    resetToUpstream,
    isResettingToUpstream,
  } = useTemplateSubscription(templateId)

  const isLegacyUnpinned = Boolean(subscription && (
    subscription.legacy_unpinned || subscription.requires_new_canonical_receipt
    || subscription.last_sync_status === 'legacy_unpinned' || !subscription.applied_release_id
  ))

  const handleResetOpenChange = (open: boolean) => setResetConfirmOpen(open && !isLegacyUnpinned)
  const handleConflictOpenChange = (open: boolean) => {
    setConflictDialogOpen(open && !isLegacyUnpinned)
    if (!open) setActivePendingUpdate(null)
  }

  const handleToggleAutoUpdate = async (checked: boolean) => {
    if (isLegacyUnpinned || !subscription) return
    try {
      await updateSettings({ auto_update_enabled: checked })
      toast.success(t('setup.saved'))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('distribution.update_error'))
    }
  }

  const handleStartUpdate = async () => {
    if (isLegacyUnpinned || !subscription?.current_release?.id) return
    try {
      const pending = await prepareUpdate({
        release_id: subscription.current_release.id,
        expected_applied_release_id: subscription.applied_release_id || undefined,
        expected_current_version_id: currentVersionId || subscription.current_version_id || undefined,
      })

      if (pending.status === 'has_conflict' && Object.keys(pending.conflicts || {}).length > 0) {
        setActivePendingUpdate(pending)
        setConflictDialogOpen(true)
      } else {
        // Ready without conflict, apply directly
        await applyUpdate({
          preparation_id: pending.id,
        })
        toast.success(t('distribution.update_success'))
        onSourceChanged?.()
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('distribution.update_error'))
    }
  }

  const handleApplyResolvedUpdate = async (resolutions: Record<string, ConflictResolution>) => {
    if (isLegacyUnpinned || !activePendingUpdate) return
    await applyUpdate({
      preparation_id: activePendingUpdate.id,
      resolutions,
    })
    toast.success(t('distribution.update_success'))
    setActivePendingUpdate(null)
    onSourceChanged?.()
  }

  const handleResetToUpstream = async () => {
    if (isLegacyUnpinned || !subscription) return
    try {
      await resetToUpstream()
      toast.success(t('distribution.reset_upstream_success'))
      setResetConfirmOpen(false)
      onSourceChanged?.()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('distribution.reset_upstream_error'))
    }
  }

  const appliedRelease = subscription?.applied_release
  const latestRelease = subscription?.current_release
  const updateAvailable = !isLegacyUnpinned && Boolean(subscription?.update_available)
  const originalListingUrl = subscription?.source_template_id
    ? `/marketplace/templates/${encodeURIComponent(subscription.source_template_id)}`
    : null

  return {
    subscription, isLoading, isError, error, refetch, isUpdatingSettings, isPreparingUpdate,
    isApplyingUpdate, isResettingToUpstream, isLegacyUnpinned, appliedRelease, latestRelease,
    updateAvailable, originalListingUrl, activePendingUpdate,
    resetConfirmOpen: resetConfirmOpen && !isLegacyUnpinned,
    conflictDialogOpen: conflictDialogOpen && !isLegacyUnpinned,
    handleResetOpenChange, handleConflictOpenChange, handleToggleAutoUpdate,
    handleStartUpdate, handleApplyResolvedUpdate, handleResetToUpstream,
  }
}
