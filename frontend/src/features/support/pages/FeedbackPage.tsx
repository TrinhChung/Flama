import { useEffect, useState } from 'react'
import {
  MessageSquareHeart,
  Plus,
  Ticket,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useLocation, useSearchParams } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Page } from '@/shared/components/Page'
import { FeedbackCreateTab } from '../components/FeedbackCreateTab'
import { MyTicketsTab } from '../components/MyTicketsTab'
import { useFeedbackForm } from '../hooks/useFeedbackForm'
import { useMyTickets } from '../hooks/useMyTickets'

export function FeedbackPage() {
  const { t } = useTranslation('support')
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const isMyTicketsRoute =
    location.pathname === '/tickets' || searchParams.get('tab') === 'my-tickets'

  const [activeTab, setActiveTab] = useState<'create' | 'my-tickets'>(
    isMyTicketsRoute ? 'my-tickets' : 'create'
  )
  const [previewImage, setPreviewImage] = useState<string | null>(null)

  useEffect(() => {
    if (location.pathname === '/tickets' || searchParams.get('tab') === 'my-tickets') {
      setActiveTab('my-tickets')
    }
  }, [location.pathname, searchParams])

  const feedbackForm = useFeedbackForm(activeTab, () => {
    setActiveTab('my-tickets')
  })

  const myTickets = useMyTickets(activeTab === 'my-tickets')

  return (
    <Page className="max-w-4xl mx-auto space-y-6 py-4 pb-20">
      {/* Hero Header */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className="px-3 py-1 text-xs font-semibold rounded-full bg-card border-border/80 text-foreground"
          >
            {t('feedback.badge')}
          </Badge>
        </div>

        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground flex items-center gap-2.5">
          <MessageSquareHeart className="size-7 text-primary shrink-0" />
          <span>{t('feedback.title')}</span>
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed max-w-2xl">
          {t('feedback.description')}
        </p>
      </div>

      {/* Tabs Navigation */}
      <div className="flex items-center justify-between border-b pb-3">
        <Tabs value={activeTab} onValueChange={(val) => setActiveTab(val as any)}>
          <TabsList className="bg-card p-1 rounded-full border border-border/80 shadow-2xs">
            <TabsTrigger
              value="create"
              className="rounded-full text-xs font-bold gap-2 px-5 py-2 transition-all data-[state=active]:!bg-orange-500 data-[state=active]:!text-white data-[state=active]:!border-transparent data-[state=active]:shadow-sm hover:text-foreground cursor-pointer"
            >
              <Plus className="size-3.5" /> {t('feedback.tabs.create')}
            </TabsTrigger>

            <TabsTrigger
              value="my-tickets"
              className="rounded-full text-xs font-bold gap-2 px-5 py-2 transition-all data-[state=active]:!bg-orange-500 data-[state=active]:!text-white data-[state=active]:!border-transparent data-[state=active]:shadow-sm hover:text-foreground cursor-pointer"
            >
              <Ticket className="size-3.5" /> {t('feedback.tabs.my_tickets')}
              {myTickets.myTicketsQuery.data?.items &&
                myTickets.myTicketsQuery.data.items.length > 0 && (
                  <span
                    className={`ml-1 px-1.5 py-0.5 text-[10px] font-bold rounded-full transition-colors ${
                      activeTab === 'my-tickets'
                        ? 'bg-white/25 text-white'
                        : 'bg-orange-500/15 text-orange-600 dark:text-orange-400'
                    }`}
                  >
                    {myTickets.myTicketsQuery.data.items.length}
                  </span>
                )}
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Tab Content 1: Create Ticket */}
      {activeTab === 'create' && (
        <FeedbackCreateTab
          form={feedbackForm}
          onPreviewImage={(url) => setPreviewImage(url)}
        />
      )}

      {/* Tab Content 2: My Tickets */}
      {activeTab === 'my-tickets' && (
        <MyTicketsTab
          myTickets={myTickets}
          onCreateClick={() => setActiveTab('create')}
        />
      )}

      {/* Lightbox Image Preview Modal */}
      <Dialog
        open={Boolean(previewImage)}
        onOpenChange={(open) => !open && setPreviewImage(null)}
      >
        <DialogContent className="max-w-4xl sm:max-w-4xl p-2 bg-black/95 border-none flex flex-col items-center justify-center">
          {previewImage && (
            <img
              src={previewImage}
              alt="Screenshot Preview"
              className="max-h-[85vh] object-contain rounded-xl"
            />
          )}
        </DialogContent>
      </Dialog>
    </Page>
  )
}
