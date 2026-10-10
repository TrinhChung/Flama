import { useTranslation } from 'react-i18next'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import { AuthorPublicationView } from './AuthorPublicationView'
import { SubscriberUpdateView } from './SubscriberUpdateView'

export interface TemplateDistributionPanelProps {
  templateId: string
  origin?: string | null
  currentVersionId?: string | null
  open?: boolean
  onOpenChange?: (open: boolean) => void
  onSourceChanged?: () => void
  className?: string
}

export function TemplateDistributionPanel({
  templateId,
  origin,
  currentVersionId,
  open,
  onOpenChange,
  onSourceChanged,
  className,
}: TemplateDistributionPanelProps) {
  const { t } = useTranslation('card_templates')

  const isSubscriber = origin === 'market_copy'

  const bodyContent = isSubscriber ? (
    <SubscriberUpdateView
      templateId={templateId}
      currentVersionId={currentVersionId}
      onSourceChanged={onSourceChanged}
    />
  ) : (
    <AuthorPublicationView
      templateId={templateId}
      currentVersionId={currentVersionId}
      onSourceChanged={onSourceChanged}
    />
  )

  // Sheet drawer mode if open/onOpenChange are passed
  if (open !== undefined && onOpenChange !== undefined) {
    return (
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent className="w-full sm:max-w-xl overflow-y-auto">
          <SheetHeader className="pb-2">
            <SheetTitle>{t('distribution.title')}</SheetTitle>
            <SheetDescription>{t('distribution.description')}</SheetDescription>
          </SheetHeader>
          <div className="py-2">{bodyContent}</div>
        </SheetContent>
      </Sheet>
    )
  }

  // Inline container mode
  return <div className={cn('space-y-6', className)}>{bodyContent}</div>
}
