import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bot,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Copy,
  ExternalLink,
  Eye,
  EyeOff,
  Globe,
  Info,
  KeyRound,
  Pencil,
  Plus,
  RefreshCw,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
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

interface McpOAuthTabProps {
  tabValue?: string
}

export function McpOAuthTab({ tabValue = 'oauth' }: McpOAuthTabProps) {
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
    <TabsContent value={tabValue} className="space-y-6">
      {/* 1. Header Card with Quick Action */}
      <Card className="shadow-2xs border-primary/20 bg-linear-to-r from-primary/5 via-card to-card">
        <CardHeader className="p-4 sm:p-6 pb-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20 text-xs font-semibold px-2.5 py-0.5">
                  OAuth 2.1 An Toàn
                </Badge>
                <Badge variant="secondary" className="text-xs">
                  ChatGPT Connector
                </Badge>
              </div>
              <CardTitle className="text-lg sm:text-xl font-bold flex items-center gap-2 pt-1">
                <Bot className="size-5 text-primary shrink-0" />
                Kết Nối ChatGPT Với Kho Flashcard Flama
              </CardTitle>
              <CardDescription className="text-xs sm:text-sm">
                Trợ lý ChatGPT có thể tự động tra từ vựng, phân tích ngữ pháp tiếng Nhật và ghi thẻ nhớ trực tiếp vào Flama thay mặt bạn một cách an toàn.{' '}
                <Link to="/guide/integrations/mcp-ai" className="text-primary hover:underline font-medium inline-flex items-center gap-0.5">
                  Xem tài liệu chi tiết &rarr;
                </Link>
              </CardDescription>
            </div>

            {isAdmin ? (
              <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                <DialogTrigger asChild>
                  <Button variant="outline" size="sm" className="shrink-0 gap-1.5 shadow-xs border-primary/30 hover:bg-primary/5 text-xs self-start sm:self-auto">
                    <Plus className="size-3.5" />
                    Đăng ký Connector mới (Admin)
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

      {/* Notice Banner: Plugin in Developer Preview */}
      <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4 sm:p-5 space-y-2.5 shadow-2xs">
        <div className="flex items-start gap-3">
          <div className="p-2.5 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5">
            <Info className="size-5" />
          </div>
          <div className="space-y-1.5 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className="text-sm sm:text-base font-bold text-foreground">
                Lưu ý quan trọng: Flama Plugin đang trong giai đoạn thử nghiệm
              </h4>
              <Badge variant="outline" className="text-[10px] bg-amber-500/10 text-amber-800 dark:text-amber-200 border-amber-500/30 font-semibold">
                Cần bật Chế độ nhà phát triển
              </Badge>
            </div>
            <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
              Do Flama Plugin chưa được OpenAI đưa lên kho Store chung của ChatGPT, bạn chỉ cần <strong>bật Chế độ Nhà phát triển (Developer Mode)</strong> trên ChatGPT một lần duy nhất và làm theo <strong>5 bước đơn giản bên dưới</strong> để hoàn tất kết nối.
            </p>
            <p className="text-[11px] sm:text-xs text-amber-800 dark:text-amber-300 font-medium">
              • Yêu cầu: Tài khoản ChatGPT Plus, Team, Edu hoặc Pro (chính sách của OpenAI để kích hoạt Developer Mode).
            </p>
          </div>
        </div>
      </div>

      {/* 2. Primary Feature: 5-Step Visual Walkthrough for Non-Tech Users */}
      <Card className="shadow-xs border-primary/25 bg-card overflow-hidden">
        <CardHeader className="p-4 sm:p-6 pb-4 border-b bg-muted/20">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="bg-primary/10 text-primary border-primary/25 text-xs font-semibold px-2 py-0.5">
                  Dành cho người dùng
                </Badge>
                <CardTitle className="text-base sm:text-lg font-bold flex items-center gap-2">
                  <Bot className="size-5 text-primary shrink-0" />
                  Hướng Dẫn 5 Bước Kết Nối ChatGPT
                </CardTitle>
              </div>
              <CardDescription className="text-xs sm:text-sm mt-1">
                Thực hiện lần lượt các bước dưới đây trên giao diện ChatGPT để kích hoạt kết nối Flashcard:
              </CardDescription>
            </div>
            <Button
              variant="ghost"
              size="xs"
              onClick={refresh}
              className="gap-1.5 text-xs self-start sm:self-auto text-muted-foreground hover:text-foreground shrink-0"
            >
              <RefreshCw className="size-3.5" />
              Làm mới thông số
            </Button>
          </div>
        </CardHeader>

        <CardContent className="p-3.5 sm:p-6 space-y-4 sm:space-y-6">
          {/* Bước 1 */}
          <div className="flex items-start gap-3 sm:gap-4 p-3.5 sm:p-5 rounded-2xl border bg-muted/25 transition-all">
            <div className="flex items-center justify-center size-8 sm:size-9 rounded-xl bg-primary text-primary-foreground font-bold text-xs sm:text-sm shrink-0 mt-0.5 shadow-2xs">
              1
            </div>
            <div className="space-y-2 flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <h4 className="text-sm sm:text-base font-bold text-foreground flex items-center gap-1.5 sm:gap-2">
                  <Settings2 className="size-4 text-primary shrink-0" />
                  <span>Bật Chế độ Nhà phát triển (Developer Mode) trên ChatGPT</span>
                </h4>
                <Badge variant="secondary" className="text-[10px] shrink-0">Chỉ làm 1 lần duy nhất</Badge>
              </div>
              <ol className="list-decimal list-inside space-y-1.5 text-xs sm:text-sm text-muted-foreground leading-relaxed pl-0.5">
                <li>Truy cập <a href="https://chatgpt.com" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline font-medium inline-flex items-center gap-0.5">chatgpt.com <ExternalLink className="size-3" /></a> và đăng nhập tài khoản của bạn.</li>
                <li>Bấm vào tên tài khoản hoặc ảnh đại diện ở góc dưới cùng bên trái màn hình ➔ Chọn <strong>Cài đặt (Settings ⚙️)</strong>.</li>
                <li>Trong hộp thoại cài đặt, bấm chọn mục <strong>Bảo mật &amp; Đăng nhập (Security &amp; login)</strong> (hoặc một số phiên bản là <em>Apps &amp; Connectors ➔ Advanced settings</em>).</li>
                <li>Gạt công tắc dòng <strong>Chế độ nhà phát triển (Developer mode)</strong> sang trạng thái <strong>Bật (On)</strong>.</li>
              </ol>
            </div>
          </div>

          {/* Bước 2 */}
          <div className="flex items-start gap-3 sm:gap-4 p-3.5 sm:p-5 rounded-2xl border bg-muted/25 transition-all">
            <div className="flex items-center justify-center size-8 sm:size-9 rounded-xl bg-primary text-primary-foreground font-bold text-xs sm:text-sm shrink-0 mt-0.5 shadow-2xs">
              2
            </div>
            <div className="space-y-2 flex-1 min-w-0">
              <h4 className="text-sm sm:text-base font-bold text-foreground flex items-center gap-1.5 sm:gap-2">
                <ExternalLink className="size-4 text-primary shrink-0" />
                <span>Mở kho Plugin và chọn "Tự tạo plugin của bạn"</span>
              </h4>
              <ol className="list-decimal list-inside space-y-1.5 text-xs sm:text-sm text-muted-foreground leading-relaxed pl-0.5">
                <li>Quay lại màn hình chat mới trên ChatGPT.</li>
                <li>Bấm vào biểu tượng Plugin / Công cụ trên thanh chat (hoặc menu dấu <strong>+</strong> chọn <em>Apps / Plugins</em>) ➔ Chọn <strong>Duyệt Plugin (Browse Plugins)</strong>.</li>
                <li>Cuộn xuống dưới cùng của danh sách và bấm chọn <strong>"Tự tạo plugin của bạn" (Develop your own plugin)</strong> (hoặc <em>Create an app / Create connector</em>).</li>
              </ol>
            </div>
          </div>

          {/* Bước 3 */}
          <div className="flex items-start gap-3 sm:gap-4 p-3.5 sm:p-5 rounded-2xl border bg-muted/25 transition-all">
            <div className="flex items-center justify-center size-8 sm:size-9 rounded-xl bg-primary text-primary-foreground font-bold text-xs sm:text-sm shrink-0 mt-0.5 shadow-2xs">
              3
            </div>
            <div className="space-y-3 flex-1 min-w-0">
              <h4 className="text-sm sm:text-base font-bold text-foreground flex items-center gap-1.5 sm:gap-2">
                <Globe className="size-4 text-primary shrink-0" />
                <span>Dán Đường dẫn Máy chủ Flama (Server URL)</span>
              </h4>
              <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
                Tại ô yêu cầu nhập URL máy chủ của plugin trên ChatGPT, hãy dán đường dẫn máy chủ MCP của Flama dưới đây:
              </p>
              
              <div className="flex flex-col sm:flex-row sm:items-center gap-2 rounded-xl border bg-background/90 p-2.5 sm:p-3 text-xs font-mono">
                <span className="text-muted-foreground font-sans text-[11px] font-semibold shrink-0">Server URL:</span>
                <span className="flex-1 break-all select-all font-semibold text-primary text-xs sm:text-sm">{ep.resource_url}</span>
                <Button
                  size="sm"
                  variant="outline"
                  className="shrink-0 h-8 gap-1.5 text-xs w-full sm:w-auto justify-center"
                  onClick={() => copy('resource_url', ep.resource_url)}
                >
                  {copiedKey === 'resource_url' ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
                  <span>{copiedKey === 'resource_url' ? 'Đã chép URL' : 'Sao chép URL'}</span>
                </Button>
              </div>

              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Sau khi dán URL, bấm <strong>Tiếp tục (Find manifest / Next)</strong>. ChatGPT sẽ tự động quét và nhận diện Flama Flashcard.
              </p>
            </div>
          </div>

          {/* Bước 4 */}
          <div className="flex items-start gap-3 sm:gap-4 p-3.5 sm:p-5 rounded-2xl border border-primary/25 bg-primary/5 transition-all">
            <div className="flex items-center justify-center size-8 sm:size-9 rounded-xl bg-primary text-primary-foreground font-bold text-xs sm:text-sm shrink-0 mt-0.5 shadow-2xs">
              4
            </div>
            <div className="space-y-3 flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <h4 className="text-sm sm:text-base font-bold text-foreground flex items-center gap-1.5 sm:gap-2">
                  <KeyRound className="size-4 text-primary shrink-0" />
                  <span>Cấu hình Nâng cao (Authentication: OAuth)</span>
                </h4>
                <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[10px] font-semibold">
                  {isAdmin ? 'Quản lý bởi Admin' : 'Cấp sẵn cho bạn'}
                </Badge>
              </div>

              <ol className="list-decimal list-inside space-y-1.5 text-xs sm:text-sm text-muted-foreground leading-relaxed pl-0.5">
                <li>Khi màn hình xác thực xuất hiện trên ChatGPT, nhấp vào mục <strong>Nâng cao (Advanced)</strong>.</li>
                <li>Tại mục <strong>Phương thức xác thực (Authentication)</strong>, chọn kiểu <strong>OAuth</strong>.</li>
                <li>Dán 2 thông số định danh bên dưới vào các ô tương ứng:</li>
              </ol>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 sm:gap-3 pt-1">
                {/* Client ID */}
                <div className="p-2.5 sm:p-3 rounded-xl border bg-background/90 flex items-center justify-between gap-2 shadow-2xs">
                  <div className="min-w-0 flex-1">
                    <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Client ID</div>
                    <div className="font-mono text-xs font-bold text-foreground truncate select-all">
                      {activeClientId}
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 px-2.5 text-xs gap-1 shrink-0 text-foreground"
                    onClick={() => copy('client_id', activeClientId)}
                  >
                    {copiedKey === 'client_id' ? <Check className="size-3.5 text-emerald-500" /> : <Copy className="size-3.5" />}
                    <span>{copiedKey === 'client_id' ? 'Đã chép' : 'Chép ID'}</span>
                  </Button>
                </div>

                {/* Client Secret */}
                <div className="p-2.5 sm:p-3 rounded-xl border bg-background/90 flex items-center justify-between gap-2 shadow-2xs">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Client Secret</div>
                      <button
                        type="button"
                        onClick={() => setShowUserSecret((prev) => !prev)}
                        className="text-[10px] text-primary hover:underline flex items-center gap-0.5 cursor-pointer"
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
                    variant="outline"
                    size="sm"
                    className="h-8 px-2.5 text-xs gap-1 shrink-0 text-foreground"
                    disabled={!activeClientSecret}
                    onClick={() => activeClientSecret && copy('client_secret', activeClientSecret)}
                  >
                    {copiedKey === 'client_secret' ? <Check className="size-3.5 text-emerald-500" /> : <Copy className="size-3.5" />}
                    <span>{copiedKey === 'client_secret' ? 'Đã chép' : 'Chép Secret'}</span>
                  </Button>
                </div>
              </div>
            </div>
          </div>

          {/* Bước 5 */}
          <div className="flex items-start gap-3 sm:gap-4 p-3.5 sm:p-5 rounded-2xl border bg-muted/25 transition-all">
            <div className="flex items-center justify-center size-8 sm:size-9 rounded-xl bg-emerald-600 text-white font-bold text-xs sm:text-sm shrink-0 mt-0.5 shadow-2xs">
              5
            </div>
            <div className="space-y-3 flex-1 min-w-0">
              <h4 className="text-sm sm:text-base font-bold text-foreground flex items-center gap-1.5 sm:gap-2">
                <CheckCircle2 className="size-4 text-emerald-600 shrink-0" />
                <span>Bấm Lưu &amp; Đồng ý Điều Khoản Cấp Quyền (Hoàn tất)</span>
              </h4>
              <ol className="list-decimal list-inside space-y-1.5 text-xs sm:text-sm text-muted-foreground leading-relaxed pl-0.5">
                <li>Bấm nút <strong>Lưu (Save) / Tiếp tục (Continue)</strong> trên ChatGPT.</li>
                <li>Trình duyệt sẽ tự động mở một cửa sổ đăng nhập Flama: Hãy bấm <strong>"Đồng ý điều khoản &amp; Cấp quyền" (Authorize / Consent)</strong> để xác nhận.</li>
                <li>Quay lại màn hình chat ChatGPT và bắt đầu trải nghiệm!</li>
              </ol>

              {/* Sample Prompts Box with 1-click Tap to Copy */}
              <div className="p-3 sm:p-3.5 rounded-xl border bg-emerald-500/5 border-emerald-500/20 space-y-2 text-xs">
                <div className="font-semibold text-emerald-800 dark:text-emerald-300 flex items-center gap-1.5">
                  <Bot className="size-4 text-emerald-600 shrink-0" />
                  <span>Mẫu câu lệnh thử nghiệm (Chạm vào để chép):</span>
                </div>
                <div className="space-y-1.5 font-mono text-[11px] text-foreground">
                  <div
                    onClick={() => copy('prompt1', 'Hãy giải thích ngữ nghĩa từ 桜 (hoa anh đào) và tự động tạo 1 thẻ flashcard vào Flama cho tôi')}
                    className="flex items-center justify-between gap-2 p-2 rounded-lg bg-background/90 border border-emerald-500/20 hover:border-emerald-500/50 cursor-pointer active:scale-[0.99] transition-all"
                  >
                    <span className="line-clamp-2 select-all">"Hãy giải thích ngữ nghĩa từ 桜 (hoa anh đào) và tự động tạo 1 thẻ flashcard vào Flama cho tôi"</span>
                    <Button variant="ghost" size="xs" className="h-6 px-1.5 shrink-0 text-muted-foreground hover:text-emerald-600">
                      {copiedKey === 'prompt1' ? <Check className="size-3 text-emerald-600" /> : <Copy className="size-3" />}
                      <span className="text-[10px] ml-1">{copiedKey === 'prompt1' ? 'Đã chép' : 'Chép'}</span>
                    </Button>
                  </div>
                  <div
                    onClick={() => copy('prompt2', 'Tra cứu xem trong kho flashcard của tôi đã có từ 勉強 chưa?')}
                    className="flex items-center justify-between gap-2 p-2 rounded-lg bg-background/90 border border-emerald-500/20 hover:border-emerald-500/50 cursor-pointer active:scale-[0.99] transition-all"
                  >
                    <span className="line-clamp-2 select-all">"Tra cứu xem trong kho flashcard của tôi đã có từ 勉強 chưa?"</span>
                    <Button variant="ghost" size="xs" className="h-6 px-1.5 shrink-0 text-muted-foreground hover:text-emerald-600">
                      {copiedKey === 'prompt2' ? <Check className="size-3 text-emerald-600" /> : <Copy className="size-3" />}
                      <span className="text-[10px] ml-1">{copiedKey === 'prompt2' ? 'Đã chép' : 'Chép'}</span>
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 3. Quick Copy Summary Card (For users who know the drill) */}
      <Card className="shadow-2xs">
        <CardHeader className="p-4 sm:p-5 pb-2">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-sm sm:text-base font-bold flex items-center gap-2">
              <Copy className="size-4 text-primary" />
              Bảng Tóm Tắt Nhanh 4 Thông Số
            </CardTitle>
            <Badge variant="secondary" className="text-[10px]">
              Sao chép nhanh
            </Badge>
          </div>
          <CardDescription className="text-xs">
            Dành cho người dùng đã quen: chỉ cần bấm sao chép lần lượt để dán vào ChatGPT.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-0">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 sm:gap-3 pt-2">
            {/* 1. Tên Plugin */}
            <div className="p-2.5 sm:p-3 rounded-xl border bg-muted/30 flex items-center justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="text-[10px] font-semibold text-muted-foreground uppercase">1. Tên Plugin</div>
                <div className="text-xs font-bold text-foreground truncate">{activeClient?.client_name || 'Flama Flashcard'}</div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs gap-1 px-2.5 shrink-0"
                onClick={() => copy('q_name', activeClient?.client_name || 'Flama Flashcard')}
              >
                {copiedKey === 'q_name' ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
                <span>{copiedKey === 'q_name' ? 'Đã chép' : 'Chép tên'}</span>
              </Button>
            </div>

            {/* 2. Mô tả */}
            <div className="p-2.5 sm:p-3 rounded-xl border bg-muted/30 flex items-center justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="text-[10px] font-semibold text-muted-foreground uppercase">2. Mô tả (Description)</div>
                <div className="text-xs font-medium text-foreground truncate">Tra cứu từ vựng và tự động tạo flashcard vào Flama.</div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs gap-1 px-2.5 shrink-0"
                onClick={() => copy('q_desc', 'Tra cứu từ vựng, kiểm tra ngữ nghĩa và tự động tạo flashcard vào kho Flama cá nhân qua giao thức MCP.')}
              >
                {copiedKey === 'q_desc' ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
                <span>{copiedKey === 'q_desc' ? 'Đã chép' : 'Chép mô tả'}</span>
              </Button>
            </div>

            {/* 3. Server URL */}
            <div className="p-2.5 sm:p-3 rounded-xl border bg-muted/30 flex items-center justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="text-[10px] font-semibold text-muted-foreground uppercase">3. Connection URL</div>
                <div className="text-xs font-mono font-bold text-primary truncate">{ep.resource_url}</div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs gap-1 px-2.5 shrink-0"
                onClick={() => copy('q_url', ep.resource_url)}
              >
                {copiedKey === 'q_url' ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
                <span>{copiedKey === 'q_url' ? 'Đã chép' : 'Chép URL'}</span>
              </Button>
            </div>

            {/* 4. Client ID */}
            <div className="p-2.5 sm:p-3 rounded-xl border bg-muted/30 flex items-center justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="text-[10px] font-semibold text-muted-foreground uppercase">4. Client ID</div>
                <div className="text-xs font-mono font-bold text-foreground truncate">{activeClientId}</div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs gap-1 px-2.5 shrink-0"
                onClick={() => copy('q_cid', activeClientId)}
              >
                {copiedKey === 'q_cid' ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
                <span>{copiedKey === 'q_cid' ? 'Đã chép' : 'Chép ID'}</span>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 4. Collapsible: Thông số Đối chiếu Kỹ thuật RFC 9728 & OIDC */}
      <Card className="shadow-2xs">
        <CardHeader className="p-4 sm:p-5 pb-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <CardTitle className="text-sm sm:text-base font-bold flex items-center gap-2">
                  <SlidersHorizontal className="size-4.5 text-primary" />
                  Thông Số Kỹ Thuật &amp; Đối Chiếu RFC 9728 (Dành Cho Lập Trình Viên)
                </CardTitle>
                <Badge variant="outline" className="text-[10px]">
                  Nâng cao / OIDC
                </Badge>
              </div>
              <CardDescription className="text-xs mt-1">
                ChatGPT thường tự động phát hiện các thông số này qua OIDC. Bạn chỉ cần đối chiếu khi kiểm tra chi tiết giao thức.
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
                  Thu gọn bảng kỹ thuật
                </>
              ) : (
                <>
                  <ChevronDown className="size-3.5" />
                  Xem bảng kỹ thuật chi tiết
                </>
              )}
            </Button>
          </div>
        </CardHeader>

        {showReferenceDetails && (
          <CardContent className="p-4 sm:p-5 pt-0 space-y-3">
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

      {/* 5. Registered OAuth Clients & Connected Apps */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Left Column: Admin sees Clients Table; Non-admin sees Security Info */}
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
                  Bảo Mật OAuth 2.1 &amp; Quyền Riêng Tư
                </CardTitle>
                <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[10px] font-semibold gap-1">
                  <Check className="size-3" /> Chuẩn PKCE
                </Badge>
              </div>
              <CardDescription className="text-xs leading-relaxed">
                Flama bảo vệ tài khoản và kho thẻ của bạn khi tích hợp với ChatGPT thông qua cơ chế phân quyền chuẩn quốc tế.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-4 sm:p-6 pt-0 space-y-3 text-xs leading-relaxed text-muted-foreground">
              <div className="p-3 rounded-xl border bg-muted/30 space-y-1.5">
                <div className="font-semibold text-foreground flex items-center gap-1.5">
                  <ShieldCheck className="size-3.5 text-primary" />
                  Xác thực danh tính trực tiếp
                </div>
                <p>
                  Khi kết nối trên ChatGPT lần đầu, trình duyệt sẽ chuyển hướng đến màn hình Flama để bạn trực tiếp bấm nút xác nhận cấp quyền.
                </p>
              </div>

              <div className="p-3 rounded-xl border bg-muted/30 space-y-1.5">
                <div className="font-semibold text-foreground flex items-center gap-1.5">
                  <KeyRound className="size-3.5 text-primary" />
                  Không tiết lộ mật khẩu cá nhân
                </div>
                <p>
                  ChatGPT không bao giờ có quyền xem hay lưu mật khẩu Flama của bạn. Mọi thao tác đều dùng mã Access Token ngắn hạn và có thể ngắt kết nối bất cứ lúc nào bên dưới.
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
              Ứng Dụng Đang Kết Nối ({connectedApps.length})
            </CardTitle>
            <CardDescription className="text-xs">
              Các phiên ChatGPT bạn đã duyệt cấp quyền truy cập tài khoản Flama.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 sm:p-6 pt-0 space-y-2.5">
            {connectedApps.length === 0 ? (
              <div className="text-center py-6 text-xs text-muted-foreground border rounded-xl border-dashed">
                Chưa có ứng dụng nào được cấp quyền. Khi bạn hoàn tất Bước 5 kết nối ChatGPT, phiên truy cập sẽ hiển thị tại đây.
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
                    Ngắt kết nối
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
