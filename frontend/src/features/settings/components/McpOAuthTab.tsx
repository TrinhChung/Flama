import { Link } from 'react-router-dom'
import {
  Bot,
  Check,
  Copy,
  Globe,
  KeyRound,
  Pencil,
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
    refresh,
    isAdmin,
  } = useMcpOAuth()

  const [customRotateSecret, setCustomRotateSecret] = useState('')

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
                  <td className="p-3 font-mono text-[11px]">
                    {clients.length > 0 ? clients[0].client_id : 'chatgpt_flama'} / [Secret bạn đã tạo]
                  </td>
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
                ? 'Quản lý Client ID, Secret và Redirect URIs được phép kết nối.'
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
                  <div className="space-y-1.5 min-w-0 flex-1">
                    <div className="font-bold text-foreground flex flex-wrap items-center gap-2">
                      <span>{c.client_name}</span>
                      <Badge variant="outline" className="text-[10px] font-mono">
                        {c.client_id}
                      </Badge>
                      {c.has_secret ? (
                        <Badge variant="default" className="text-[10px] bg-emerald-600 dark:bg-emerald-700">
                          Đã có Secret
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="text-[10px]">
                          Không có Secret
                        </Badge>
                      )}
                    </div>
                    <div className="text-[11px] text-muted-foreground truncate">
                      Callbacks: {c.redirect_uris.join(', ')}
                    </div>
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
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
                  Client Secret mới (để trống nếu giữ nguyên)
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
                placeholder="Để trống để giữ nguyên secret cũ"
                className="font-mono text-xs"
              />
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
