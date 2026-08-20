import {
  Bot,
  Check,
  Copy,
  Globe,
  KeyRound,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Zap,
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
import { useMcpOAuth } from '../hooks/useMcpOAuth'

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
    copiedKey,
    copy,
    createClientMutation,
    deleteClientMutation,
    revokeConnectedAppMutation,
    refresh,
    isAdmin,
  } = useMcpOAuth()

  const defaultBase = BACKEND_ORIGIN || window.location.origin
  const ep = endpointsQuery.data || {
    base_url: defaultBase,
    auth_url: `${defaultBase}/oauth/authorize`,
    token_url: `${defaultBase}/oauth/token`,
    resource_url: FLAMA_MCP_URL || `${defaultBase}/api/mcp`,
    userinfo_url: `${defaultBase}/oauth/userinfo`,
    openid_config_url: `${defaultBase}/.well-known/openid-configuration`,
    scopes_string: 'deck:read note-type:read note:check note:create',
  }

  const clients = clientsQuery.data?.items || []
  const connectedApps = connectedAppsQuery.data?.items || []


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
                Cung cấp mã xác thực chuẩn để ChatGPT Actions & MCP Client kết nối trực tiếp, tự động đăng nhập và thao tác kho thẻ thay mặt bạn an toàn.
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

                  <div className="grid grid-cols-2 gap-3">
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
                      <Label htmlFor="c-secret" className="text-xs font-semibold">Client Secret</Label>
                      <Input
                        id="c-secret"
                        value={clientSecret}
                        onChange={(e) => setClientSecret(e.target.value)}
                        placeholder="flama_secret_2026"
                      />
                    </div>
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
                    disabled={createClientMutation.isPending}
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

      {/* 2. Endpoints Copy-Paste Table */}
      <Card className="shadow-2xs">
        <CardHeader className="p-4 sm:p-6 pb-3">
          <CardTitle className="text-base sm:text-lg font-bold flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Globe className="size-5 text-primary" />
              Thông số Endpoints (Dán vào ChatGPT)
            </span>
            <Button variant="ghost" size="xs" onClick={refresh} className="gap-1 text-xs">
              <RefreshCw className="size-3.5" />
              Làm mới
            </Button>
          </CardTitle>
          <CardDescription className="text-xs sm:text-sm">
            Sao chép nhanh các đường dẫn bên dưới vào form thiết lập <strong>New Plugin / Connector</strong> của ChatGPT.
          </CardDescription>
        </CardHeader>

        <CardContent className="p-4 sm:p-6 pt-0 space-y-3">
          <div className="grid gap-2.5">
            {[
              {
                label: 'Connection / Server URL',
                sub: 'Endpoint nhận lệnh MCP của Flama',
                value: ep.resource_url,
                key: 'resource',
              },
              {
                label: 'Auth URL',
                sub: 'Trang người dùng đăng nhập & cấp quyền',
                value: ep.auth_url,
                key: 'auth_url',
              },
              {
                label: 'Token URL',
                sub: 'Endpoint ChatGPT đổi authorization code lấy token',
                value: ep.token_url,
                key: 'token_url',
              },
              {
                label: 'Authorization server base',
                sub: 'Domain gốc của hệ thống xác thực',
                value: ep.base_url,
                key: 'base_url',
              },
              {
                label: 'Default scopes & Base scopes',
                sub: 'Quyền đọc bộ thẻ và tạo flashcard',
                value: ep.scopes_string,
                key: 'scopes',
              },
              {
                label: 'OIDC configuration URL (Tùy chọn)',
                sub: 'Cấu hình OpenID Connect',
                value: ep.openid_config_url,
                key: 'openid',
              },
              {
                label: 'OIDC userinfo endpoint (Tùy chọn)',
                sub: 'Endpoint lấy thông tin user đăng nhập',
                value: ep.userinfo_url,
                key: 'userinfo',
              },
            ].map((item) => (
              <div
                key={item.key}
                className="flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded-xl border bg-muted/40 hover:bg-muted/60 transition-colors gap-2"
              >
                <div className="min-w-0 pr-2">
                  <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                    {item.label}
                  </div>
                  <div className="text-[11px] text-muted-foreground font-mono truncate select-all">
                    {item.value}
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copy(item.key, item.value)}
                  className="shrink-0 text-xs gap-1.5 h-8 self-end sm:self-auto"
                >
                  {copiedKey === item.key ? (
                    <>
                      <Check className="size-3.5 text-emerald-500" />
                      Đã chép
                    </>
                  ) : (
                    <>
                      <Copy className="size-3.5" />
                      Sao chép
                    </>
                  )}
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* 3. Mapping Guide matching ChatGPT's Modal */}
      <Card className="shadow-2xs">
        <CardHeader className="p-4 sm:p-6 pb-3">
          <CardTitle className="text-base sm:text-lg font-bold flex items-center gap-2">
            <Zap className="size-5 text-amber-500" />
            Hướng dẫn đối chiếu từng ô trong Modal ChatGPT
          </CardTitle>
          <CardDescription className="text-xs sm:text-sm">
            Chi tiết các trường bạn cần điền trên giao diện <strong>New Plugin</strong> của ChatGPT:
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 sm:p-6 pt-0">
          <div className="overflow-x-auto rounded-xl border">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-muted/70 border-b">
                  <th className="p-3 font-bold text-foreground">Trường trên ChatGPT</th>
                  <th className="p-3 font-bold text-foreground">Giá trị cần chọn / nhập</th>
                  <th className="p-3 font-bold text-foreground">Ghi chú</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr>
                  <td className="p-3 font-semibold">Name & Description</td>
                  <td className="p-3 font-mono text-[11px]">Flama / Flama Flashcard MCP</td>
                  <td className="p-3 text-muted-foreground">Tùy chọn hiển thị</td>
                </tr>
                <tr>
                  <td className="p-3 font-semibold">Connection / Server URL</td>
                  <td className="p-3 font-mono text-[11px] text-primary">{ep.resource_url}</td>
                  <td className="p-3 text-muted-foreground">URL sạch không chứa token</td>
                </tr>
                <tr>
                  <td className="p-3 font-semibold">Authentication</td>
                  <td className="p-3 font-semibold text-emerald-600 dark:text-emerald-400">OAuth</td>
                  <td className="p-3 text-muted-foreground">Chọn phương thức OAuth</td>
                </tr>
                <tr>
                  <td className="p-3 font-semibold">Registration method</td>
                  <td className="p-3 font-semibold">User-Defined OAuth Client</td>
                  <td className="p-3 text-muted-foreground">Sử dụng Client ID tự cấp</td>
                </tr>
                <tr>
                  <td className="p-3 font-semibold">Client ID & Secret</td>
                  <td className="p-3 font-mono text-[11px]">chatgpt_flama / flama_secret_2026</td>
                  <td className="p-3 text-muted-foreground">Lấy từ danh sách client bên dưới</td>
                </tr>
                <tr>
                  <td className="p-3 font-semibold">Token endpoint auth method</td>
                  <td className="p-3 font-semibold">client_secret_post</td>
                  <td className="p-3 text-muted-foreground">Gửi secret qua POST body</td>
                </tr>
                <tr>
                  <td className="p-3 font-semibold">Scopes (Default & Base)</td>
                  <td className="p-3 font-mono text-[11px]">deck:read note-type:read note:check note:create</td>
                  <td className="p-3 text-muted-foreground">Dán cùng một chuỗi vào cả 2 ô</td>
                </tr>
                <tr>
                  <td className="p-3 font-semibold">Auth URL & Token URL</td>
                  <td className="p-3 font-mono text-[11px]">{ep.auth_url} / {ep.token_url}</td>
                  <td className="p-3 text-muted-foreground">Bấm nút sao chép ở bảng trên</td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* 4. Registered OAuth Clients & Connected Apps */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Clients Table (Admin Only) */}
        <Card className="shadow-2xs">
          <CardHeader className="p-4 sm:p-6 pb-3">
            <CardTitle className="text-sm sm:text-base font-bold flex items-center gap-2">
              <KeyRound className="size-4.5 text-primary" />
              OAuth Clients {isAdmin ? `(${clients.length})` : ''}
            </CardTitle>
            <CardDescription className="text-xs">
              {isAdmin
                ? 'Các Client ID được phép yêu cầu xác thực qua Flama OAuth.'
                : 'Cấu hình OAuth Client do Quản trị viên quản lý.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 sm:p-6 pt-0 space-y-2.5">
            {!isAdmin ? (
              <div className="text-center py-6 px-3 text-xs text-muted-foreground border rounded-xl border-dashed">
                Đăng ký & quản lý OAuth Client chỉ khả dụng cho Quản trị viên (Admin). Bạn vẫn có thể sử dụng thông số Endpoint ở trên để kết nối ChatGPT và quản lý các phiên đã duyệt quyền ở bên cạnh.
              </div>
            ) : clients.length === 0 ? (
              <div className="text-center py-6 text-xs text-muted-foreground border rounded-xl border-dashed">
                Chưa có Client nào. Hãy bấm "Đăng ký ChatGPT Connector" ở trên để tạo.
              </div>
            ) : (
              clients.map((c) => (
                <div
                  key={c.id}
                  className="p-3 rounded-xl border bg-card flex items-start justify-between gap-2 text-xs"
                >
                  <div className="space-y-1 min-w-0">
                    <div className="font-bold text-foreground flex items-center gap-2">
                      {c.client_name}
                      <Badge variant="outline" className="text-[10px] font-mono">
                        {c.client_id}
                      </Badge>
                    </div>
                    <div className="text-[11px] text-muted-foreground truncate">
                      Callbacks: {c.redirect_uris.join(', ')}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-7 text-destructive hover:bg-destructive/10 shrink-0"
                    onClick={() => deleteClientMutation.mutate(c.id)}
                    title="Xóa Client"
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              ))
            )}
          </CardContent>
        </Card>

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
    </TabsContent>
  )
}
