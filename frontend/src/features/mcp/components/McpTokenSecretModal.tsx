import { KeyRound, AlertTriangle } from 'lucide-react'
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
import type { IssuedTokenResult } from '../types'

export interface McpTokenSecretModalProps {
  issuedToken: IssuedTokenResult | null
  isOpen?: boolean
  onClose: () => void
}

export function McpTokenSecretModal({
  issuedToken,
  isOpen,
  onClose,
}: McpTokenSecretModalProps) {
  const showModal = isOpen !== undefined ? isOpen : Boolean(issuedToken)

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

            <CodeSnippetBox
              code={issuedToken.token}
              title="Secret Access Token (Bearer Key)"
              showCopyButton
            />

            <CodeSnippetBox
              code={serverUrl}
              title="Endpoint URL dành cho AI Assistant (Cursor / Claude)"
              showCopyButton
              copyLabel="Sao chép URL"
            />

            <CodeSnippetBox
              code={jsonConfig}
              language="json"
              title="Cấu hình nhanh Cursor / Claude Desktop (mcpServers)"
              showCopyButton
            />
          </div>
        )}

        <DialogFooter>
          <Button onClick={onClose}>Đã lưu Secret & Đóng</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
