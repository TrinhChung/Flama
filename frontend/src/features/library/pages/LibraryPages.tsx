import { ArrowRight } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Page, PageHeader } from '@/shared/components/Page'
import {
  EmptyState,
  PageError,
  PageLoading,
} from '@/shared/components/PageState'

type NoteTypeItem = {
  id: string
  name: string
  description: string | null
  field_defs?: unknown[]
  templates?: unknown[]
  updated_at: string | null
}

type MarketplaceAuthor = {
  username?: string
  account_name?: string
}

type InstalledDeckItem = {
  id: string
  title: string
  description: string | null
  author: MarketplaceAuthor | null
  installed_deck_id: number | null
  install_bucket: 'using_now' | 'installed' | 'owned'
  last_sync_status: string | null
}

function formatUpdatedAt(value: string | null) {
  if (!value) return 'Chưa có thời gian cập nhật'
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function NoteTypesPage() {
  const query = useQuery({
    queryKey: ['note-types'],
    queryFn: () => appApi.get<{ items: NoteTypeItem[] }>('/note-types'),
  })

  if (query.isPending) return <PageLoading label="Đang tải loại thẻ…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page>
      <PageHeader
        title="Loại thẻ"
        description="Quản lý field, template và cách render flashcard."
      />
      {!query.data.items.length ? (
        <EmptyState
          title="Chưa có loại thẻ"
          description="Tạo note type đầu tiên hoặc cài một mẫu từ marketplace."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {query.data.items.map((item) => (
            <Card key={item.id}>
              <CardHeader>
                <div className="mb-2">
                  <Badge variant="secondary">
                    {item.templates?.length || 0} template
                  </Badge>
                </div>
                <CardTitle>{item.name}</CardTitle>
                <CardDescription>
                  {item.field_defs?.length || 0} field
                  {item.description ? ` · ${item.description}` : ''}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  Cập nhật {formatUpdatedAt(item.updated_at)}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </Page>
  )
}

export function InstalledDecksPage() {
  const query = useQuery({
    queryKey: ['installed-decks'],
    queryFn: () =>
      appApi.get<{ items: InstalledDeckItem[] }>(
        '/marketplace/installed-decks',
      ),
  })

  if (query.isPending) return <PageLoading label="Đang tải deck đã cài…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page>
      <PageHeader
        title="Deck đã cài"
        description="Theo dõi nguồn và trạng thái của các logical overlay install."
        actions={
          <Button asChild>
            <Link to="/marketplace/decks">Khám phá deck<ArrowRight /></Link>
          </Button>
        }
      />
      {!query.data.items.length ? (
        <EmptyState
          title="Chưa cài deck nào"
          description="Khám phá marketplace và cài một deck để bắt đầu học."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {query.data.items.map((item) => (
            <Card key={item.id}>
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <Badge variant={item.install_bucket === 'using_now' ? 'default' : 'secondary'}>
                    {item.install_bucket === 'using_now'
                      ? 'Đang sử dụng'
                      : item.install_bucket === 'owned'
                        ? 'Deck của bạn'
                        : 'Đã cài'}
                  </Badge>
                  {item.last_sync_status ? (
                    <span className="text-xs text-muted-foreground">
                      {item.last_sync_status}
                    </span>
                  ) : null}
                </div>
                <CardTitle>{item.title}</CardTitle>
                <CardDescription>
                  bởi {item.author?.account_name || item.author?.username || 'Cộng đồng'}
                </CardDescription>
              </CardHeader>
              {item.description ? (
                <CardContent>
                  <p className="line-clamp-3 text-sm text-muted-foreground">
                    {item.description}
                  </p>
                </CardContent>
              ) : null}
              {item.installed_deck_id ? (
                <CardFooter>
                  <Button className="w-full" variant="outline" asChild>
                    <Link to={`/study?deck_id=${item.installed_deck_id}`}>
                      Bắt đầu học
                    </Link>
                  </Button>
                </CardFooter>
              ) : null}
            </Card>
          ))}
        </div>
      )}
    </Page>
  )
}
