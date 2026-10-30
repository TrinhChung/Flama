import { useParams } from 'react-router-dom'
import { BaseOverrideComparisonView, InstalledDeckUpdateLegacyPage, useInstalledDeckContentModel } from '@/features/deck-collaboration'
import { Page } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'

export function InstalledDeckUpdatePage() {
  const { installId = '', releaseId } = useParams<{ installId: string; releaseId: string }>()
  const contentModel = useInstalledDeckContentModel(installId)
  if (!installId) return <Page><PageError error={new Error('Thiếu mã bản cài.')} /></Page>
  if (contentModel.isPending) return <PageLoading label="Đang tải bộ thẻ…" />
  if (contentModel.error) return <Page><PageError error={contentModel.error} /></Page>
  if (contentModel.data.content_model === 'published_base') return <BaseOverrideComparisonView key={installId} installId={installId} />
  if (!releaseId) return <Page><PageError error={new Error('Bộ thẻ này chưa hỗ trợ so sánh phần sửa riêng.')} /></Page>
  return <InstalledDeckUpdateLegacyPage />
}
