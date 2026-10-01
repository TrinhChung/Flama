import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  BookOpen,
  Bot,
  Brain,
  Check,
  Copy,
  FolderTree,
  Globe,
  Image,
  Info,
  Layers,
  ShieldCheck,
} from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { TabsContent } from '@/components/ui/tabs'
import { BACKEND_ORIGIN, FLAMA_MCP_URL } from '@/config/env'
import { useBootstrap } from '@/shared/api/bootstrap'
import { McpTokensManager } from '@/features/mcp/components/McpTokensManager'
import { ALL_MCP_SCOPES, SCOPE_CATEGORIES } from '../hooks/useMcpTokenCRUD'

export interface McpTokensTabProps {
  hookResult?: any
  onSwitchToChatGPT?: () => void
}

function getCategoryIcon(key: string) {
  switch (key) {
    case 'decks':
      return FolderTree
    case 'notes':
      return BookOpen
    case 'note_types':
      return Layers
    case 'study_stats':
      return Brain
    case 'media':
      return Image
    default:
      return FolderTree
  }
}

export function McpTokensTab({ onSwitchToChatGPT }: McpTokensTabProps) {
  const { data: bootstrap } = useBootstrap()
  const canManageTokens = Boolean(
    bootstrap?.user?.is_admin || bootstrap?.user?.can_manage_mcp_tokens
  )

  const [copiedEndpoint, setCopiedEndpoint] = useState<string | null>(null)
  const defaultBase = BACKEND_ORIGIN || window.location.origin
  const mcpServerUrl = FLAMA_MCP_URL || `${defaultBase}/api/mcp`

  const copyEndpoint = async (label: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value)
      setCopiedEndpoint(label)
      window.setTimeout(() => setCopiedEndpoint(null), 2000)
      toast.success(`Đã sao chép ${label} vào bộ nhớ tạm.`)
    } catch {
      toast.error('Không thể sao chép vào bộ nhớ tạm.')
    }
  }

  return (
    <TabsContent value="tokens" className="space-y-6">
      {onSwitchToChatGPT && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3.5 sm:p-4 rounded-2xl border border-emerald-500/25 bg-emerald-500/5 shadow-2xs">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0">
              <Bot className="size-5" />
            </div>
            <div className="space-y-0.5">
              <div className="text-xs sm:text-sm font-bold text-foreground">
                Bạn đang tìm cách kết nối Flashcard Flama với ChatGPT?
              </div>
              <p className="text-[11px] sm:text-xs text-muted-foreground">
                Hãy mở tab <strong>1. Kết nối ChatGPT</strong> để được hướng dẫn 5 bước kết nối tự động bằng OAuth, không cần tạo mã token thủ công.
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={onSwitchToChatGPT}
            className="h-8 text-xs gap-1.5 shrink-0 border-emerald-500/30 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-500/10 w-full sm:w-auto justify-center"
          >
            <span>Mở Hướng Dẫn ChatGPT</span>
            <ArrowRight className="size-3.5" />
          </Button>
        </div>
      )}

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
                    Thông số Máy chủ MCP (Flama Remote Endpoint)
                  </CardTitle>
                  <Badge variant="outline" className="text-[10px] text-primary border-primary/30 font-mono">
                    Stream HTTP POST / SSE
                  </Badge>
                </div>
                <CardDescription className="text-xs sm:text-sm">
                  Đường dẫn kết nối MCP dùng cho Cursor IDE, Antigravity, Cline và các script tự động hóa qua Personal Access Token. Đối với ChatGPT, hãy mở tab <strong className="text-foreground">1. Kết nối ChatGPT</strong> để sử dụng quy trình đăng nhập OAuth tự động.
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
        <CardContent className="p-4 sm:p-5 pt-0 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 rounded-xl border bg-muted/40 p-2.5 text-xs font-mono">
            <span className="text-muted-foreground font-sans text-[11px] font-semibold shrink-0">Endpoint URL:</span>
            <span className="flex-1 break-all select-all font-semibold text-foreground text-xs sm:text-sm">{mcpServerUrl}</span>
            <Button
              size="sm"
              variant="outline"
              className="shrink-0 h-8 gap-1.5 text-xs w-full sm:w-auto justify-center"
              onClick={() => copyEndpoint('Server URL', mcpServerUrl)}
            >
              {copiedEndpoint === 'Server URL' ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
              <span>{copiedEndpoint === 'Server URL' ? 'Đã chép' : 'Sao chép URL'}</span>
            </Button>
          </div>

          <div className="flex items-start gap-2.5 p-2.5 rounded-xl border bg-amber-500/5 border-amber-500/20 text-xs text-amber-900 dark:text-amber-200">
            <Info className="size-4 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
            <div className="leading-relaxed text-[11px] sm:text-xs">
              <span className="font-bold">Claude Desktop:</span> Tính năng kết nối trợ lý Claude Desktop hiện đang trong giai đoạn thử nghiệm nội bộ (chưa ra mắt chính thức). Màn hình này hiện chủ yếu phục vụ Cursor IDE, Antigravity, Cline và quản lý Personal Access Token.
            </div>
          </div>
        </CardContent>
      </Card>

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
                  Tài khoản của bạn đang sử dụng cơ chế bảo mật kết nối AI tiêu chuẩn. Bạn có thể sao chép URL kết nối từ danh sách Token bên dưới để tích hợp với Cursor hoặc công cụ lập trình. Đối với ChatGPT, hãy chuyển sang tab <strong>1. Kết nối ChatGPT</strong> để làm theo hướng dẫn kết nối 5 bước dễ dàng.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
        </Card>
      )}

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

      {canManageTokens && (
        <McpTokensManager
          mode="user"
          createLayout="inline"
          onSwitchToChatGPT={onSwitchToChatGPT}
        />
      )}
    </TabsContent>
  )
}
