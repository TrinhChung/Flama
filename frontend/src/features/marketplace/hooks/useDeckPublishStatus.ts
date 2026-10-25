import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { updateDeckPublishStatus, type DeckPublishStatus } from '../api/deckListingApi'

/** Creator withdraw/republish of a marketplace deck listing. */
export function useDeckPublishStatus(deckItemId: string | undefined) {
  const { t } = useTranslation('marketplace')
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (newStatus: DeckPublishStatus) => updateDeckPublishStatus(deckItemId!, newStatus),
    onSuccess: (_, newStatus) => {
      queryClient.invalidateQueries({ queryKey: ['shared-deck-detail', deckItemId] })
      toast.success(
        newStatus === 'private'
          ? t('detail.toast_revoked', 'Đã thu hồi bộ deck khỏi Marketplace.')
          : t('detail.toast_republished', 'Đã xuất bản lại bộ deck lên Marketplace.')
      )
    },
    onError: (err: any) => {
      toast.error(err?.message || t('common.error', 'Không thể cập nhật trạng thái xuất bản.'))
    },
  })
}
