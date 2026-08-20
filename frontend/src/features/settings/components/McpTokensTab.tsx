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
  AlertCircle,
  Check,
  Clock,
  Copy,
  Eraser,
  Key,
  KeyRound,
  Link as LinkIcon,
  Pencil,
  RefreshCw,
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
    purgeTargetToken,
    setPurgeTargetToken,
    isCleanupDialogOpen,
    setIsCleanupDialogOpen,
    editingToken,
    setEditingToken,
    editName,
    setEditName,
    editExpiry,
    setEditExpiry,
    editScopes,
    toggleEditScope,
    openEditDialog,
    rotateTargetToken,
    setRotateTargetToken,
    rotateExpiry,
    setRotateExpiry,
    openRotateDialog,
    createMutation,
    updateMutation,
    rotateMutation,
    revokeMutation,
    purgeMutation,
    cleanupMutation,
  } = hookResult

  const items = query.data?.items || []
  const activeCount = items.filter((t) => t.status === 'active').length
  const inactiveCount = items.filter((t) => t.status === 'revoked' || t.status === 'expired').length

  // Check if name typed by user matches any active token
  const isDuplicateName = Boolean(
    name.trim() &&
      items.some(
        (t) =>
          t.status === 'active' &&
          t.name.trim().toLowerCase() === name.trim().toLowerCase()
      )
  )

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
          label="Token cũ / Hết hạn"
          value={inactiveCount.toString()}
          hint={inactiveCount > 0 ? 'Có thể dọn dẹp để giải phóng DB' : 'Cơ sở dữ liệu gọn gàng'}
          tone={inactiveCount > 0 ? 'warning' : 'default'}
        />
        <StatCard
          label="Quyền hạn hỗ trợ"
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

          {/* Duplicate Name Warning */}
          {isDuplicateName && (
            <div className="flex items-center gap-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-900 dark:text-amber-200 text-xs">
              <AlertCircle className="size-4 text-amber-600 shrink-0" />
              <span>
                Bạn đã có một token đang hoạt động mang tên này. Bạn có thể dùng nút <strong>Sửa</strong> hoặc <strong>Đổi Secret (Rotate)</strong> ở danh sách bên dưới thay vì tạo trùng lặp.
              </span>
            </div>
          )}

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

      {/* Newly Issued or Rotated Token Notice */}
      {issued && (
        <Alert className="border-amber-500/60 bg-amber-500/10 dark:bg-amber-950/30 p-4 sm:p-5">
          <ShieldAlert className="size-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-3 w-full">
            <AlertTitle className="text-sm sm:text-base font-bold text-amber-950 dark:text-amber-100 flex items-center justify-between">
              <span>Secret Token của bạn đã sẵn sàng!</span>
              <Button
                variant="ghost"
                size="xs"
                className="text-xs text-muted-foreground hover:text-foreground h-6 px-2"
                onClick={() => hookResult.setIssued(null)}
              >
                Đóng
              </Button>
            </AlertTitle>
            <AlertDescription className="text-xs text-amber-900 dark:text-amber-200 leading-relaxed">
              Hãy sao chép chuỗi token bí mật hoặc đường dẫn URL dưới đây. Chuỗi secret sẽ không được hiển thị lại vì lý do bảo mật.
            </AlertDescription>

            {/* Plain Token */}
            <div className="space-y-1">
              <div className="text-[11px] font-semibold text-amber-900 dark:text-amber-200 flex items-center justify-between">
                <span>1. Chuỗi Plaintext Secret (Dùng cho Authorization: Bearer Header)</span>
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
                  2. Đường dẫn Server URL trực tiếp (Dành cho Cursor / Client chỉ hỗ trợ nhập URL)
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
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base sm:text-lg font-bold">Danh sách Token & Secrets ({items.length})</CardTitle>
              <CardDescription className="text-xs sm:text-sm">
                Theo dõi trạng thái, chỉnh sửa thông tin hoặc xoay vòng secret mà không gây phình dữ liệu.
              </CardDescription>
            </div>
            {inactiveCount > 0 && (
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5 text-xs text-amber-700 dark:text-amber-400 border-amber-500/40 hover:bg-amber-50 dark:hover:bg-amber-950/30"
                onClick={() => setIsCleanupDialogOpen(true)}
              >
                <Eraser className="size-3.5" />
                Dọn dẹp {inactiveCount} token cũ
              </Button>
            )}
          </div>
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
                        <div className="flex items-center justify-end gap-1">
                          {/* Sửa / Edit */}
                          <Button
                            size="icon"
                            variant="ghost"
                            className="size-8 text-muted-foreground hover:text-foreground"
                            title="Chỉnh sửa tên & quyền"
                            onClick={() => openEditDialog(token)}
                          >
                            <Pencil className="size-3.5" />
                          </Button>

                          {/* Rotate / Đổi Secret */}
                          <Button
                            size="icon"
                            variant="ghost"
                            className="size-8 text-amber-600 hover:bg-amber-50 hover:text-amber-700 dark:hover:bg-amber-950/40"
                            title="Xoay vòng / Đổi Secret Key"
                            onClick={() => openRotateDialog(token)}
                          >
                            <RefreshCw className="size-3.5" />
                          </Button>

                          {/* Thu hồi (Revoke) nếu đang active */}
                          {token.status === 'active' && (
                            <Button
                              size="icon"
                              variant="ghost"
                              className="size-8 text-rose-600 hover:bg-rose-50 hover:text-rose-700 dark:hover:bg-rose-950/40"
                              title="Thu hồi Token"
                              onClick={() => setRevokeTargetId(token.id)}
                            >
                              <ShieldAlert className="size-3.5" />
                            </Button>
                          )}

                          {/* Xóa vĩnh viễn (Purge) nếu đã revoked hoặc expired */}
                          {token.status !== 'active' && (
                            <Button
                              size="icon"
                              variant="ghost"
                              className="size-8 text-destructive hover:bg-destructive/10"
                              title="Xóa vĩnh viễn khỏi database"
                              onClick={() => setPurgeTargetToken(token)}
                            >
                              <Trash2 className="size-3.5" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 1. Edit Token Dialog */}
      <Dialog open={editingToken !== null} onOpenChange={(open) => !open && setEditingToken(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Pencil className="size-4.5 text-primary" />
              Chỉnh sửa MCP Token
            </DialogTitle>
            <DialogDescription className="text-xs sm:text-sm">
              Cập nhật tên gợi nhớ, thời hạn hoặc các quyền hạn được cấp.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="edit-token-name" className="text-xs font-semibold">Tên gợi nhớ</Label>
              <Input
                id="edit-token-name"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                maxLength={120}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="edit-token-expiry" className="text-xs font-semibold">Gia hạn thời gian hiệu lực</Label>
              <NativeSelect
                id="edit-token-expiry"
                value={editExpiry}
                onChange={(e) => setEditExpiry(e.target.value)}
                className="h-10 text-sm"
              >
                <NativeSelectOption value="keep">Giữ nguyên thời hạn hiện tại</NativeSelectOption>
                <NativeSelectOption value="180">Gia hạn 6 tháng (180 ngày)</NativeSelectOption>
                <NativeSelectOption value="365">Gia hạn 1 năm (365 ngày)</NativeSelectOption>
                <NativeSelectOption value="none">Chuyển sang Vĩnh viễn (Không hết hạn)</NativeSelectOption>
                <NativeSelectOption value="90">Gia hạn 3 tháng (90 ngày)</NativeSelectOption>
                <NativeSelectOption value="30">Gia hạn 1 tháng (30 ngày)</NativeSelectOption>
              </NativeSelect>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Quyền hạn (Scopes)</Label>
              <div className="grid grid-cols-2 gap-2 pt-1">
                {ALL_MCP_SCOPES.map((scope) => {
                  const checked = editScopes.includes(scope.key)
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
                        onCheckedChange={() => toggleEditScope(scope.key)}
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
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setEditingToken(null)}>
              Hủy
            </Button>
            <Button
              onClick={() => updateMutation.mutate()}
              disabled={!editName.trim() || updateMutation.isPending}
            >
              {updateMutation.isPending ? 'Đang lưu…' : 'Lưu thay đổi'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 2. Rotate Token Secret Dialog */}
      <Dialog open={rotateTargetToken !== null} onOpenChange={(open) => !open && setRotateTargetToken(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
              <RefreshCw className="size-5" />
              Đổi Secret Token (Rotate)
            </DialogTitle>
            <DialogDescription className="text-xs sm:text-sm">
              Hành động này sẽ <strong>tạo mới chuỗi bí mật (Secret Key)</strong> cho token{' '}
              <strong>"{rotateTargetToken?.name}"</strong> và vô hiệu hóa key cũ ngay lập tức.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2 text-xs text-muted-foreground leading-relaxed">
            <p>
              Bản ghi token này sẽ được giữ nguyên (không tạo trùng lặp trong cơ sở dữ liệu). Bạn chỉ cần cập nhật chuỗi key mới vào AI Client (Claude Desktop / Cursor).
            </p>
            <div className="space-y-1.5 pt-2">
              <Label htmlFor="rotate-token-expiry" className="text-xs font-semibold text-foreground">
                Thời hạn hiệu lực cho Secret mới
              </Label>
              <NativeSelect
                id="rotate-token-expiry"
                value={rotateExpiry}
                onChange={(e) => setRotateExpiry(e.target.value)}
                className="h-10 text-sm"
              >
                <NativeSelectOption value="180">6 tháng (180 ngày) - Mặc định</NativeSelectOption>
                <NativeSelectOption value="365">1 năm (365 ngày)</NativeSelectOption>
                <NativeSelectOption value="none">Vĩnh viễn (Không hết hạn)</NativeSelectOption>
                <NativeSelectOption value="90">3 tháng (90 ngày)</NativeSelectOption>
                <NativeSelectOption value="30">1 tháng (30 ngày)</NativeSelectOption>
                <NativeSelectOption value="7">7 ngày (Ngắn hạn / Test)</NativeSelectOption>
              </NativeSelect>
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setRotateTargetToken(null)}>
              Hủy bỏ
            </Button>
            <Button
              className="bg-amber-600 hover:bg-amber-700 text-white"
              disabled={rotateMutation.isPending}
              onClick={() => rotateTargetToken && rotateMutation.mutate(rotateTargetToken.id)}
            >
              {rotateMutation.isPending ? 'Đang tạo Secret mới…' : 'Xác nhận Đổi Secret'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 3. Revoke Dialog (Soft revoke) */}
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

      {/* 4. Purge Dialog (Hard delete) */}
      <Dialog open={purgeTargetToken !== null} onOpenChange={(open) => !open && setPurgeTargetToken(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-destructive flex items-center gap-2">
              <Trash2 className="size-5" />
              Xác nhận xóa vĩnh viễn Token
            </DialogTitle>
            <DialogDescription className="text-xs sm:text-sm">
              Bạn có chắc chắn muốn xóa vĩnh viễn token <strong>"{purgeTargetToken?.name}"</strong> khỏi cơ sở dữ liệu?
            </DialogDescription>
          </DialogHeader>
          <div className="text-xs text-muted-foreground leading-relaxed">
            Thao tác này sẽ xóa hoàn toàn bản ghi khỏi bảng lưu trữ để giải phóng dung lượng DB. Hành động này không thể hoàn tác.
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setPurgeTargetToken(null)}>
              Hủy bỏ
            </Button>
            <Button
              variant="destructive"
              disabled={purgeMutation.isPending}
              onClick={() => purgeTargetToken && purgeMutation.mutate(purgeTargetToken.id)}
            >
              {purgeMutation.isPending ? 'Đang xóa…' : 'Xóa vĩnh viễn'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 5. Cleanup Dialog (Bulk purge) */}
      <Dialog open={isCleanupDialogOpen} onOpenChange={setIsCleanupDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
              <Eraser className="size-5" />
              Dọn dẹp Token cũ & Hết hạn
            </DialogTitle>
            <DialogDescription className="text-xs sm:text-sm">
              Xóa sạch tất cả <strong>{inactiveCount} token</strong> đã thu hồi hoặc đã hết hạn của bạn khỏi cơ sở dữ liệu?
            </DialogDescription>
          </DialogHeader>
          <div className="text-xs text-muted-foreground leading-relaxed">
            Hành động này giúp cơ sở dữ liệu luôn gọn gàng, tránh phình dữ liệu và tối ưu hiệu suất truy vấn. Các token đang hoạt động sẽ không bị ảnh hưởng.
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setIsCleanupDialogOpen(false)}>
              Hủy
            </Button>
            <Button
              className="bg-amber-600 hover:bg-amber-700 text-white"
              disabled={cleanupMutation.isPending}
              onClick={() => cleanupMutation.mutate()}
            >
              {cleanupMutation.isPending ? 'Đang dọn dẹp…' : `Dọn dẹp ${inactiveCount} token`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </TabsContent>
  )
}

