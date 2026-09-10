import { Link } from 'react-router-dom'
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
  BookOpen,
  Brain,
  Check,
  Clock,
  Copy,
  Eraser,
  FileText,
  FolderTree,
  Globe,
  Image as ImageIcon,
  Key,
  KeyRound,
  Layers,
  Link as LinkIcon,
  Pencil,
  RefreshCw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  Zap,
} from 'lucide-react'
import { FLAMA_MCP_URL, BACKEND_ORIGIN } from '@/config/env'
import {
  ALL_MCP_SCOPES,
  SCOPE_CATEGORIES,
  SCOPE_PRESETS,
  type useMcpTokenCRUD,
} from '../hooks/useMcpTokenCRUD'

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

function getCategoryIcon(catKey: string) {
  switch (catKey) {
    case 'decks':
      return FolderTree
    case 'notes':
      return FileText
    case 'note_types':
      return Layers
    case 'study_stats':
      return Brain
    case 'media':
      return ImageIcon
    default:
      return Shield
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
    applyCreatePreset,
    toggleCreateCategory,
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
    applyEditPreset,
    toggleEditCategory,
    isPermissionsOnlyDialog,
    openEditDialog,
    openPermissionsDialog,
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
    canManageTokens,
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
      {/* Stats row (Admin or Users with Token Management Permission) */}
      {canManageTokens && (
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
            value={`${ALL_MCP_SCOPES.length} Scopes`}
            hint="5 nhóm: Bộ thẻ, Thẻ, Mẫu, SRS & Ảnh"
            tone="default"
          />
        </div>
      )}

      {/* 1. Connection Endpoint Info Card (Visible to All Users) */}
      {(() => {
        const defaultBase = BACKEND_ORIGIN || window.location.origin
        const mcpServerUrl = FLAMA_MCP_URL || `${defaultBase}/api/mcp`
        return (
          <Card className="shadow-2xs border-primary/20 bg-linear-to-r from-primary/5 via-card to-card">
            <CardHeader className="p-4 sm:p-5 pb-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-start gap-3 min-w-0">
                  <div className="p-2 rounded-xl bg-primary/10 text-primary shrink-0 mt-0.5">
                    <Globe className="size-5" />
                  </div>
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <CardTitle className="text-base sm:text-lg font-bold">
                        Thông số Kết nối MCP Server
                      </CardTitle>
                      <Badge variant="outline" className="text-[10px] text-primary border-primary/30 font-mono">
                        Stream HTTP POST / SSE
                      </Badge>
                    </div>
                    <CardDescription className="text-xs sm:text-sm">
                      Đường dẫn kết nối MCP dùng cho Claude Desktop, Cursor, Antigravity, Cline. Đối với ChatGPT, hãy mở tab <strong className="text-foreground">ChatGPT &amp; OAuth 2.1</strong> để sử dụng Client ID &amp; Secret dùng chung do Admin cấu hình sẵn.
                    </CardDescription>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0 self-start sm:self-center">
                  <Link
                    to="/guide/integrations/mcp-ai"
                    className="text-xs text-primary hover:underline font-medium inline-flex items-center gap-1"
                  >
                    <BookOpen className="size-3.5" />
                    <span>Hướng dẫn cài đặt &rarr;</span>
                  </Link>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-4 sm:p-5 pt-0 space-y-2">
              <div className="flex flex-col sm:flex-row sm:items-center gap-2 rounded-xl border bg-muted/40 p-2.5 text-xs font-mono">
                <span className="text-muted-foreground font-sans text-[11px] font-semibold shrink-0">Endpoint URL:</span>
                <span className="flex-1 break-all select-all font-semibold text-foreground text-xs sm:text-sm">{mcpServerUrl}</span>
                <Button
                  size="sm"
                  variant="outline"
                  className="shrink-0 h-8 gap-1.5 text-xs self-end sm:self-auto"
                  onClick={() => copy('Server URL', mcpServerUrl)}
                >
                  {copied === 'Server URL' ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
                  {copied === 'Server URL' ? 'Đã chép' : 'Sao chép URL'}
                </Button>
              </div>
            </CardContent>
          </Card>
        )
      })()}

      {/* Standard User Notice (when user cannot self-manage tokens) */}
      {!canManageTokens && (
        <Card className="shadow-2xs border-primary/20 bg-linear-to-r from-primary/5 via-card to-card">
          <CardHeader className="p-4 sm:p-5 pb-3">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-xl bg-primary/10 text-primary shrink-0 mt-0.5">
                <ShieldCheck className="size-5" />
              </div>
              <div className="space-y-1">
                <CardTitle className="text-base sm:text-lg font-bold">
                  Thông số Kết nối AI do Quản trị viên Quản lý
                </CardTitle>
                <CardDescription className="text-xs sm:text-sm leading-relaxed">
                  Tài khoản của bạn đang sử dụng cơ chế bảo mật kết nối AI tiêu chuẩn. Bạn có thể sao chép URL kết nối từ danh sách Token bên dưới để tích hợp với Claude Desktop hoặc Cursor. Đối với ChatGPT, hãy chuyển sang tab <strong>ChatGPT &amp; OAuth 2.1</strong> để sử dụng thông tin Client ID &amp; Secret do hệ thống thiết lập sẵn.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
        </Card>
      )}

      {/* Scope Matrix Card for Standard Users (Granted to all tokens by default) */}
      {!canManageTokens && (
        <Card className="shadow-2xs border-emerald-500/20">
          <CardHeader className="p-4 sm:p-6 pb-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <CardTitle className="text-base sm:text-lg font-bold flex items-center gap-2">
                    <ShieldCheck className="size-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                    Bảng Phân Quyền Tính Năng AI ({ALL_MCP_SCOPES.length} Scopes)
                  </CardTitle>
                  <Badge className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-xs font-semibold gap-1">
                    <Check className="size-3" /> Cấp cho tất cả token
                  </Badge>
                </div>
                <CardDescription className="text-xs sm:text-sm">
                  Tất cả các quyền hạn tính năng AI dưới đây được hệ thống kích hoạt đầy đủ cho toàn bộ token kết nối của bạn. Token của bạn có thể sử dụng tất cả công cụ tương ứng để tra cứu, tạo thẻ và ôn tập mà không cần cấu hình thủ công.
                </CardDescription>
              </div>
              <Link to="/guide/integrations/mcp-tools" className="text-xs text-primary hover:underline font-normal shrink-0">
                Xem 20 công cụ tương ứng &rarr;
              </Link>
            </div>
          </CardHeader>
          <CardContent className="p-4 sm:p-6 pt-0 space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 pt-1">
              {SCOPE_CATEGORIES.map((cat) => {
                const CatIcon = getCategoryIcon(cat.key)
                const catScopes = ALL_MCP_SCOPES.filter((s) => s.category === cat.key)

                return (
                  <div
                    key={cat.key}
                    className="rounded-xl border bg-muted/20 p-3 space-y-2.5 flex flex-col justify-between"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between gap-2 pb-1.5 border-b border-border/50">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <div className="flex size-6 items-center justify-center rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0">
                            <CatIcon className="size-3.5" />
                          </div>
                          <span className="font-semibold text-xs text-foreground truncate">{cat.name}</span>
                        </div>
                        <Badge variant="outline" className="text-[10px] text-emerald-600 dark:text-emerald-400 border-emerald-500/30 bg-emerald-500/5 font-semibold">
                          {catScopes.length}/{catScopes.length} quyền
                        </Badge>
                      </div>

                      <div className="space-y-1.5">
                        {catScopes.map((scope) => (
                          <div
                            key={scope.key}
                            className="flex items-start gap-2 p-1.5 rounded-lg border border-border/40 bg-background/80 text-xs shadow-2xs"
                          >
                            <div className="mt-0.5 rounded-full p-0.5 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0">
                              <Check className="size-3" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="font-medium text-[11px] leading-tight text-foreground">
                                {scope.label}
                              </div>
                              <div className="text-[10px] text-muted-foreground leading-tight line-clamp-1 mt-0.5">
                                {scope.desc}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Quick Generate Card (Admin or Users with Token Management Permission) */}
      {canManageTokens && (
        <Card className="shadow-2xs border-primary/20">
        <CardHeader className="p-4 sm:p-6 pb-3">
          <CardTitle className="text-base sm:text-lg font-bold flex items-center gap-2">
            <KeyRound className="size-5 text-primary shrink-0" />
            Tạo MCP Access Token mới
          </CardTitle>
          <CardDescription className="text-xs sm:text-sm">
            Mỗi AI client (Claude Desktop, Cursor, Antigravity) nên tạo 1 token riêng để phân quyền an toàn.{' '}
            <Link to="/guide/integrations/mcp-ai" className="text-primary hover:underline font-medium inline-flex items-center gap-0.5">
              Xem hướng dẫn cấu hình file JSON &rarr;
            </Link>
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
              disabled={!name.trim() || selectedScopes.length === 0 || createMutation.isPending}
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
                Bạn đã có một token đang hoạt động mang tên này. Bạn có thể dùng nút <strong>Sửa quyền</strong> hoặc <strong>Đổi Secret (Rotate)</strong> ở danh sách bên dưới thay vì tạo trùng lặp.
              </span>
            </div>
          )}

          {/* Scope selection matrix */}
          <div className="space-y-3 pt-2 border-t">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="text-xs font-semibold text-foreground flex items-center gap-1.5 flex-wrap">
                <Shield className="size-4 text-primary shrink-0" />
                <span>Quyền hạn cấp cho Token ({selectedScopes.length}/{ALL_MCP_SCOPES.length} Scopes):</span>
                <Link to="/guide/integrations/mcp-tools" className="text-xs text-primary hover:underline font-normal">
                  (Xem 20 công cụ tương ứng &rarr;)
                </Link>
              </div>

              {/* 1-Click Presets Bar */}
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] text-muted-foreground font-medium mr-1">Mẫu nhanh:</span>
                {SCOPE_PRESETS.map((preset) => {
                  const isPresetActive =
                    preset.scopes.length === selectedScopes.length &&
                    preset.scopes.every((s) => selectedScopes.includes(s))
                  return (
                    <Button
                      key={preset.key}
                      type="button"
                      variant={isPresetActive ? 'secondary' : 'outline'}
                      size="xs"
                      className={`text-[11px] h-6 px-2 gap-1 rounded-md transition-colors ${
                        isPresetActive ? 'border-primary/40 font-semibold text-primary' : 'text-muted-foreground'
                      }`}
                      onClick={() => applyCreatePreset(preset.key)}
                    >
                      {preset.key === 'all' && <ShieldCheck className="size-3" />}
                      {preset.key === 'readonly' && <BookOpen className="size-3" />}
                      {preset.key === 'manager' && <FolderTree className="size-3" />}
                      {preset.key === 'study' && <Brain className="size-3" />}
                      <span>{preset.label}</span>
                    </Button>
                  )
                })}
              </div>
            </div>

            {/* Categorized Scope Grid */}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 pt-1">
              {SCOPE_CATEGORIES.map((cat) => {
                const CatIcon = getCategoryIcon(cat.key)
                const catScopes = ALL_MCP_SCOPES.filter((s) => s.category === cat.key)
                const selectedInCat = catScopes.filter((s) => selectedScopes.includes(s.key)).length
                const isAllInCat = selectedInCat === catScopes.length

                return (
                  <div
                    key={cat.key}
                    className="rounded-xl border bg-muted/20 p-3 space-y-2.5 flex flex-col justify-between"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between gap-2 pb-1.5 border-b border-border/50">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <div className="flex size-6 items-center justify-center rounded-md bg-primary/10 text-primary shrink-0">
                            <CatIcon className="size-3.5" />
                          </div>
                          <span className="font-semibold text-xs text-foreground truncate">{cat.name}</span>
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="xs"
                          className="h-5 px-1.5 text-[10px] text-muted-foreground hover:text-foreground"
                          onClick={() => toggleCreateCategory(cat.key)}
                        >
                          {isAllInCat ? 'Bỏ chọn' : 'Chọn hết'}
                        </Button>
                      </div>

                      <div className="space-y-1.5">
                        {catScopes.map((scope) => {
                          const checked = selectedScopes.includes(scope.key)
                          return (
                            <label
                              key={scope.key}
                              className={`flex items-start gap-2 p-1.5 rounded-lg border text-xs cursor-pointer transition-colors ${
                                checked
                                  ? 'bg-background border-primary/30 text-foreground shadow-2xs'
                                  : 'bg-muted/40 border-transparent text-muted-foreground hover:bg-muted/60'
                              }`}
                            >
                              <Checkbox
                                checked={checked}
                                onCheckedChange={() => toggleScope(scope.key)}
                                className="mt-0.5"
                              />
                              <div className="min-w-0 flex-1">
                                <div className="font-medium text-[11px] leading-tight">
                                  {scope.label}
                                </div>
                                <div className="text-[10px] text-muted-foreground leading-tight line-clamp-1 mt-0.5">
                                  {scope.desc}
                                </div>
                              </div>
                            </label>
                          )
                        })}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </CardContent>
      </Card>
      )}

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

      {/* Token List (Admin or Users with Token Management Permission) */}
      {canManageTokens && (
        <Card className="shadow-2xs">
        <CardHeader className="p-4 sm:p-6 pb-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base sm:text-lg font-bold">
                {canManageTokens ? `Danh sách Token & Secrets (${items.length})` : `Token & Quyền Kết nối AI (${items.length})`}
              </CardTitle>
              <CardDescription className="text-xs sm:text-sm">
                {canManageTokens
                  ? 'Theo dõi trạng thái, chỉnh sửa quyền hạn trực tiếp hoặc xoay vòng secret mà không làm gián đoạn kết nối.'
                  : 'Danh sách các Token kết nối được cấp cho tài khoản của bạn để tích hợp với các trợ lý AI.'}
              </CardDescription>
            </div>
            {canManageTokens && inactiveCount > 0 && (
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
              title={canManageTokens ? 'Chưa có MCP token nào' : 'Chưa có Token cá nhân'}
              description={
                canManageTokens
                  ? "Điền tên và bấm 'Tạo Token mới' ở trên để cấp token kết nối đầu tiên cho AI client."
                  : 'Bạn chưa có token kết nối Claude/Cursor nào được cấp. Bạn có thể sử dụng kết nối ChatGPT ở tab bên cạnh hoặc liên hệ Quản trị viên để được cấp Token.'
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/40">
                    <TableHead className="font-semibold">Tên gợi nhớ</TableHead>
                    <TableHead className="font-semibold">Trạng thái</TableHead>
                    <TableHead className="font-semibold">Thời hạn</TableHead>
                    <TableHead className="font-semibold">Quyền hạn (Scopes)</TableHead>
                    <TableHead className="font-semibold">Lần dùng cuối</TableHead>
                    <TableHead className="text-right font-semibold">Thao tác</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((token) => {
                    const tokenScopes = token.scopes || []
                    const isFullAccess = tokenScopes.length === ALL_MCP_SCOPES.length
                    const isReadOnly =
                      tokenScopes.length > 0 &&
                      tokenScopes.every((s) => s.includes(':read') || s === 'note:check')

                    return (
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

                        {/* Interactive Scopes Cell */}
                        <TableCell>
                          <div
                            className={`group flex flex-wrap items-center gap-1 ${
                              canManageTokens ? 'cursor-pointer' : 'cursor-default'
                            } py-1 max-w-xs`}
                            title={canManageTokens ? 'Bấm để chỉnh sửa quyền hạn trực tiếp' : 'Xem chi tiết quyền hạn'}
                            onClick={() => openPermissionsDialog(token)}
                          >
                            {isFullAccess ? (
                              <Badge className="bg-primary/10 text-primary border-primary/30 font-medium text-[11px] gap-1 hover:bg-primary/20 transition-colors">
                                <ShieldCheck className="size-3 text-primary" />
                                Toàn quyền ({tokenScopes.length}/{ALL_MCP_SCOPES.length})
                              </Badge>
                            ) : isReadOnly ? (
                              <Badge variant="secondary" className="font-medium text-[11px] gap-1 hover:bg-muted transition-colors">
                                <BookOpen className="size-3 text-muted-foreground" />
                                Chỉ đọc ({tokenScopes.length}/{ALL_MCP_SCOPES.length})
                              </Badge>
                            ) : (
                              <Badge variant="outline" className="font-medium text-[11px] gap-1 hover:border-primary/50 transition-colors">
                                <Shield className="size-3 text-primary" />
                                {tokenScopes.length} Scopes
                              </Badge>
                            )}

                            {/* Show small badges */}
                            {!isFullAccess &&
                              tokenScopes.slice(0, 2).map((scope) => (
                                <Badge
                                  key={scope}
                                  variant="outline"
                                  className="font-mono text-[9px] px-1 py-0 text-muted-foreground"
                                >
                                  {scope}
                                </Badge>
                              ))}

                            {canManageTokens && (
                              <span className="text-[10px] text-primary/80 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-0.5 ml-1">
                                <Pencil className="size-2.5" /> Sửa
                              </span>
                            )}
                          </div>
                        </TableCell>

                        <TableCell className="text-xs text-muted-foreground">
                          {token.last_used_at ? displayDate(token.last_used_at) : 'Chưa sử dụng'}
                        </TableCell>

                        <TableCell className="text-right">
                          {canManageTokens ? (
                            <div className="flex items-center justify-end gap-1">
                              {/* Phân quyền nhanh (Edit Scopes) */}
                              <Button
                                size="icon"
                                variant="ghost"
                                className="size-8 text-primary hover:bg-primary/10"
                                title="Phân quyền & Cấp quyền hạn (Scopes)"
                                onClick={() => openPermissionsDialog(token)}
                              >
                                <ShieldCheck className="size-4" />
                              </Button>

                              {/* Sửa thông tin (Edit Name & Expiry) */}
                              <Button
                                size="icon"
                                variant="ghost"
                                className="size-8 text-muted-foreground hover:text-foreground"
                                title="Chỉnh sửa tên & thời hạn"
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
                          ) : (
                            <div className="flex items-center justify-end gap-1">
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-8 gap-1 text-xs text-muted-foreground hover:text-foreground"
                                title="Xem chi tiết quyền hạn (Scopes)"
                                onClick={() => openPermissionsDialog(token)}
                              >
                                <Shield className="size-3.5 text-primary" />
                                <span>Xem quyền</span>
                              </Button>
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
      )}

      {/* 1. Edit Token & Permissions Dialog */}
      <Dialog open={editingToken !== null} onOpenChange={(open) => !open && setEditingToken(null)}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {isPermissionsOnlyDialog ? (
                <ShieldCheck className="size-5 text-primary" />
              ) : (
                <Pencil className="size-5 text-primary" />
              )}
              {isPermissionsOnlyDialog
                ? canManageTokens
                  ? 'Cấp & Chỉnh sửa Quyền hạn MCP Token'
                  : 'Chi tiết Quyền hạn MCP Token'
                : 'Chỉnh sửa MCP Token'}
            </DialogTitle>
            <DialogDescription className="text-xs sm:text-sm">
              {canManageTokens ? (
                <>
                  Cập nhật quyền hạn cho token <strong>"{editingToken?.name}"</strong>. Thay đổi có hiệu lực ngay lập tức và <strong>giữ nguyên Secret Token</strong>.
                </>
              ) : (
                <>
                  Danh sách quyền hạn (scopes) được thiết lập cho token <strong>"{editingToken?.name}"</strong>.
                </>
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {!isPermissionsOnlyDialog && (
              <div className="grid gap-3 sm:grid-cols-2">
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
              </div>
            )}

            {/* Scope Matrix Section */}
            <div className="space-y-3 pt-2">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b pb-2">
                <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                  <Shield className="size-4 text-primary shrink-0" />
                  <span>Danh sách Quyền ({editScopes.length}/{ALL_MCP_SCOPES.length} đã chọn):</span>
                </div>

                {/* Presets Bar */}
                {canManageTokens && (
                  <div className="flex flex-wrap items-center gap-1">
                    {SCOPE_PRESETS.map((preset) => {
                      const isPresetActive =
                        preset.scopes.length === editScopes.length &&
                        preset.scopes.every((s) => editScopes.includes(s))
                      return (
                        <Button
                          key={preset.key}
                          type="button"
                          variant={isPresetActive ? 'secondary' : 'outline'}
                          size="xs"
                          className={`text-[10px] h-5 px-1.5 gap-1 rounded-md transition-colors ${
                            isPresetActive ? 'border-primary/40 font-semibold text-primary' : 'text-muted-foreground'
                          }`}
                          onClick={() => applyEditPreset(preset.key)}
                        >
                          <span>{preset.label}</span>
                        </Button>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Categorized Matrix */}
              <div className="grid gap-3 sm:grid-cols-2 pt-1">
                {SCOPE_CATEGORIES.map((cat) => {
                  const CatIcon = getCategoryIcon(cat.key)
                  const catScopes = ALL_MCP_SCOPES.filter((s) => s.category === cat.key)
                  const selectedInCat = catScopes.filter((s) => editScopes.includes(s.key)).length
                  const isAllInCat = selectedInCat === catScopes.length

                  return (
                    <div
                      key={cat.key}
                      className="rounded-xl border bg-muted/20 p-3 space-y-2 flex flex-col justify-between"
                    >
                      <div className="space-y-2">
                        <div className="flex items-center justify-between gap-2 pb-1 border-b border-border/50">
                          <div className="flex items-center gap-1.5 min-w-0">
                            <CatIcon className="size-3.5 text-primary shrink-0" />
                            <span className="font-semibold text-xs text-foreground truncate">{cat.name}</span>
                          </div>
                          {canManageTokens && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="xs"
                              className="h-5 px-1.5 text-[10px] text-muted-foreground hover:text-foreground"
                              onClick={() => toggleEditCategory(cat.key)}
                            >
                              {isAllInCat ? 'Bỏ chọn' : 'Chọn hết'}
                            </Button>
                          )}
                        </div>

                        <div className="space-y-1.5">
                          {catScopes.map((scope) => {
                            const checked = editScopes.includes(scope.key)
                            return (
                              <label
                                key={scope.key}
                                className={`flex items-start gap-2 p-1.5 rounded-lg border text-xs transition-colors ${
                                  canManageTokens ? 'cursor-pointer' : 'cursor-default'
                                } ${
                                  checked
                                    ? 'bg-background border-primary/30 text-foreground shadow-2xs'
                                    : 'bg-muted/40 border-transparent text-muted-foreground hover:bg-muted/60'
                                }`}
                              >
                                <Checkbox
                                  checked={checked}
                                  disabled={!canManageTokens}
                                  onCheckedChange={() => canManageTokens && toggleEditScope(scope.key)}
                                  className="mt-0.5"
                                />
                                <div className="min-w-0 flex-1">
                                  <div className="font-medium text-[11px] leading-tight">
                                    {scope.label}
                                  </div>
                                  <div className="text-[10px] text-muted-foreground leading-tight line-clamp-1 mt-0.5">
                                    {scope.desc}
                                  </div>
                                </div>
                              </label>
                            )
                          })}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0 pt-2 border-t">
            {canManageTokens ? (
              <>
                <Button variant="outline" onClick={() => setEditingToken(null)}>
                  Hủy
                </Button>
                <Button
                  onClick={() => updateMutation.mutate()}
                  disabled={!editName.trim() || editScopes.length === 0 || updateMutation.isPending}
                >
                  {updateMutation.isPending ? 'Đang lưu…' : `Lưu quyền hạn (${editScopes.length} Scopes)`}
                </Button>
              </>
            ) : (
              <Button variant="outline" onClick={() => setEditingToken(null)}>
                Đóng
              </Button>
            )}
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

