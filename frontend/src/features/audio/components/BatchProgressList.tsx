import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { CheckCircle2, LoaderCircle, XCircle } from 'lucide-react'
import type { BatchItem } from '../hooks/useLocalAudioEngine'

interface BatchProgressListProps {
  items: BatchItem[]
}

export function BatchProgressList({ items }: BatchProgressListProps) {
  const { t } = useTranslation('audio')

  return (
    <div className="max-h-48 overflow-y-auto space-y-1.5 border rounded-xl p-2.5 bg-background">
      {items.map((item, idx) => (
        <div
          key={idx}
          className="flex items-center justify-between text-xs p-2 rounded-lg hover:bg-muted/50 border border-border/40"
        >
          <span className="font-semibold truncate max-w-[220px]">{item.word}</span>
          <div className="flex items-center gap-2">
            {item.status === 'pending' && <Badge variant="outline">{t('queue.status_pending')}</Badge>}
            {item.status === 'synthesizing' && (
              <Badge variant="secondary" className="gap-1 bg-primary/10 text-primary border-primary/20">
                <LoaderCircle className="size-3 animate-spin" /> {t('queue.status_synthesizing')}
              </Badge>
            )}
            {item.status === 'uploading' && (
              <Badge variant="secondary" className="gap-1 bg-primary/10 text-primary border-primary/20">
                <LoaderCircle className="size-3 animate-spin" /> {t('queue.status_uploading')}
              </Badge>
            )}
            {item.status === 'done' && (
              <Badge variant="default" className="bg-emerald-600 text-white gap-1">
                <CheckCircle2 className="size-3" /> {t('queue.status_completed')}
              </Badge>
            )}
            {item.status === 'skipped' && (
              <Badge variant="outline" className="text-amber-600 border-amber-300">
                {t('queue.status_skipped')}
              </Badge>
            )}
            {item.status === 'failed' && (
              <Badge variant="destructive" className="gap-1" title={item.error}>
                <XCircle className="size-3" /> {t('queue.status_failed')}
              </Badge>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
