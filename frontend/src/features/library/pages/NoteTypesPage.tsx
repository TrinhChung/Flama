import { Layers } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Page, PageHeader } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'

type NoteTypeItem = {
  id: string
  name: string
  description: string | null
  field_defs?: unknown[]
  templates?: unknown[]
  updated_at: string | null
}

function formatUpdatedAt(value: string | null, fallbackText: string) {
  if (!value) return fallbackText
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function NoteTypesPage() {
  const { t } = useTranslation('library')
  const query = useQuery({
    queryKey: ['note-types'],
    queryFn: () => appApi.get<{ items: NoteTypeItem[] }>('/note-types'),
  })

  if (query.isPending) {
    return <PageLoading label={t('note_types_page.loading', { defaultValue: 'Đang tải loại thẻ…' })} />
  }

  if (query.error) {
    return (
      <Page>
        <PageError error={query.error} />
      </Page>
    )
  }

  return (
    <Page className="relative min-h-screen px-2.5 sm:px-6 py-4 sm:py-6">
      <AmbientBackground />
      <PageHeader
        title={t('note_types_page.title', { defaultValue: 'Loại thẻ' })}
        description={t('note_types_page.description', { defaultValue: 'Quản lý field, template và quy cách hiển thị flashcard.' })}
      />
      {!query.data?.items.length ? (
        <EmptyState
          title={t('note_types_page.empty_title', { defaultValue: 'Chưa có loại thẻ' })}
          description={t('note_types_page.empty_desc', { defaultValue: 'Tạo note type đầu tiên hoặc cài một mẫu từ marketplace.' })}
        />
      ) : (
        <div className="grid gap-3 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {query.data.items.map((item) => (
            <Card
              key={item.id}
              className="group relative flex flex-col justify-between overflow-hidden border-border/80 bg-card p-4 sm:p-5 transition-all duration-200 hover:-translate-y-1 hover:border-primary/50 hover:shadow-md rounded-2xl"
            >
              <div className="flex flex-col flex-1 space-y-2">
                <div className="flex items-center justify-between gap-1.5 mb-1">
                  <Badge variant="secondary" className="px-2 py-0.5 text-xs font-semibold rounded-md">
                    <Layers className="mr-1 size-3 text-primary" />
                    {t('note_types_page.templates_count', { count: item.templates?.length || 0, defaultValue: `${item.templates?.length || 0} template` })}
                  </Badge>

                  <Badge variant="outline" className="px-2 py-0.5 text-xs font-semibold rounded-md">
                    {t('note_types_page.fields_count', { count: item.field_defs?.length || 0, defaultValue: `${item.field_defs?.length || 0} field` })}
                  </Badge>
                </div>

                <h3 className="text-sm sm:text-base font-bold tracking-tight text-foreground line-clamp-1 group-hover:text-primary transition-colors leading-snug">
                  {item.name}
                </h3>

                <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground font-normal">
                  {item.description || t('note_types_page.no_desc', { defaultValue: 'Chưa có mô tả cho loại thẻ này.' })}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-border/60 text-xs text-muted-foreground">
                {t('note_types_page.updated_at', {
                  date: formatUpdatedAt(item.updated_at, t('note_types_page.no_updated_at', { defaultValue: 'Chưa có thời gian cập nhật' })),
                  defaultValue: `Cập nhật ${formatUpdatedAt(item.updated_at, 'Chưa có thời gian cập nhật')}`,
                })}
              </div>
            </Card>
          ))}
        </div>
      )}
    </Page>
  )
}
