import '@/shared/config/i18n'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  AlertCircle,
  ArrowLeft,
  FileQuestion,
  Home,
  Layers,
  RotateCw,
  ShieldAlert,
  ShoppingBag,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ApiError } from '@/shared/api/client'

type StudyScopeErrorCardProps = {
  error: unknown
  deckName?: string | null
  deckId?: string | null
  onRetry?: () => void
}

type ErrorDetails = {
  deck_id?: number | string
  deck_name?: string
  marketplace_url?: string
  marketplace_item_id?: string
}

export function StudyScopeErrorCard({
  error,
  deckName,
  deckId,
  onRetry,
}: StudyScopeErrorCardProps) {
  const { t } = useTranslation('study')
  const isApiError = error instanceof ApiError
  const errorCode = isApiError ? error.code : ''
  const errorStatus = isApiError ? error.status : 0
  const details = (isApiError && error.details && typeof error.details === 'object'
    ? error.details as ErrorDetails
    : {})

  const isAccessDenied = errorCode === 'DECK_ACCESS_DENIED' || errorStatus === 403
  const isDeckNotFound = errorCode === 'DECK_NOT_FOUND' || (
    errorStatus === 404 && errorCode !== 'NO_STUDY_CARDS' && errorCode !== 'NOTE_TYPE_NOT_FOUND'
  )
  const isNoCards = errorCode === 'NO_STUDY_CARDS'
  const marketplaceUrl = details.marketplace_url || '/marketplace/decks'

  if (isAccessDenied) {
    return (
      <div className="w-full max-w-xl mx-auto py-6 px-4">
        <div className="rounded-3xl border border-amber-200/50 dark:border-amber-900/40 bg-card/90 backdrop-blur-md p-6 sm:p-8 space-y-6 text-center shadow-2xl shadow-amber-500/5">
          <div className="inline-flex items-center justify-center size-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-600 dark:text-amber-400 mx-auto">
            <ShieldAlert className="size-6" />
          </div>

          <div className="space-y-2">
            <div className="text-xs font-medium text-muted-foreground">
              {details.deck_name || deckName || (deckId ? `Deck #${deckId}` : t('page.session_title'))}
            </div>
            <h2 className="text-2xl font-bold text-foreground tracking-tight">
              {t('scope_error.unauthorized_title')}
            </h2>
            <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
              {t('scope_error.unauthorized_desc')}
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <Button asChild className="w-full sm:w-auto">
              <Link to={marketplaceUrl}>
                <ShoppingBag className="mr-2 size-4" />
                {t('scope_error.explore_market')}
              </Link>
            </Button>
            <Button asChild variant="outline" className="w-full sm:w-auto">
              <Link to="/dashboard">
                <Home className="mr-2 size-4" />
                {t('scope_error.back_to_dashboard')}
              </Link>
            </Button>
          </div>
        </div>
      </div>
    )
  }

  if (isDeckNotFound) {
    return (
      <div className="w-full max-w-xl mx-auto py-6 px-4">
        <div className="rounded-3xl border border-border/40 bg-card/90 backdrop-blur-md p-6 sm:p-8 space-y-6 text-center shadow-2xl shadow-primary/5 dark:shadow-none">
          <div className="inline-flex items-center justify-center size-12 rounded-2xl bg-muted border border-border/40 text-muted-foreground mx-auto">
            <FileQuestion className="size-6" />
          </div>

          <div className="space-y-2">
            <div className="text-xs font-medium text-muted-foreground">
              {deckId ? `Deck #${deckId}` : t('page.session_title')}
            </div>
            <h2 className="text-2xl font-bold text-foreground tracking-tight">
              {t('scope_error.not_found_title')}
            </h2>
            <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
              {t('scope_error.not_found_desc')}
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <Button asChild className="w-full sm:w-auto">
              <Link to="/dashboard">
                <Home className="mr-2 size-4" />
                {t('scope_error.back_to_dashboard')}
              </Link>
            </Button>
            <Button asChild variant="outline" className="w-full sm:w-auto">
              <Link to="/marketplace/decks">
                <ShoppingBag className="mr-2 size-4" />
                {t('scope_error.explore_market')}
              </Link>
            </Button>
          </div>
        </div>
      </div>
    )
  }

  if (isNoCards) {
    return (
      <div className="w-full max-w-xl mx-auto py-6 px-4">
        <div className="rounded-3xl border border-border/40 bg-card/90 backdrop-blur-md p-6 sm:p-8 space-y-6 text-center shadow-2xl shadow-primary/5 dark:shadow-none">
          <div className="inline-flex items-center justify-center size-12 rounded-2xl bg-muted border border-border/40 text-muted-foreground mx-auto">
            <Layers className="size-6" />
          </div>

          <div className="space-y-2">
            <div className="text-xs font-medium text-muted-foreground">
              {deckName || (deckId ? `Deck #${deckId}` : t('page.session_title'))}
            </div>
            <h2 className="text-2xl font-bold text-foreground tracking-tight">
              {t('scope_error.empty_deck_title')}
            </h2>
            <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
              {t('scope_error.empty_deck_desc')}
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <Button asChild className="w-full sm:w-auto">
              <Link to="/dashboard">
                <Home className="mr-2 size-4" />
                {t('scope_error.back_to_dashboard')}
              </Link>
            </Button>
            {deckId ? (
              <Button asChild variant="outline" className="w-full sm:w-auto">
                <Link to={`/browse?deck_id=${deckId}`}>
                  {t('scope_error.manage_cards')}
                </Link>
              </Button>
            ) : null}
          </div>
        </div>
      </div>
    )
  }

  // Generic fallback error
  const errorMessage = error instanceof Error
    ? error.message
    : (typeof error === 'string' ? error : t('scope_error.load_failed_default'))

  return (
    <div className="w-full max-w-xl mx-auto py-6 px-4">
      <div className="rounded-3xl border border-destructive/25 bg-card/90 backdrop-blur-md p-6 sm:p-8 space-y-6 text-center shadow-2xl shadow-destructive/5">
        <div className="inline-flex items-center justify-center size-12 rounded-2xl bg-destructive/10 border border-destructive/20 text-destructive mx-auto">
          <AlertCircle className="size-6" />
        </div>

        <div className="space-y-2">
          <div className="text-xs font-medium text-muted-foreground">
            {deckName || (deckId ? `Deck #${deckId}` : t('page.session_title'))}
          </div>
          <h2 className="text-2xl font-bold text-foreground tracking-tight">
            {t('scope_error.load_failed_title')}
          </h2>
          <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
            {errorMessage}
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          {onRetry ? (
            <Button type="button" onClick={onRetry} className="w-full sm:w-auto">
              <RotateCw className="mr-2 size-4" />
              {t('scope_error.retry')}
            </Button>
          ) : null}
          <Button asChild variant="outline" className="w-full sm:w-auto">
            <Link to="/dashboard">
              <ArrowLeft className="mr-2 size-4" />
              {t('scope_error.back_to_dashboard')}
            </Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
