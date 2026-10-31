import { Navigate, useParams } from 'react-router-dom'
import { BaseOverrideComparisonView } from '@/features/deck-collaboration'
import { Page } from '@/shared/components/Page'
import { PageError } from '@/shared/components/PageState'

export function InstalledDeckComparisonPage() {
  const { installId = '', releaseId } = useParams<{ installId: string; releaseId: string }>()
  if (!installId) return <Page><PageError error={new Error('Thiếu mã bản cài.')} /></Page>
  if (releaseId) return <Navigate replace to={`/installed-decks/${encodeURIComponent(installId)}/comparison`} />
  return <BaseOverrideComparisonView key={installId} installId={installId} />
}
