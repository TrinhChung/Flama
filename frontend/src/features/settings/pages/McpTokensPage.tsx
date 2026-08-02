import { useState } from 'react'
import { Check, Copy, Key, ShieldAlert, Trash2 } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Page, PageHeader, StatCard } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'
import { useBootstrap } from '@/shared/api/bootstrap'

type McpTokenItem = {
  id: number
  status: 'active' | 'expired' | 'exhausted' | 'revoked' | string
  expires_at: string | null
  max_requests: number
  remaining_requests: number
  scopes: string[]
  last_used_at: string | null
}

type McpPolicy = {
  ttl_minutes: number
  max_requests: number
  scopes: string[]
}

type McpTokensResponse = {
  items: McpTokenItem[]
  policy: McpPolicy
}

type IssuedMcpToken = {
  token: string
  expires_at?: string
  remaining_requests?: number
  scopes?: string[]
}

export function McpTokensPage() {
  const bootstrapQuery = useBootstrap()
  const queryClient = useQueryClient()
  const [issuedToken, setIssuedToken] = useState<IssuedMcpToken | null>(null)
  const [copied, setCopied] = useState(false)
  const [revokeTargetId, setRevokeTargetId] = useState<number | null>(null)

  const isAdmin = Boolean(bootstrapQuery.data?.user?.is_admin)

  const queryKey = ['mcp-tokens'] as const
  const query = useQuery({
    queryKey,
    queryFn: () => appApi.get<McpTokensResponse>('/mcp-tokens'),
    enabled: isAdmin,
  })

  const generateMutation = useMutation({
    mutationFn: () =>
      appApi.mutate<{ item: IssuedMcpToken }>('/mcp-tokens', 'POST'),
    onSuccess: async (data) => {
      setIssuedToken(data.item)
      await queryClient.invalidateQueries({ queryKey })
      toast.success('Đã tạo MCP Token mới thành công.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const revokeMutation = useMutation({
    mutationFn: (tokenId: number) =>
      appApi.mutate(`/mcp-tokens/${tokenId}`, 'DELETE'),
    onSuccess: async () => {
      setRevokeTargetId(null)
      await queryClient.invalidateQueries({ queryKey })
      toast.success('Đã thu hồi MCP Token.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const handleCopyToken = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      toast.success('Đã sao chép Bearer token!')
      setTimeout(() => setCopied(false), 2000)
    })
  }

  if (bootstrapQuery.data && !isAdmin) {
    return (
      <Page>
        <PageError error={new Error('Chỉ quản trị viên (Admin) mới có quyền truy cập MCP Access Tokens.')} />
      </Page>
    )
  }

  if (query.isPending || bootstrapQuery.isPending) {
    return <PageLoading label="Đang tải danh sách MCP Token…" />
  }
  if (query.error) return <Page><PageError error={query.error} /></Page>
  if (!query.data) return <Page><PageError error={new Error('Không có dữ liệu MCP Token.')} /></Page>

  const { items, policy } = query.data
  const activeCount = items.filter((i) => i.status === 'active').length

  return (
    <Page>
      <PageHeader
        title="MCP Access Tokens"
        description="Tạo và quản lý Bearer token ngắn hạn kết nối MCP client bên ngoài."
        actions={
          <Button
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending}
            className="gap-2"
          >
            <Key className="size-4" />
            Tạo MCP token
          </Button>
        }
      />

      {/* Policy summary */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Chính sách TTL"
          value={`${policy.ttl_minutes} phút`}
          hint="Thời gian sống mặc định"
          tone="primary"
        />
        <StatCard
          label="Giới hạn Request"
          value={`${policy.max_requests} req`}
          hint="Tối đa trên mỗi token"
          tone="default"
        />
        <StatCard
          label="Token đang hoạt động"
          value={activeCount.toString()}
          hint="Active token"
          tone={activeCount > 0 ? 'success' : 'default'}
        />
      </div>

      {/* Newly Generated Token One-time Notice */}
      {issuedToken && (
        <Alert className="border-amber-500/50 bg-amber-50 dark:bg-amber-950/30">
          <ShieldAlert className="size-5 text-amber-600 dark:text-amber-400" />
          <AlertTitle className="font-bold text-amber-900 dark:text-amber-200">
            Sao chép token này ngay bây giờ. Nó sẽ không được hiển thị lại!
          </AlertTitle>
          <AlertDescription className="mt-2 space-y-3">
            <div className="flex items-center gap-2 rounded-md border border-amber-300 bg-white p-2.5 font-mono text-xs font-semibold text-amber-950 shadow-xs dark:border-amber-800 dark:bg-amber-900/50 dark:text-amber-100">
              <span className="flex-1 break-all">{issuedToken.token}</span>
              <Button
                size="sm"
                variant="outline"
                className="shrink-0 gap-1.5"
                onClick={() => handleCopyToken(issuedToken.token)}
              >
                {copied ? <Check className="size-4 text-emerald-600" /> : <Copy className="size-4" />}
                {copied ? 'Đã sao chép' : 'Sao chép'}
              </Button>
            </div>
            <div className="text-xs text-amber-800 dark:text-amber-300">
              Hết hạn: {issuedToken.expires_at || 'N/A'} | Scope: {(issuedToken.scopes || policy.scopes).join(', ')}
            </div>
          </AlertDescription>
        </Alert>
      )}

      {/* Token List */}
      <Card className="shadow-xs">
        <CardHeader>
          <CardTitle>Danh sách Token đã cấp</CardTitle>
        </CardHeader>
        <CardContent>
          {!items.length ? (
            <EmptyState
              title="Chưa có MCP token nào"
              description="Bấm 'Tạo MCP token' ở trên để cấp token đầu tiên cho client."
            />
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/40">
                    <TableHead>Trạng thái</TableHead>
                    <TableHead>Thời gian hết hạn</TableHead>
                    <TableHead>Request còn lại</TableHead>
                    <TableHead>Scopes</TableHead>
                    <TableHead>Sử dụng lần cuối</TableHead>
                    <TableHead className="text-right">Thao tác</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((token) => (
                    <TableRow key={token.id}>
                      <TableCell>
                        <Badge
                          variant={
                            token.status === 'active'
                              ? 'default'
                              : token.status === 'revoked'
                                ? 'destructive'
                                : 'secondary'
                          }
                          className="capitalize"
                        >
                          {token.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {token.expires_at || '—'}
                      </TableCell>
                      <TableCell className="text-sm">
                        {token.remaining_requests} / {token.max_requests}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {(token.scopes || []).map((scope) => (
                            <Badge key={scope} variant="outline" className="font-mono text-[10px]">
                              {scope}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {token.last_used_at || 'Chưa sử dụng'}
                      </TableCell>
                      <TableCell className="text-right">
                        {token.status !== 'revoked' ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-rose-600 hover:bg-rose-50 hover:text-rose-700 dark:hover:bg-rose-950/40"
                            onClick={() => setRevokeTargetId(token.id)}
                          >
                            <Trash2 className="mr-1 size-3.5" /> Thu hồi
                          </Button>
                        ) : (
                          <span className="text-xs text-muted-foreground">Đã thu hồi</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Revoke Confirmation Dialog */}
      <Dialog open={revokeTargetId !== null} onOpenChange={(open) => !open && setRevokeTargetId(null)}>
        <DialogContent className="sm:max-w-xs">
          <DialogHeader>
            <DialogTitle>Xác nhận thu hồi token</DialogTitle>
            <DialogDescription>
              Token sau khi thu hồi sẽ lập tức mất quyền truy cập vào MCP endpoint.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRevokeTargetId(null)}>
              Hủy
            </Button>
            <Button
              variant="destructive"
              disabled={revokeMutation.isPending}
              onClick={() => revokeTargetId && revokeMutation.mutate(revokeTargetId)}
            >
              Thu hồi
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Page>
  )
}
