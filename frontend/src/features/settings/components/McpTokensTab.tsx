import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { TabsContent } from '@/components/ui/tabs'
import { StatCard } from '@/shared/components/Page'
import { EmptyState } from '@/shared/components/PageState'
import {
  Check,
  Clock,
  Copy,
  Key,
  KeyRound,
  Link as LinkIcon,
  Shield,
  ShieldAlert,
  Trash2,
  Zap,
} from 'lucide-react'
import { ALL_MCP_SCOPES, type useMcpTokenCRUD } from '../hooks/useMcpTokenCRUD'

type McpTokenCrudResult = ReturnType<typeof useMcpTokenCRUD>

interface McpTokensTabProps {
  hookResult: McpTokenCrudResult
}

function displayDate(value: string | null) {
  if (!value) return 'Vĩnh viễn (Không hết hạn)'
  try {
    return new Date(value).toLocaleString('vi-VN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return value
  }
}

export function McpTokensTab({ hookResult }: McpTokensTabProps) {
  const {
    query,
    name,
    setName,
    expiry,
    setExpiry,
    selectedScopes,
    toggleScope,
    issued,
    copied,
    copy,
    issuedMcpUrl,
    revokeTargetId,
    setRevokeTargetId,
    createMutation,
    revokeMutation,
  } = hookResult

  const items = query.data?.items || []
  const activeCount = items.filter((t) => t.status === 'active').length

  return (
    <TabsContent value="tokens" className="space-y-6">
      {/* Stats row */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Token đang hoạt động"
          value={activeCount.toString()}
          hint="Đang sẵn sàng kết nối AI"
          tone={activeCount > 0 ? 'success' : 'default'}
        />
        <StatCard
          label="Thời hạn mặc định"
          value="180 ngày"
          hint="Hỗ trợ chọn từ 7 ngày đến Vĩnh viễn"
          tone="primary"
        />
        <StatCard
          label="Quyền hạn đầy đủ"
          value="4 Scopes"
          hint="Đọc Deck, Note Type, Tìm kiếm & Tạo thẻ"
          tone="default"
        />
      </div>

      {/* Quick Generate Card */}
      <Card className="shadow-2xs border-primary/20">
        <CardHeader className="p-4 sm:p-6 pb-3">
          <CardTitle className="text-base sm:text-lg font-bold flex items-center gap-2">
            <KeyRound className="size-5 text-primary shrink-0" />
            Tạo MCP Access Token mới
          </CardTitle>
          <CardDescription className="text-xs sm:text-sm">
            Mỗi AI client hoặc thiết bị (Claude Desktop, Cursor, Laptop, PC) nên tạo 1 token riêng biệt để dễ dàng quản lý.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 sm:p-6 pt-0 space-y-5">
          <div className="grid gap-4 md:grid-cols-[1fr_220px_auto] md:items-end">
            <div className="space-y-2">
              <Label htmlFor="mcp-token-name" className="text-xs font-semibold">
                Tên gợi nhớ (Client / Thiết bị)
              </Label>
              <Input
                id="mcp-token-name"
                value={name}
                maxLength={120}
                placeholder="Ví dụ: Claude Desktop - MacBook Pro"
                className="h-10 text-sm"
                onChange={(e) => setName(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="mcp-token-expiry" className="text-xs font-semibold">
                Thời hạn hiệu lực
              </Label>
              <NativeSelect
                id="mcp-token-expiry"
                className="w-full h-10 text-sm"
                value={expiry}
                onChange={(e) => setExpiry(e.target.value)}
              >
                <NativeSelectOption value="180">6 tháng (180 ngày) - Mặc định</NativeSelectOption>
                <NativeSelectOption value="365">1 năm (365 ngày)</NativeSelectOption>
                <NativeSelectOption value="none">Vĩnh viễn (Không hết hạn)</NativeSelectOption>
                <NativeSelectOption value="90">3 tháng (90 ngày)</NativeSelectOption>
                <NativeSelectOption value="30">1 tháng (30 ngày)</NativeSelectOption>
                <NativeSelectOption value="7">7 ngày (Ngắn hạn / Test)</NativeSelectOption>
              </NativeSelect>
            </div>

            <Button
              size="lg"
              className="w-full md:w-auto h-10 font-semibold shadow-2xs gap-2"
              disabled={!name.trim() || createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              <Key className="size-4" />
              {createMutation.isPending ? 'Đang tạo…' : 'Tạo Token mới'}
            </Button>
          </div>

          {/* Scope selection summary */}
          <div className="space-y-2 pt-1 border-t">
            <div className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
              <Shield className="size-3.5" />
              Quyền hạn cấp cho Token (Scopes):
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {ALL_MCP_SCOPES.map((scope) => {
                const checked = selectedScopes.includes(scope.key)
                return (
                  <label
                    key={scope.key}
                    className={`flex items-start gap-2 p-2 rounded-lg border text-xs cursor-pointer transition-colors ${
                      checked
                        ? 'bg-primary/5 border-primary/40 text-foreground'
                        : 'bg-muted/30 border-border/60 text-muted-foreground'
                    }`}
                  >
                    <Checkbox
                      checked={checked}
                      onCheckedChange={() => toggleScope(scope.key)}
                      className="mt-0.5"
                    />
                    <div className="min-w-0">
                      <div className="font-semibold text-[11px] truncate">{scope.label}</div>
                      <div className="text-[10px] text-muted-foreground truncate">{scope.key}</div>
                    </div>
                  </label>
                )
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Newly Issued Token Notice */}
      {issued && (
        <Alert className="border-amber-500/60 bg-amber-500/10 dark:bg-amber-950/30 p-4 sm:p-5">
          <ShieldAlert className="size-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-3 w-full">
            <AlertTitle className="text-sm sm:text-base font-bold text-amber-950 dark:text-amber-100">
              Token của bạn đã được tạo thành công!
            </AlertTitle>
            <AlertDescription className="text-xs text-amber-900 dark:text-amber-200 leading-relaxed">
              Hãy sao chép token hoặc đường dẫn URL dưới đây ngay bây giờ. Chuỗi token bí mật sẽ không được hiển thị lại vì lý do bảo mật.
            </AlertDescription>

            {/* Plain Token */}
            <div className="space-y-1">
              <div className="text-[11px] font-semibold text-amber-900 dark:text-amber-200 flex items-center justify-between">
                <span>1. Chuỗi Plaintext Token (Dùng cho Bearer Header)</span>
                <span className="text-[10px] font-normal text-muted-foreground">
                  Hạn: {displayDate(issued.expires_at)}
                </span>
              </div>
              <div className="flex items-center gap-2 rounded-lg border border-amber-400/60 bg-background/80 p-2 text-xs font-mono">
                <span className="flex-1 break-all select-all">{issued.token}</span>
                <Button
                  size="sm"
                  variant="outline"
                  className="shrink-0 h-8 gap-1 text-xs"
                  onClick={() => issued.token && copy('Token', issued.token)}
                >
                  {copied === 'Token' ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
                  {copied === 'Token' ? 'Đã chép' : 'Sao chép'}
                </Button>
              </div>
            </div>

            {/* URL Tokenized Endpoint */}
            {issuedMcpUrl && (
              <div className="space-y-1">
                <div className="text-[11px] font-semibold text-amber-900 dark:text-amber-200">
                  2. Đường dẫn Server URL trực tiếp (Dành cho Client chỉ hỗ trợ nhập URL)
                </div>
                <div className="flex items-center gap-2 rounded-lg border border-amber-400/60 bg-background/80 p-2 text-xs font-mono">
                  <span className="flex-1 break-all select-all text-xs">{issuedMcpUrl}</span>
                  <Button
                    size="sm"
                    variant="outline"
                    className="shrink-0 h-8 gap-1 text-xs"
                    onClick={() => copy('Server URL', issuedMcpUrl)}
                  >
                    {copied === 'Server URL' ? <Check className="size-3.5 text-emerald-600" /> : <LinkIcon className="size-3.5" />}
                    {copied === 'Server URL' ? 'Đã chép' : 'Sao chép URL'}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </Alert>
      )}

      {/* Token List */}
      <Card className="shadow-2xs">
        <CardHeader className="p-4 sm:p-6 pb-3">
          <CardTitle className="text-base sm:text-lg font-bold">Danh sách Token đã cấp</CardTitle>
          <CardDescription className="text-xs sm:text-sm">
            Theo dõi trạng thái hoạt động, thời hạn hiệu lực và quyền hạn của các token đã tạo.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 sm:p-6 pt-0">
          {!items.length ? (
            <EmptyState
              title="Chưa có MCP token nào"
              description="Điền tên và bấm 'Tạo Token mới' ở trên để cấp token kết nối đầu tiên cho AI client."
            />
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/40">
                    <TableHead className="font-semibold">Tên gợi nhớ</TableHead>
                    <TableHead className="font-semibold">Trạng thái</TableHead>
                    <TableHead className="font-semibold">Thời hạn hết hạn</TableHead>
                    <TableHead className="font-semibold">Quyền hạn (Scopes)</TableHead>
                    <TableHead className="font-semibold">Lần dùng cuối</TableHead>
                    <TableHead className="text-right font-semibold">Thao tác</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((token) => (
                    <TableRow key={token.id}>
                      <TableCell className="font-medium text-xs sm:text-sm">
                        <div className="flex items-center gap-2">
                          <Zap className="size-3.5 text-primary shrink-0" />
                          <span className="font-semibold">{token.name || 'MCP Token'}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            token.status === 'active'
                              ? 'default'
                              : token.status === 'revoked'
                                ? 'destructive'
                                : 'secondary'
                          }
                          className="capitalize text-[11px]"
                        >
                          {token.status === 'active'
                            ? 'Hoạt động'
                            : token.status === 'revoked'
                              ? 'Đã thu hồi'
                              : 'Hết hạn'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        <div className="flex items-center gap-1.5 font-medium">
                          <Clock className="size-3 text-muted-foreground/80" />
                          {displayDate(token.expires_at)}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {(token.scopes || []).map((scope) => (
                            <Badge key={scope} variant="outline" className="font-mono text-[10px] px-1.5 py-0">
                              {scope}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {token.last_used_at ? displayDate(token.last_used_at) : 'Chưa sử dụng'}
                      </TableCell>
                      <TableCell className="text-right">
                        {token.status !== 'revoked' ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-rose-600 hover:bg-rose-50 hover:text-rose-700 dark:hover:bg-rose-950/40 h-8 text-xs font-semibold"
                            onClick={() => setRevokeTargetId(token.id)}
                          >
                            <Trash2 className="mr-1 size-3.5" /> Thu hồi
                          </Button>
                        ) : (
                          <span className="text-xs text-muted-foreground italic">Đã thu hồi</span>
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

      {/* Revoke Dialog */}
      <Dialog open={revokeTargetId !== null} onOpenChange={(open) => !open && setRevokeTargetId(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Xác nhận thu hồi MCP Token</DialogTitle>
            <DialogDescription className="text-xs sm:text-sm">
              Token này sẽ bị hủy kích hoạt ngay lập tức. Các AI client (Claude Desktop, Cursor) đang sử dụng token này sẽ không thể truy cập vào dữ liệu Flama nữa.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setRevokeTargetId(null)}>
              Hủy bỏ
            </Button>
            <Button
              variant="destructive"
              disabled={revokeMutation.isPending}
              onClick={() => revokeTargetId && revokeMutation.mutate(revokeTargetId)}
            >
              {revokeMutation.isPending ? 'Đang thu hồi…' : 'Xác nhận thu hồi'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </TabsContent>
  )
}
