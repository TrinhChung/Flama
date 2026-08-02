import { useState } from 'react'
import { Check, Copy, KeyRound, RefreshCw, ShieldAlert, Trash2 } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { FLAMA_CONNECT_URL } from '@/config/env'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Page, PageHeader } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'

type IntegrationToken = {
  id: number
  name: string
  token_prefix: string
  scopes: string[]
  status: 'active' | 'expired' | 'revoked' | string
  expires_at: string | null
  last_used_at: string | null
  created_at: string
  token?: string
}

type TokensResponse = {
  items: IntegrationToken[]
  policy: {
    default_expiry_days: number
    allowed_expiry_days: number[]
    allow_no_expiry: boolean
  }
}

function displayDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : 'Không hết hạn'
}

export function YomitanTokensPage() {
  const queryClient = useQueryClient()
  const queryKey = ['integration-tokens'] as const
  const [name, setName] = useState('Yomitan - PC cá nhân')
  const [expiry, setExpiry] = useState('180')
  const [issued, setIssued] = useState<IntegrationToken | null>(null)
  const [copied, setCopied] = useState<string | null>(null)
  const issuedConnectUrl = issued?.token
    ? `${FLAMA_CONNECT_URL.replace(/\/+$/, '')}/${encodeURIComponent(issued.token)}`
    : null

  const query = useQuery({
    queryKey,
    queryFn: () => appApi.get<TokensResponse>('/integration-tokens'),
  })

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey })
  }

  const createMutation = useMutation({
    mutationFn: () => appApi.mutate<{ item: IntegrationToken }>('/integration-tokens', 'POST', {
      name: name.trim(),
      expires_in_days: expiry === 'none' ? null : Number(expiry),
    }),
    onSuccess: async ({ item }) => {
      setIssued(item)
      await refresh()
      toast.success('Đã tạo token Flama Connect.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const revokeMutation = useMutation({
    mutationFn: (id: number) => appApi.mutate(`/integration-tokens/${id}`, 'DELETE'),
    onSuccess: async () => {
      await refresh()
      toast.success('Token đã được thu hồi ngay lập tức.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const rotateMutation = useMutation({
    mutationFn: (id: number) => appApi.mutate<{ item: IntegrationToken }>(`/integration-tokens/${id}/rotate`, 'POST', {
      expires_in_days: expiry === 'none' ? null : Number(expiry),
    }),
    onSuccess: async ({ item }) => {
      setIssued(item)
      await refresh()
      toast.success('Đã thu hồi token cũ và tạo token mới.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const copy = async (label: string, value: string) => {
    await navigator.clipboard.writeText(value)
    setCopied(label)
    window.setTimeout(() => setCopied(null), 1800)
    toast.success('Đã sao chép.')
  }

  if (query.isPending) return <PageLoading label="Đang tải token Yomitan…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page>
      <PageHeader
        title="Kết nối Yomitan"
        description="Tạo API token riêng để Yomitan gửi từ và câu ví dụ vào Flama. Token này không phải token đăng nhập."
      />

      <Card>
        <CardHeader><CardTitle>Cấu hình kết nối</CardTitle></CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-[1fr_220px_auto] md:items-end">
          <div className="space-y-2">
            <Label htmlFor="connect-token-name">Tên thiết bị</Label>
            <Input id="connect-token-name" value={name} maxLength={120} onChange={(event) => setName(event.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="connect-token-expiry">Thời hạn token</Label>
            <NativeSelect id="connect-token-expiry" className="w-full" value={expiry} onChange={(event) => setExpiry(event.target.value)}>
              <NativeSelectOption value="30">30 ngày</NativeSelectOption>
              <NativeSelectOption value="90">90 ngày</NativeSelectOption>
              <NativeSelectOption value="180">180 ngày (mặc định)</NativeSelectOption>
              <NativeSelectOption value="365">365 ngày</NativeSelectOption>
              <NativeSelectOption value="none">Không hết hạn</NativeSelectOption>
            </NativeSelect>
          </div>
          <Button disabled={!name.trim() || createMutation.isPending} onClick={() => createMutation.mutate()}>
            <KeyRound className="mr-2 size-4" /> Tạo token
          </Button>
        </CardContent>
      </Card>

      <Alert>
        <ShieldAlert className="size-4" />
        <AlertTitle>Cấu hình trong Yomitan</AlertTitle>
        <AlertDescription>
          Tạo token rồi dán toàn bộ URL được cấp vào ô Server URL của Yomitan; không cần ô API key riêng. URL này chứa token nên hãy giữ bí mật. Flama Connect nhận audio MP3 tối đa 1 MB; ảnh và video hiện chưa được hỗ trợ.
        </AlertDescription>
      </Alert>

      {issuedConnectUrl ? (
        <Alert className="border-amber-500/50 bg-amber-50 dark:bg-amber-950/30">
          <ShieldAlert className="size-5 text-amber-600" />
          <AlertTitle>Sao chép URL này ngay — Flama sẽ không hiển thị lại URL đầy đủ.</AlertTitle>
          <AlertDescription className="mt-3 flex items-center gap-2">
            <code className="min-w-0 flex-1 break-all rounded-md border bg-background p-3 text-xs">{issuedConnectUrl}</code>
            <Button variant="outline" onClick={() => copy('connect-url', issuedConnectUrl)}>
              {copied === 'connect-url' ? <Check className="size-4" /> : <Copy className="size-4" />}
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader><CardTitle>Token đã tạo</CardTitle></CardHeader>
        <CardContent>
          {!query.data.items.length ? (
            <EmptyState title="Chưa có token Yomitan" description="Tạo token đầu tiên để kết nối Yomitan với tài khoản này." />
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader><TableRow><TableHead>Tên</TableHead><TableHead>Trạng thái</TableHead><TableHead>Hết hạn</TableHead><TableHead>Dùng gần nhất</TableHead><TableHead className="text-right">Thao tác</TableHead></TableRow></TableHeader>
                <TableBody>
                  {query.data.items.map((token) => (
                    <TableRow key={token.id}>
                      <TableCell><div className="font-medium">{token.name}</div><code className="text-xs text-muted-foreground">{token.token_prefix}…</code></TableCell>
                      <TableCell><Badge variant={token.status === 'active' ? 'default' : token.status === 'revoked' ? 'destructive' : 'secondary'}>{token.status}</Badge></TableCell>
                      <TableCell className="text-xs">{displayDate(token.expires_at)}</TableCell>
                      <TableCell className="text-xs">{token.last_used_at ? displayDate(token.last_used_at) : 'Chưa sử dụng'}</TableCell>
                      <TableCell className="text-right">
                        {token.status === 'active' ? <>
                          <Button size="sm" variant="ghost" disabled={rotateMutation.isPending} onClick={() => window.confirm('Thu hồi token cũ và tạo token mới?') && rotateMutation.mutate(token.id)}><RefreshCw className="mr-1 size-3.5" /> Tạo lại</Button>
                          <Button size="sm" variant="ghost" className="text-destructive" disabled={revokeMutation.isPending} onClick={() => window.confirm('Thu hồi token này ngay?') && revokeMutation.mutate(token.id)}><Trash2 className="mr-1 size-3.5" /> Thu hồi</Button>
                        </> : null}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </Page>
  )
}
