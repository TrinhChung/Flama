import { useState } from 'react'
import { KeyRound, AlertTriangle, Check, Copy, LinkIcon } from 'lucide-react'
import { toast } from 'sonner'
import { CodeSnippetBox } from '@/shared/ui'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { FLAMA_MCP_URL } from '@/config/env'
import type { IssuedTokenResult, McpMode } from '../types'

export interface McpTokenSecretModalProps {
  issuedToken: IssuedTokenResult | null
  isOpen?: boolean
  onClose: () => void
  mode?: McpMode
}

export function McpTokenSecretModal({
  issuedToken,
  isOpen,
  onClose,
  mode = 'user',
}: McpTokenSecretModalProps) {
  const showModal = isOpen !== undefined ? isOpen : Boolean(issuedToken)
  const [copiedToken, setCopiedToken] = useState(false)
  const [copiedUrl, setCopiedUrl] = useState(false)

  const serverUrl = issuedToken
    ? `${FLAMA_MCP_URL.replace(/\/+$/, '')}/${encodeURIComponent(issuedToken.token)}`
    : ''

  const jsonConfig = issuedToken
    ? JSON.stringify(
        {
          mcpServers: {
            flama: {
              url: serverUrl,
              headers: {
                Authorization: `Bearer ${issuedToken.token}`,
              },
            },
          },
        },
        null,
        2
      )
    : ''

  const handleCopyToken = async () => {
    if (!issuedToken?.token) return
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(issuedToken.token)
      } else {
        throw new Error('Clipboard API unavailable')
      }
      setCopiedToken(true)
      toast.success(mode === 'admin' ? 'Đã sao chép Secret Token' : 'Đã sao chép Token vào bộ nhớ tạm.')
      setTimeout(() => setCopiedToken(false), 2000)
    } catch {
      toast.error(mode === 'admin' ? 'Không thể sao chép vào bộ nhớ tạm' : 'Không thể sao chép vào bộ nhớ tạm.')
    }
  }

  const handleCopyUrl = async () => {
    if (!serverUrl) return
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(serverUrl)
      } else {
        throw new Error('Clipboard API unavailable')
      }
      setCopiedUrl(true)
      toast.success(mode === 'admin' ? 'Đã sao chép URL' : 'Đã sao chép URL Endpoint vào bộ nhớ tạm.')
      setTimeout(() => setCopiedUrl(false), 2000)
    } catch {
      toast.error(mode === 'admin' ? 'Không thể sao chép vào bộ nhớ tạm' : 'Không thể sao chép vào bộ nhớ tạm.')
    }
  }

  return (
    <Dialog open={showModal} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
            <KeyRound className="size-5" />
            Token & Secret Đã Được Tạo Thành Công
          </DialogTitle>
          <DialogDescription>
            Secret Token của bạn đã sẵn sàng! Hãy sao chép ngay chuỗi Secret token bên dưới. Vì lý do an toàn, chuỗi secret đầy đủ sẽ không được hiển thị lại sau khi bạn đóng hộp thoại này.
          </DialogDescription>
        </DialogHeader>

        {issuedToken && (
          <div className="space-y-4 py-2">
            <input
              type="text"
              readOnly
              value={issuedToken.token}
              className="sr-only font-mono"
              tabIndex={-1}
              aria-hidden="true"
            />

            <div className="p-3 rounded-lg border bg-muted/40 text-xs space-y-1">
              <div><strong>Tên gợi nhớ:</strong> {issuedToken.name}</div>
              {issuedToken.username && <div><strong>Chủ sở hữu:</strong> {issuedToken.username}</div>}
              {issuedToken.expires_at && <div><strong>Hạn dùng:</strong> {issuedToken.expires_at}</div>}
            </div>

            <div className="flex items-start gap-2.5 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-800 dark:text-amber-300">
              <AlertTriangle className="size-4 shrink-0 mt-0.5" />
              <span>Chỉ hiển thị 1 lần duy nhất. Nếu đánh mất, bạn cần dùng chức năng <strong>Xoay vòng Secret (Rotate)</strong> để sinh key mới.</span>
            </div>

            <div className="rounded-lg border bg-muted/20 overflow-hidden text-sm">
              <div className="flex items-center justify-between border-b border-border/80 bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground">
                <span className="font-medium text-foreground font-mono">Secret Access Token (Bearer Key)</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="xs"
                  onClick={handleCopyToken}
                  className="h-6 gap-1 px-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted"
                >
                  {copiedToken ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
                  <span>{copiedToken ? 'Đã chép' : 'Sao chép'}</span>
                </Button>
              </div>
              <pre className="p-3 overflow-x-auto font-mono text-xs text-foreground">
                <code>{issuedToken.token}</code>
              </pre>
            </div>

            <div className="rounded-lg border bg-muted/20 overflow-hidden text-sm">
              <div className="flex items-center justify-between border-b border-border/80 bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground">
                <span className="font-medium text-foreground font-mono">Endpoint URL dành cho AI Assistant (Cursor / Claude)</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="xs"
                  onClick={handleCopyUrl}
                  className="h-6 gap-1 px-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted"
                >
                  {copiedUrl ? <Check className="size-3 text-emerald-500" /> : <LinkIcon className="size-3" />}
                  <span>{copiedUrl ? 'Đã chép' : 'Sao chép URL'}</span>
                </Button>
              </div>
              <pre className="p-3 overflow-x-auto font-mono text-xs text-foreground">
                <code>{serverUrl}</code>
              </pre>
            </div>

            <CodeSnippetBox
              code={jsonConfig}
              language="json"
              title="Cấu hình nhanh Cursor / Claude Desktop (mcpServers)"
              showCopyButton
            />
          </div>
        )}

        <DialogFooter className="flex-row justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Đóng</Button>
          <Button onClick={onClose}>Đã lưu Secret & Đóng</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
