import { ShieldCheck } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Page, PageHeader } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'

type TtsProvider = {
  id: number
  provider_name: string
  provider_type: string
  base_url: string | null
  requires_api_key: boolean
  is_active: boolean
  shared_config: Record<string, unknown>
  provider_config: Record<string, unknown>
  default_settings: Record<string, unknown>
}
function AdminHeader({
  title,
  description,
}: {
  title: string
  description?: string
}) {
  return (
    <div className="space-y-3">
      <Badge variant="destructive" className="gap-1 font-semibold">
        <ShieldCheck className="size-3.5" /> Admin
      </Badge>
      <PageHeader title={title} description={description} />
    </div>
  )
}

export function AdminTtsPage() {
  const queryClient = useQueryClient()
  const queryKey = ['admin', 'tts-providers'] as const
  const query = useQuery({
    queryKey,
    queryFn: () =>
      appApi.get<{ items: TtsProvider[] }>('/admin/tts-providers'),
  })
  const mutation = useMutation({
    mutationFn: ({
      provider,
      isActive,
    }: {
      provider: TtsProvider
      isActive: boolean
    }) =>
      appApi.mutate(`/admin/tts-providers/${provider.id}`, 'PUT', {
        ...provider,
        is_active: isActive,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey })
      toast.success('Đã cập nhật TTS provider.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  if (query.isPending) return <PageLoading label="Đang tải TTS provider…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page>
      <AdminHeader
        title="TTS Provider"
        description="Cấu hình provider dùng chung cho tài khoản người học."
      />
      {!query.data.items.length ? (
        <EmptyState title="Chưa có provider" description="Chưa có TTS provider nào trong hệ thống." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {query.data.items.map((provider) => (
            <Card key={provider.id}>
              <CardHeader>
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <CardTitle>{provider.provider_name}</CardTitle>
                    <CardDescription>{provider.provider_type}</CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch
                      id={`provider-${provider.id}`}
                      checked={provider.is_active}
                      disabled={mutation.isPending}
                      onCheckedChange={(isActive) =>
                        mutation.mutate({ provider, isActive })
                      }
                    />
                    <Label htmlFor={`provider-${provider.id}`}>
                      {provider.is_active ? 'Đang bật' : 'Đang tắt'}
                    </Label>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div>
                  <p className="text-muted-foreground">Base URL</p>
                  <p className="break-all font-mono text-xs">
                    {provider.base_url || 'Không cấu hình'}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Badge variant="outline">
                    {provider.requires_api_key ? 'Cần API key' : 'Không cần API key'}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </Page>
  )
}

export { AdminTicketsPage } from './AdminTicketsPage'
export { AdminTicketDetailPage } from './AdminTicketDetailPage'
