import { Link } from 'react-router-dom'
import {
  Bot,
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  Eye,
  EyeOff,
  KeyRound,
  Pencil,
  Plus,
  RefreshCw,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Star,
  Trash2,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { TabsContent } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'

import { FLAMA_MCP_URL, BACKEND_ORIGIN } from '@/config/env'
import { useMcpOAuth, type OAuthEndpointsInfo } from '../hooks/useMcpOAuth'
import { useState } from 'react'

export function McpOAuthTab() {
  const {
    endpointsQuery,
    clientsQuery,
    connectedAppsQuery,
    clientName,
    setClientName,
    clientId,
    setClientId,
    clientSecret,
    setClientSecret,
    redirectUrisText,
    setRedirectUrisText,
    isCreateOpen,
    setIsCreateOpen,
    editingClient,
    editClientName,
    setEditClientName,
    editClientSecret,
    setEditClientSecret,
    editRedirectUrisText,
    setEditRedirectUrisText,
    isEditOpen,
    setIsEditOpen,
    openEditClient,
    rotateClientTarget,
    setRotateClientTarget,
    newRotatedSecret,
    setNewRotatedSecret,
    generateRandomKey,
    copiedKey,
    copy,
    createClientMutation,
    updateClientMutation,
    rotateSecretMutation,
    deleteClientMutation,
    revokeConnectedAppMutation,
    setDefaultClientMutation,
    refresh,
    isAdmin,
  } = useMcpOAuth()

  const [customRotateSecret, setCustomRotateSecret] = useState('')
  const [showUserSecret, setShowUserSecret] = useState(false)
  const [showReferenceDetails, setShowReferenceDetails] = useState(false)
  const [visibleSecrets, setVisibleSecrets] = useState<Record<number, boolean>>({})

  const toggleSecretVisibility = (id: number) => {
    setVisibleSecrets((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const defaultBase = BACKEND_ORIGIN || window.location.origin
  const ep: OAuthEndpointsInfo = endpointsQuery.data || {
    base_url: defaultBase,
    auth_url: `${defaultBase}/oauth/authorize`,
    token_url: `${defaultBase}/oauth/token`,
    resource_url: FLAMA_MCP_URL || `${defaultBase}/api/mcp`,
    userinfo_url: `${defaultBase}/oauth/userinfo`,
    openid_config_url: `${defaultBase}/.well-known/openid-configuration`,
    scopes: ['deck:read', 'note-type:read', 'note:check', 'note:create'],
    scopes_string: 'deck:read note-type:read note:check note:create',
    default_client: null,
  }

  const clients = clientsQuery.data?.items || []
  const connectedApps = connectedAppsQuery.data?.items || []

  const defaultClientFromEp = ep.default_client
  const activeClient = isAdmin
    ? (clients.find((c) => c.is_default) || clients[0] || defaultClientFromEp)
    : defaultClientFromEp

  const activeClientId = activeClient?.client_id || 'chatgpt_flama'
  const activeClientSecret = activeClient?.client_secret || ''

  return (
    <TabsContent value="oauth" className="space-y-6">
      {/* 1. Header Card with Quick Action */}
      <Card className="shadow-2xs border-primary/20 bg-linear-to-r from-primary/5 via-card to-card">
        <CardHeader className="p-4 sm:p-6 pb-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20 text-xs font-semibold px-2.5 py-0.5">
                  OAuth 2.1 PKCE
                </Badge>
                <Badge variant="secondary" className="text-xs">
                  ChatGPT & AI Connectors
                </Badge>
              </div>
              <CardTitle className="text-lg sm:text-xl font-bold flex items-center gap-2 pt-1">
                <Bot className="size-5 text-primary shrink-0" />
                Tích hợp ChatGPT qua OAuth 2.1
              </CardTitle>
              <CardDescription className="text-xs sm:text-sm">
                Cung cấp mã xác thực chuẩn để ChatGPT Actions & MCP Client kết nối trực tiếp, tự động đăng nhập và thao tác kho thẻ thay mặt bạn an toàn.{' '}
                <Link to="/guide/integrations/mcp-ai" className="text-primary hover:underline font-medium inline-flex items-center gap-0.5">
                  Xem hướng dẫn kết nối &rarr;
                </Link>
              </CardDescription>
            </div>

            {isAdmin ? (
              <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                <DialogTrigger asChild>
                  <Button className="shrink-0 gap-1.5 shadow-xs">
                    <Plus className="size-4" />
                    Đăng ký ChatGPT Connector
                  </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-md">
                  <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                      <ShieldCheck className="size-5 text-primary" />
                      Đăng ký OAuth Client cho ChatGPT
                    </DialogTitle>
                    <DialogDescription className="text-xs sm:text-sm">
                      Nhập thông tin Callback URL do ChatGPT cấp để cấp phép cho Connector.
                    </DialogDescription>
                  </DialogHeader>

                  <div className="space-y-4 py-2">
                    <div className="space-y-1.5">
                      <Label htmlFor="c-name" className="text-xs font-semibold">Tên Ứng dụng</Label>
                      <Input
                        id="c-name"
                        value={clientName}
                        onChange={(e) => setClientName(e.target.value)}
                        placeholder="ChatGPT Assistant"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="c-id" className="text-xs font-semibold">Client ID</Label>
                      <Input
                        id="c-id"
                        value={clientId}
                        onChange={(e) => setClientId(e.target.value)}
                        placeholder="chatgpt_flama"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <Label htmlFor="c-secret" className="text-xs font-semibold">Client Secret</Label>
                        <Button
                          type="button"
                          variant="ghost"
                          size="xs"
                          className="h-6 text-[11px] text-primary gap-1 px-1.5"
                          onClick={() => setClientSecret(generateRandomKey())}
                        >
                          <RefreshCw className="size-3" />
                          Tạo Secret ngẫu nhiên
                        </Button>
                      </div>
                      <Input
                        id="c-secret"
                        value={clientSecret}
                        onChange={(e) => setClientSecret(e.target.value)}
                        placeholder="flama_secret_2026"
                        className="font-mono text-xs"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="c-redirect" className="text-xs font-semibold">
                        Callback / Redirect URL từ ChatGPT
                      </Label>
                      <Textarea
                        id="c-redirect"
                        rows={3}
                        value={redirectUrisText}
                        onChange={(e) => setRedirectUrisText(e.target.value)}
                        placeholder="https://chatgpt.com/connector/oauth/ZIPD0EH64oVa"
                        className="font-mono text-xs"
                      />
                      <p className="text-[11px] text-muted-foreground">
                        Dán chính xác đường dẫn Callback URL do ChatGPT hiển thị tại ô "Callback URL".
                      </p>
                    </div>
                  </div>

                  <DialogFooter className="gap-2 sm:gap-0">
                    <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
                      Hủy
                    </Button>
                    <Button
                      onClick={() => createClientMutation.mutate()}
                      disabled={createClientMutation.isPending || !clientId.trim() || !clientName.trim()}
                    >
                      {createClientMutation.isPending ? 'Đang lưu…' : 'Lưu Client'}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            ) : null}
          </div>
        </CardHeader>
      </Card>

      {/* Newly Rotated Secret Notification */}
      {newRotatedSecret && (
        <Card className="border-emerald-500/50 bg-emerald-500/10 dark:bg-emerald-950/30">
          <CardHeader className="p-4 sm:p-5 pb-2">
            <CardTitle className="text-sm sm:text-base font-bold text-emerald-950 dark:text-emerald-100 flex items-center justify-between">
              <span className="flex items-center gap-2">
                <ShieldCheck className="size-5 text-emerald-600 dark:text-emerald-400" />
                Client Secret mới cho "{newRotatedSecret.clientName}"
              </span>
              <Button
                variant="ghost"
                size="xs"
                className="text-xs text-muted-foreground hover:text-foreground h-6 px-2"
                onClick={() => setNewRotatedSecret(null)}
              >
                Đóng
              </Button>
            </CardTitle>
            <CardDescription className="text-xs text-emerald-900 dark:text-emerald-200">
              Hãy sao chép chuỗi Client Secret này và cập nhật vào cấu hình ChatGPT của bạn. Chuỗi secret sẽ không hiển thị lại.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 sm:p-5 pt-0 space-y-2">
            <div className="flex items-center gap-2 rounded-lg border border-emerald-400/60 bg-background/80 p-2 text-xs font-mono">
              <span className="flex-1 break-all select-all">{newRotatedSecret.secret}</span>
              <Button
                size="sm"
                variant="outline"
                className="shrink-0 h-8 gap-1 text-xs"
                onClick={() => copy('Client Secret', newRotatedSecret.secret)}
              >
                {copiedKey === 'Client Secret' ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
                {copiedKey === 'Client Secret' ? 'Đã chép' : 'Sao chép Secret'}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 2. Primary Card: 4 Thông số Cần Điền Vào ChatGPT */}
      <Card className="shadow-xs border-primary/30 bg-card">
        <CardHeader className="p-4 sm:p-6 pb-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20 text-xs font-semibold px-2 py-0.5">
                  Thiết lập chính
                </Badge>
                <CardTitle className="text-base sm:text-lg font-bold flex items-center gap-2">
                  <Sparkles className="size-5 text-amber-500 shrink-0" />
                  Thông số Cần Điền Vào ChatGPT
                </CardTitle>
              </div>
              <CardDescription className="text-xs sm:text-sm mt-1">
                Khi tạo Custom GPT hoặc Action mới trên ChatGPT, bạn chỉ cần điền <strong>4 thông số</strong> dưới đây vào form cài đặt:
              </CardDescription>
            </div>
            <Button
              variant="ghost"
              size="xs"
              onClick={refresh}
              className="gap-1.5 text-xs self-start sm:self-auto text-muted-foreground hover:text-foreground shrink-0"
            >
              <RefreshCw className="size-3.5" />
              Làm mới
            </Button>
          </div>
        </CardHeader>

        <CardContent className="p-4 sm:p-6 pt-0 space-y-3.5">
          {/* Row 1: 1. Tên Plugin & 2. Mô tả */}
          <div className="grid sm:grid-cols-2 gap-3">
            {/* Item 1: Tên Plugin */}
            <div className="p-3.5 rounded-xl border bg-muted/30 flex flex-col justify-between gap-3">
              <div className="space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                    1. Tên Plugin (Name)
                  </span>
                  <Badge variant="secondary" className="text-[10px]">Tên hiển thị</Badge>
                </div>
                <div className="text-sm font-bold text-foreground truncate select-all">
                  {activeClient?.client_name || 'Flama Flashcard'}
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Tên định danh hiển thị của công cụ trong giao diện ChatGPT.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs gap-1.5 self-start"
                onClick={() => copy('plugin_name', activeClient?.client_name || 'Flama Flashcard')}
              >
                {copiedKey === 'plugin_name' ? (
                  <>
                    <Check className="size-3.5 text-emerald-500" />
                    Đã chép Tên
                  </>
                ) : (
                  <>
                    <Copy className="size-3.5" />
                    Sao chép Tên
                  </>
                )}
              </Button>
            </div>

            {/* Item 2: Mô tả */}
            <div className="p-3.5 rounded-xl border bg-muted/30 flex flex-col justify-between gap-3">
              <div className="space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                    2. Mô tả (Description)
                  </span>
                  <Badge variant="secondary" className="text-[10px]">Mục đích</Badge>
                </div>
                <div className="text-xs font-medium text-foreground line-clamp-2 select-all">
                  Tra cứu từ vựng, kiểm tra ngữ nghĩa và tự động tạo flashcard vào kho Flama cá nhân qua giao thức MCP.
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Giúp ChatGPT tự động nhận biết khi nào cần kích hoạt công cụ Flama.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs gap-1.5 self-start"
                onClick={() =>
                  copy(
                    'plugin_desc',
                    'Tra cứu từ vựng, kiểm tra ngữ nghĩa và tự động tạo flashcard vào kho Flama cá nhân qua giao thức MCP.'
                  )
                }
              >
                {copiedKey === 'plugin_desc' ? (
                  <>
                    <Check className="size-3.5 text-emerald-500" />
                    Đã chép Mô tả
                  </>
                ) : (
                  <>
                    <Copy className="size-3.5" />
                    Sao chép Mô tả
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Row 2: Item 3: Connection / Server URL */}
          <div className="p-3.5 rounded-xl border bg-muted/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  3. Connection / Server URL
                </span>
                <Badge variant="outline" className="text-[10px] border-primary/30 text-primary">
                  Endpoint MCP
                </Badge>
              </div>
              <div className="text-xs font-mono font-bold text-primary truncate select-all">
                {ep.resource_url}
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                URL gốc của máy chủ MCP Flama để ChatGPT gửi các lệnh tra cứu và tạo thẻ.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-xs gap-1.5 shrink-0 self-end sm:self-auto"
              onClick={() => copy('resource_url', ep.resource_url)}
            >
              {copiedKey === 'resource_url' ? (
                <>
                  <Check className="size-3.5 text-emerald-500" />
                  Đã chép URL
                </>
              ) : (
                <>
                  <Copy className="size-3.5" />
                  Sao chép Server URL
                </>
              )}
            </Button>
          </div>

          {/* Row 3: Item 4: Authentication (OAuth) - Client ID & Client Secret */}
          <div className="p-4 rounded-xl border border-primary/20 bg-primary/5 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                    <KeyRound className="size-4 text-primary" />
                    4. Client ID & Client Secret (Authentication: OAuth)
                  </span>
                  <Badge
                    variant="outline"
                    className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[10px] font-semibold"
                  >
                    {isAdmin ? 'Quản lý bởi Admin' : 'Cấp sẵn bởi Admin'}
                  </Badge>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Tại ô <strong>Authentication</strong> trên ChatGPT, chọn phương thức <strong>OAuth</strong> và dán 2 thông số sau:
                </p>
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-3 pt-1">
              {/* Client ID */}
              <div className="p-3 rounded-lg border bg-background/80 flex items-center justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Client ID</div>
                  <div className="font-mono text-xs font-bold text-foreground truncate select-all">
                    {activeClientId}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs gap-1 shrink-0 text-muted-foreground hover:text-foreground"
                  onClick={() => copy('client_id', activeClientId)}
                >
                  {copiedKey === 'client_id' ? <Check className="size-3.5 text-emerald-500" /> : <Copy className="size-3.5" />}
                  <span>{copiedKey === 'client_id' ? 'Đã chép' : 'Chép ID'}</span>
                </Button>
              </div>

              {/* Client Secret */}
              <div className="p-3 rounded-lg border bg-background/80 flex items-center justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Client Secret</div>
                    <button
                      type="button"
                      onClick={() => setShowUserSecret((prev) => !prev)}
                      className="text-[10px] text-primary hover:underline flex items-center gap-0.5"
                    >
                      {showUserSecret ? <EyeOff className="size-2.5" /> : <Eye className="size-2.5" />}
                      <span>{showUserSecret ? 'Ẩn' : 'Hiện'}</span>
                    </button>
                  </div>
                  <div className="font-mono text-xs font-bold text-emerald-600 dark:text-emerald-400 truncate select-all">
                    {activeClientSecret
                      ? showUserSecret
                        ? activeClientSecret
                        : '••••••••••••••••••••••••••••••••'
                      : isAdmin
                      ? '[Chưa có Secret - Hãy bấm Đổi Secret]'
                      : '[Chờ Admin thiết lập]'}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs gap-1 shrink-0 text-muted-foreground hover:text-foreground"
                  disabled={!activeClientSecret}
                  onClick={() => activeClientSecret && copy('client_secret', activeClientSecret)}
                >
                  {copiedKey === 'client_secret' ? <Check className="size-3.5 text-emerald-500" /> : <Copy className="size-3.5" />}
                  <span>{copiedKey === 'client_secret' ? 'Đã chép' : 'Chép Secret'}</span>
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 3. Secondary Card: Thông số Đối chiếu Kỹ thuật (Reference) */}
      <Card className="shadow-2xs">
        <CardHeader className="p-4 sm:p-6 pb-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <CardTitle className="text-base sm:text-lg font-bold flex items-center gap-2">
                  <SlidersHorizontal className="size-4.5 text-primary" />
                  Thông số Đối Chiếu Kỹ Thuật (Reference)
                </CardTitle>
                <Badge variant="outline" className="text-[10px]">
                  Tự động / Nâng cao
                </Badge>
              </div>
              <CardDescription className="text-xs sm:text-sm mt-1">
                ChatGPT thường tự nhận diện các thông số này qua OIDC. Bạn chỉ cần đối chiếu khi ChatGPT mở rộng yêu cầu kiểm tra kỹ thuật.
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowReferenceDetails((prev) => !prev)}
              className="gap-1.5 text-xs shrink-0 self-start sm:self-auto h-8"
            >
              {showReferenceDetails ? (
                <>
                  <ChevronUp className="size-3.5" />
                  Thu gọn bảng đối chiếu
                </>
              ) : (
                <>
                  <ChevronDown className="size-3.5" />
                  Xem bảng đối chiếu chi tiết
                </>
              )}
            </Button>
          </div>
        </CardHeader>

        {showReferenceDetails && (
          <CardContent className="p-4 sm:p-6 pt-0 space-y-3">
            <div className="overflow-x-auto rounded-xl border">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-muted/70 border-b">
                    <th className="p-3 font-bold text-foreground">Trường Kỹ Thuật</th>
                    <th className="p-3 font-bold text-foreground">Giá trị hệ thống Flama</th>
                    <th className="p-3 font-bold text-foreground">Ghi chú đối chiếu</th>
                    <th className="p-3 font-bold text-foreground text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {[
                    {
                      field: 'Auth URL',
                      value: ep.auth_url,
                      key: 'auth_url',
                      note: 'Trang người dùng đăng nhập & cấp quyền cá nhân',
                    },
                    {
                      field: 'Token URL',
                      value: ep.token_url,
                      key: 'token_url',
                      note: 'Endpoint ChatGPT đổi authorization code lấy access token',
                    },
                    {
                      field: 'Token auth method',
                      value: 'client_secret_post',
                      key: 'token_method',
                      note: 'Phương thức gửi Client Secret trong thân HTTP POST',
                    },
                    {
                      field: 'Scopes (Default & Base)',
                      value: ep.scopes_string,
                      key: 'scopes',
                      note: 'Quyền đọc bộ thẻ và tạo flashcard vào Flama',
                    },
                    {
                      field: 'Authorization server base',
                      value: ep.base_url,
                      key: 'base_url',
                      note: 'Domain gốc của hệ thống máy chủ xác thực',
                    },
                    {
                      field: 'OIDC configuration URL',
                      value: ep.openid_config_url,
                      key: 'openid',
                      note: 'Tự động phát hiện cấu hình chuẩn OpenID Connect',
                    },
                    {
                      field: 'OIDC userinfo endpoint',
                      value: ep.userinfo_url,
                      key: 'userinfo',
                      note: 'Endpoint lấy thông tin người dùng đang đăng nhập',
                    },
                  ].map((row) => (
                    <tr key={row.key} className="hover:bg-muted/30 transition-colors">
                      <td className="p-3 font-semibold text-foreground whitespace-nowrap">
                        {row.field}
                      </td>
                      <td className="p-3 font-mono text-[11px] text-primary select-all break-all">
                        {row.value}
                      </td>
                      <td className="p-3 text-muted-foreground">
                        {row.note}
                      </td>
                      <td className="p-3 text-right">
                        <Button
                          variant="ghost"
                          size="xs"
                          onClick={() => copy(row.key, row.value)}
                          className="h-7 px-2 text-xs gap-1 text-muted-foreground hover:text-foreground inline-flex"
                        >
                          {copiedKey === row.key ? (
                            <>
                              <Check className="size-3 text-emerald-500" />
                              <span className="text-emerald-600 dark:text-emerald-400">Đã chép</span>
                            </>
                          ) : (
                            <>
                              <Copy className="size-3" />
                              <span>Sao chép</span>
                            </>
                          )}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        )}
      </Card>

      {/* 4. Registered OAuth Clients & Connected Apps */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Left Column: Admin sees Clients Table; Non-admin sees Pre-configured Credentials Card */}
        {isAdmin ? (
          <Card className="shadow-2xs">
            <CardHeader className="p-4 sm:p-6 pb-3">
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="text-sm sm:text-base font-bold flex items-center gap-2">
                  <KeyRound className="size-4.5 text-primary" />
                  OAuth Clients ({clients.length})
                </CardTitle>
                <Badge variant="outline" className="text-[10px]">
                  Chỉ Quản trị viên
                </Badge>
              </div>
              <CardDescription className="text-xs">
                Quản lý Client ID, Secret và chọn 1 bộ mặc định cho người dùng kết nối ChatGPT.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-4 sm:p-6 pt-0 space-y-2.5">
              {clients.length === 0 ? (
                <div className="text-center py-6 text-xs text-muted-foreground border rounded-xl border-dashed">
                  Chưa có Client nào. Hãy bấm "Đăng ký ChatGPT Connector" ở trên để tạo.
                </div>
              ) : (
                clients.map((c) => (
                  <div
                    key={c.id}
                    className={`p-3.5 rounded-xl border flex flex-col gap-2 text-xs transition-all ${
                      c.is_default
                        ? 'border-emerald-500/40 bg-emerald-500/5 shadow-2xs'
                        : 'bg-card hover:bg-muted/30'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-1 min-w-0 flex-1">
                        <div className="font-bold text-foreground flex flex-wrap items-center gap-2">
                          <span className="text-sm">{c.client_name}</span>
                          <Badge variant="outline" className="text-[10px] font-mono">
                            {c.client_id}
                          </Badge>
                          {c.is_default ? (
                            <Badge className="text-[10px] bg-emerald-600 dark:bg-emerald-700 text-white gap-1 font-semibold">
                              <Star className="size-3 fill-current" />
                              Mặc định cho người dùng
                            </Badge>
                          ) : (
                            <Badge variant="secondary" className="text-[10px]">
                              Phụ
                            </Badge>
                          )}
                        </div>
                        <div className="text-[11px] text-muted-foreground truncate">
                          Callbacks: {c.redirect_uris.join(', ')}
                        </div>
                      </div>

                      <div className="flex items-center gap-1 shrink-0">
                        {/* Set Default Button */}
                        {!c.is_default && (
                          <Button
                            variant="outline"
                            size="xs"
                            className="h-7 text-xs gap-1 text-muted-foreground hover:text-foreground"
                            onClick={() => setDefaultClientMutation.mutate(c.id)}
                            disabled={setDefaultClientMutation.isPending}
                            title="Chọn làm bộ thông số mặc định cho tất cả người dùng"
                          >
                            <Star className="size-3 text-amber-500" />
                            <span className="hidden sm:inline">Chọn mặc định</span>
                          </Button>
                        )}

                        {/* Edit Client */}
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-7 text-muted-foreground hover:text-foreground"
                          onClick={() => openEditClient(c)}
                          title="Chỉnh sửa Client"
                        >
                          <Pencil className="size-3.5" />
                        </Button>

                        {/* Rotate Secret */}
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-7 text-amber-600 hover:bg-amber-50 hover:text-amber-700 dark:hover:bg-amber-950/40"
                          onClick={() => {
                            setRotateClientTarget(c)
                            setCustomRotateSecret('')
                          }}
                          title="Tạo mới / Đổi Secret"
                        >
                          <RefreshCw className="size-3.5" />
                        </Button>

                        {/* Delete Client */}
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-7 text-destructive hover:bg-destructive/10"
                          onClick={() => deleteClientMutation.mutate(c.id)}
                          title="Xóa Client"
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </div>
                    </div>

                    {/* Secret display box */}
                    {c.client_secret ? (
                      <div className="flex items-center justify-between gap-2 p-2 rounded-lg bg-muted/50 border border-muted font-mono text-[11px]">
                        <div className="flex items-center gap-1.5 truncate">
                          <span className="text-muted-foreground text-[10px] font-sans font-medium">Secret:</span>
                          <span className="truncate select-all text-foreground">
                            {visibleSecrets[c.id] ? c.client_secret : '••••••••••••••••••••••••••••••••'}
                          </span>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-6 text-muted-foreground hover:text-foreground"
                            onClick={() => toggleSecretVisibility(c.id)}
                            title={visibleSecrets[c.id] ? 'Ẩn' : 'Hiện'}
                          >
                            {visibleSecrets[c.id] ? <EyeOff className="size-3" /> : <Eye className="size-3" />}
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-6 text-muted-foreground hover:text-foreground"
                            onClick={() => copy(`secret-${c.id}`, c.client_secret!)}
                            title="Sao chép Secret"
                          >
                            {copiedKey === `secret-${c.id}` ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="text-[11px] text-muted-foreground italic">
                        Chưa có chuỗi secret dạng rõ (hãy bấm Đổi Secret để tạo mới).
                      </div>
                    )}
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        ) : (
          /* Non-admin User View: Security & Connection Info Card */
          <Card className="shadow-2xs border-primary/20 bg-linear-to-br from-primary/5 via-card to-card">
            <CardHeader className="p-4 sm:p-6 pb-3">
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="text-sm sm:text-base font-bold flex items-center gap-2">
                  <ShieldCheck className="size-4.5 text-emerald-500" />
                  Bảo Mật OAuth 2.1 & Quyền Riêng Tư
                </CardTitle>
                <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[10px] font-semibold gap-1">
                  <Check className="size-3" /> Chuẩn PKCE
                </Badge>
              </div>
              <CardDescription className="text-xs leading-relaxed">
                Flama bảo vệ tài khoản và kho thẻ của bạn khi tích hợp với ChatGPT Actions thông qua cơ chế phân quyền chuẩn quốc tế.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-4 sm:p-6 pt-0 space-y-3 text-xs leading-relaxed text-muted-foreground">
              <div className="p-3 rounded-xl border bg-muted/30 space-y-1.5">
                <div className="font-semibold text-foreground flex items-center gap-1.5">
                  <Sparkles className="size-3.5 text-primary" />
                  Xác thực danh tính cá nhân
                </div>
                <p>
                  Khi bấm Test hoặc sử dụng Plugin trên ChatGPT lần đầu, trình duyệt sẽ tự động chuyển hướng đến màn hình đăng nhập Flama để bạn trực tiếp xác nhận cấp quyền.
                </p>
              </div>

              <div className="p-3 rounded-xl border bg-muted/30 space-y-1.5">
                <div className="font-semibold text-foreground flex items-center gap-1.5">
                  <KeyRound className="size-3.5 text-primary" />
                  Không tiết lộ mật khẩu
                </div>
                <p>
                  ChatGPT không bao giờ có quyền xem hay lưu mật khẩu Flama của bạn. Mọi thao tác truy vấn thẻ đều được ký bằng mã Access Token ngắn hạn và có thể thu hồi bất cứ lúc nào.
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Connected Apps Table */}
        <Card className="shadow-2xs">
          <CardHeader className="p-4 sm:p-6 pb-3">
            <CardTitle className="text-sm sm:text-base font-bold flex items-center gap-2">
              <ShieldCheck className="size-4.5 text-emerald-500" />
              Ứng dụng Đang Có Quyền Truy Cập ({connectedApps.length})
            </CardTitle>
            <CardDescription className="text-xs">
              Các phiên ChatGPT bạn đã bấm duyệt cấp quyền truy cập tài khoản.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 sm:p-6 pt-0 space-y-2.5">
            {connectedApps.length === 0 ? (
              <div className="text-center py-6 text-xs text-muted-foreground border rounded-xl border-dashed">
                Chưa có ứng dụng nào được cấp quyền. Khi bạn kết nối ChatGPT thành công, phiên truy cập sẽ hiển thị tại đây.
              </div>
            ) : (
              connectedApps.map((app) => (
                <div
                  key={app.client_id}
                  className="p-3 rounded-xl border bg-card flex items-center justify-between gap-2 text-xs"
                >
                  <div className="space-y-0.5 min-w-0">
                    <div className="font-bold text-foreground">{app.client_name}</div>
                    <div className="text-[10px] text-muted-foreground">
                      Cấp quyền: {app.authorized_at ? new Date(app.authorized_at).toLocaleDateString('vi-VN') : 'Mới đây'}
                    </div>
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    className="text-xs h-7 px-2.5 gap-1"
                    onClick={() => revokeConnectedAppMutation.mutate(app.client_id)}
                  >
                    Thu hồi quyền
                  </Button>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Edit OAuth Client Dialog */}
      <Dialog open={isEditOpen} onOpenChange={(open) => !open && setIsEditOpen(false)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Pencil className="size-4.5 text-primary" />
              Chỉnh sửa OAuth Client
            </DialogTitle>
            <DialogDescription className="text-xs sm:text-sm">
              Cập nhật tên, secret hoặc danh sách Callback URLs của Client <strong>{editingClient?.client_id}</strong>.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="edit-c-name" className="text-xs font-semibold">Tên Ứng dụng</Label>
              <Input
                id="edit-c-name"
                value={editClientName}
                onChange={(e) => setEditClientName(e.target.value)}
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="edit-c-secret" className="text-xs font-semibold">
                  Client Secret
                </Label>
                <Button
                  type="button"
                  variant="ghost"
                  size="xs"
                  className="h-6 text-[11px] text-primary gap-1 px-1.5"
                  onClick={() => setEditClientSecret(generateRandomKey())}
                >
                  <RefreshCw className="size-3" />
                  Tạo ngẫu nhiên
                </Button>
              </div>
              <Input
                id="edit-c-secret"
                value={editClientSecret}
                onChange={(e) => setEditClientSecret(e.target.value)}
                placeholder="Nhập secret mới hoặc để trống để giữ nguyên secret cũ"
                className="font-mono text-xs"
              />
              <p className="text-[11px] text-muted-foreground">
                Thông tin được tải từ cơ sở dữ liệu. Bạn có thể chỉnh sửa trực tiếp hoặc giữ nguyên khi lưu.
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="edit-c-redirect" className="text-xs font-semibold">
                Callback / Redirect URLs (mỗi URL một dòng)
              </Label>
              <Textarea
                id="edit-c-redirect"
                rows={3}
                value={editRedirectUrisText}
                onChange={(e) => setEditRedirectUrisText(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setIsEditOpen(false)}>
              Hủy
            </Button>
            <Button
              onClick={() => updateClientMutation.mutate()}
              disabled={updateClientMutation.isPending || !editClientName.trim()}
            >
              {updateClientMutation.isPending ? 'Đang lưu…' : 'Lưu thay đổi'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Rotate Client Secret Dialog */}
      <Dialog open={rotateClientTarget !== null} onOpenChange={(open) => !open && setRotateClientTarget(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
              <RefreshCw className="size-5" />
              Đổi Client Secret cho "{rotateClientTarget?.client_name}"
            </DialogTitle>
            <DialogDescription className="text-xs sm:text-sm">
              Tạo mới mã bí mật (Client Secret) để cập nhật vào ChatGPT Connector.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2">
            <p className="text-xs text-muted-foreground leading-relaxed">
              Bạn có thể để hệ thống tự động sinh một chuỗi Secret 32 ký tự an toàn, hoặc nhập một chuỗi bí mật tùy chọn bên dưới.
            </p>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="rotate-c-sec" className="text-xs font-semibold">Secret tùy chỉnh (Tùy chọn)</Label>
                <Button
                  type="button"
                  variant="ghost"
                  size="xs"
                  className="h-6 text-[11px] text-primary gap-1 px-1.5"
                  onClick={() => setCustomRotateSecret(generateRandomKey())}
                >
                  <RefreshCw className="size-3" />
                  Sinh ngẫu nhiên
                </Button>
              </div>
              <Input
                id="rotate-c-sec"
                value={customRotateSecret}
                onChange={(e) => setCustomRotateSecret(e.target.value)}
                placeholder="Để trống để tự động tạo secret an toàn"
                className="font-mono text-xs"
              />
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setRotateClientTarget(null)}>
              Hủy bỏ
            </Button>
            <Button
              className="bg-amber-600 hover:bg-amber-700 text-white"
              disabled={rotateSecretMutation.isPending}
              onClick={() => {
                if (rotateClientTarget) {
                  rotateSecretMutation.mutate({
                    clientPk: rotateClientTarget.id,
                    customSecret: customRotateSecret.trim() || undefined,
                  })
                }
              }}
            >
              {rotateSecretMutation.isPending ? 'Đang tạo…' : 'Xác nhận Đổi Secret'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </TabsContent>
  )
}
