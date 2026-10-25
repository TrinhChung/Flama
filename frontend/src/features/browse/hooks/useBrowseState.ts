import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useBootstrap } from '@/shared/api/bootstrap'
import { useBrowseFilters } from './useBrowseFilters'
import { useBrowseData } from './useBrowseData'
import { useBrowseSelection } from './useBrowseSelection'
import { useBrowseEditor } from './useBrowseEditor'
import { useBrowseBatchActions } from './useBrowseBatchActions'
import { useBrowseToolDialogs } from './useBrowseToolDialogs'
import { useBrowseTts } from './useBrowseTts'

/** Compose Browse workflows while keeping their state and effects with their owners. */
export function useBrowseState() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const urlDeckId = searchParams.get('deck_id')
  const urlCardId = searchParams.get('note_id') || searchParams.get('card_id')
  const queryClient = useQueryClient()
  const bootstrapQuery = useBootstrap()
  const isAdmin = Boolean(bootstrapQuery.data?.user?.is_admin)
  const filters = useBrowseFilters()
  const data = useBrowseData(filters)
  const selection = useBrowseSelection(data.cards)
  const editor = useBrowseEditor({ urlDeckId, urlCardId, filters, data, selection })
  const batch = useBrowseBatchActions({ data, editor, selection })
  const dialogs = useBrowseToolDialogs()
  const tts = useBrowseTts({ data, editor, selection, dialogs })
  const { selectedNoteIdsRef: _selectedNoteIdsRef, ...publicSelection } = selection
  return { navigate, urlDeckId, urlCardId, queryClient, isAdmin,
    ...filters, ...data, ...publicSelection, ...editor, ...batch, ...dialogs, ...tts }
}
