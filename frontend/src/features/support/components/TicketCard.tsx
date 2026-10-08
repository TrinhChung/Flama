import { Check, Copy, ExternalLink, Eye, Image as ImageIcon, MessageSquare } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import type { TicketItem } from '../types'
import { formatRelativeTime, getCategories, getStatusMap } from '../utils/supportHelpers'

interface TicketCardProps {
  ticket: TicketItem
  isCopied: boolean
  onCopyCode: (e: React.MouseEvent, code: string) => void
}

export function TicketCard({ ticket, isCopied, onCopyCode }: TicketCardProps) {
  const { t, i18n } = useTranslation('support')
  const navigate = useNavigate()

  const statusMap = getStatusMap(t)
  const statusInfo = statusMap[ticket.status] || statusMap.open
  const StatusIcon = statusInfo.icon

  const categories = getCategories(t)
  const catCfg = categories.find((c) => c.key === ticket.category) || categories[3]
  const CatIcon = catCfg.icon

  return (
    <Card
      className="shadow-2xs hover:shadow-md hover:border-primary/60 transition-all cursor-pointer border-border/80 bg-card rounded-xl group"
      onClick={() => navigate(`/tickets/${ticket.id}`)}
    >
      <CardContent className="p-4 sm:p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-2 max-w-xl">
          <div className="flex flex-wrap items-center gap-2">
            {/* Ticket Code with Copy Button */}
            <div className="flex items-center gap-1 font-mono font-bold text-xs px-2.5 py-0.5 bg-primary/10 text-primary rounded-full">
              <span>{ticket.ticket_code}</span>
              <button
                type="button"
                onClick={(e) => onCopyCode(e, ticket.ticket_code)}
                className="p-0.5 hover:bg-primary/20 rounded text-primary transition-colors cursor-pointer"
                title={t('feedback.copy_code_tooltip')}
              >
                {isCopied ? <Check className="size-3 text-emerald-600" /> : <Copy className="size-3" />}
              </button>
            </div>

            {/* Category Badge */}
            <Badge
              variant="outline"
              className="px-2 py-0.5 text-[11px] gap-1 font-medium rounded-full bg-card border-border/80 text-foreground"
            >
              <CatIcon className={`size-3 ${catCfg.color}`} /> {catCfg.title}
            </Badge>

            {/* Replies Count Badge */}
            {ticket.replies_count && ticket.replies_count > 0 ? (
              <Badge className="px-2 py-0.5 text-[10px] gap-1 rounded-full bg-blue-600 text-white font-bold">
                <MessageSquare className="size-3" />{' '}
                {t('feedback.replies_count', { count: ticket.replies_count })}
              </Badge>
            ) : null}
          </div>

          {/* Title */}
          <h3 className="font-bold text-sm sm:text-base text-foreground group-hover:text-primary transition-colors">
            {ticket.title}
          </h3>

          {/* Description snippet */}
          <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
            {ticket.description}
          </p>

          {/* Metadata Row */}
          <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground pt-0.5">
            {ticket.screen_name && (
              <span className="flex items-center gap-1 font-medium text-foreground">
                <ExternalLink className="size-3 text-primary" /> {ticket.screen_name}
              </span>
            )}
            <span>•</span>
            <span
              title={new Date(ticket.created_at).toLocaleString(
                i18n.language === 'en' ? 'en-US' : 'vi-VN'
              )}
            >
              {t('relative_time.sent_at', {
                time: formatRelativeTime(
                  ticket.created_at,
                  t,
                  i18n.language === 'en' ? 'en-US' : 'vi-VN'
                ),
              })}
            </span>
            {ticket.attachment_urls && ticket.attachment_urls.length > 0 && (
              <>
                <span>•</span>
                <span className="flex items-center gap-1 text-blue-600 dark:text-blue-400 font-medium">
                  <ImageIcon className="size-3" />{' '}
                  {t('feedback.images_count', {
                    count: ticket.attachment_urls.length,
                  })}
                </span>
              </>
            )}
          </div>
        </div>

        {/* Right Status & Action */}
        <div className="flex items-center gap-3">
          <Badge
            className={`px-3 py-1 text-xs gap-1.5 rounded-full font-semibold ${statusInfo.badge}`}
          >
            <StatusIcon className="size-3.5" /> {statusInfo.label}
          </Badge>
          <Button
            size="sm"
            variant="ghost"
            className="rounded-full px-3 text-xs gap-1 group-hover:bg-primary group-hover:text-primary-foreground transition-all"
          >
            <Eye className="size-3.5" /> {t('feedback.view_details')}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
