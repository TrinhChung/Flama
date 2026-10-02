import { useState, useEffect } from 'react'
import { Check, Shield } from 'lucide-react'
import { ConfirmDialog } from '@/shared/ui'
import { Button } from '@/components/ui/button'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import type { McpMode, McpToken } from '../types'
import { ALL_MCP_SCOPES } from '../types'

export interface McpTokenActionModalsProps {
  mode: McpMode
  rotatingToken: McpToken | null
  onRotateClose: () => void
  onRotateConfirm: (tokenId: number, expiryDays: number | null | 'none') => Promise<void>
  isRotating?: boolean
  revokingTokenId: number | null
  onRevokeClose: () => void
  onRevokeConfirm: (tokenId: number) => Promise<void>
  isRevoking?: boolean
  purgingToken: McpToken | null
  onPurgeClose: () => void
  onPurgeConfirm: (tokenId: number) => Promise<void>
  isPurging?: boolean
  isCleanupOpen: boolean
  inactiveCount: number
  onCleanupClose: () => void
  onCleanupConfirm: () => Promise<void>
  isCleaningUp?: boolean
  viewingScopeToken: McpToken | null
  onScopeDetailsClose: () => void
}

export function McpTokenActionModals({
  mode,
  rotatingToken,
  onRotateClose,
  onRotateConfirm,
  isRotating = false,
  revokingTokenId,
  onRevokeClose,
  onRevokeConfirm,
  isRevoking = false,
  purgingToken,
  onPurgeClose,
  onPurgeConfirm,
  isPurging = false,
  isCleanupOpen,
  inactiveCount,
  onCleanupClose,
  onCleanupConfirm,
  isCleaningUp = false,
  viewingScopeToken,
  onScopeDetailsClose,
}: McpTokenActionModalsProps) {
  const [rotateExpiry, setRotateExpiry] = useState('180')

  useEffect(() => {
    if (!rotatingToken) {
      setRotateExpiry('180')
    }
  }, [rotatingToken])

  return (
    <>
      {/* 1. Rotate Secret ConfirmDialog */}
      <ConfirmDialog
        open={Boolean(rotatingToken)}
        onOpenChange={(open) => !open && onRotateClose()}
        variant="primary"
        title={mode === 'admin' ? 'Xoay Vòng Secret Cho Token' : 'Đổi Secret Token (Rotate)'}
        description={
          mode === 'admin'
            ? 'Xoay vòng secret sẽ sinh một Secret Key mới cho token. Secret cũ sẽ ngay lập tức bị vô hiệu hóa mà không làm mất phân quyền Scopes đã cấu hình.'
            : 'Xoay vòng secret sẽ tạo mới chuỗi bí mật (Secret Key) cho token. Token cũ sẽ bị vô hiệu hóa ngay lập tức.'
        }
        confirmText={mode === 'admin' ? 'Xác Nhận Xoay Vòng Secret' : 'Xác nhận Đổi Secret'}
        isLoading={isRotating}
        onConfirm={async () => {
          if (rotatingToken) {
            await onRotateConfirm(
              rotatingToken.id,
              rotateExpiry === 'none' ? 'none' : Number(rotateExpiry)
            )
          }
        }}
      >
        <div className="mt-3 space-y-1.5">
          <label htmlFor="rotate-token-expiry" className="text-xs font-semibold text-foreground">
            Thời hạn hiệu lực của Secret mới
          </label>
          <NativeSelect
            id="rotate-token-expiry"
            value={rotateExpiry}
            onChange={(e) => setRotateExpiry(e.target.value)}
            className="w-full text-xs"
          >
            <NativeSelectOption value="30">30 ngày</NativeSelectOption>
            <NativeSelectOption value="90">90 ngày</NativeSelectOption>
            <NativeSelectOption value="180">180 ngày (Khuyên dùng)</NativeSelectOption>
            <NativeSelectOption value="365">1 năm</NativeSelectOption>
            <NativeSelectOption value="none">Vĩnh viễn (Không hết hạn)</NativeSelectOption>
          </NativeSelect>
        </div>
      </ConfirmDialog>

      {/* 2. Revoke ConfirmDialog */}
      <ConfirmDialog
        open={revokingTokenId !== null}
        onOpenChange={(open) => !open && onRevokeClose()}
        variant="destructive"
        title={mode === 'admin' ? 'Thu Hồi Token Này?' : 'Xác nhận thu hồi MCP Token'}
        description={
          mode === 'admin'
            ? 'Token sẽ chuyển sang trạng thái Đã thu hồi (Revoked). Các ứng dụng AI đang sử dụng token này sẽ không thể gọi API được nữa.'
            : 'Token này sẽ bị hủy kích hoạt ngay lập tức và các ứng dụng AI sẽ không thể truy cập dữ liệu được nữa.'
        }
        confirmText={mode === 'admin' ? 'Xác Nhận Thu Hồi' : 'Xác nhận thu hồi'}
        isLoading={isRevoking}
        onConfirm={async () => {
          if (revokingTokenId !== null) {
            await onRevokeConfirm(revokingTokenId)
          }
        }}
      />

      {/* 3. Purge ConfirmDialog */}
      <ConfirmDialog
        open={Boolean(purgingToken)}
        onOpenChange={(open) => !open && onPurgeClose()}
        variant="destructive"
        title={mode === 'admin' ? 'Xóa Vĩnh Viễn Token?' : 'Xác nhận xóa vĩnh viễn Token'}
        description={`Hành động này không thể hoàn tác. Bản ghi token "${purgingToken?.name || ''}" sẽ bị xóa vĩnh viễn khỏi hệ thống.`}
        confirmText={mode === 'admin' ? 'Xóa Vĩnh Viễn' : 'Xóa vĩnh viễn'}
        isLoading={isPurging}
        onConfirm={async () => {
          if (purgingToken) {
            await onPurgeConfirm(purgingToken.id)
          }
        }}
      />

      {/* 4. Cleanup ConfirmDialog */}
      <ConfirmDialog
        open={isCleanupOpen}
        onOpenChange={(open) => !open && onCleanupClose()}
        variant="primary"
        title={mode === 'admin' ? 'Dọn Dẹp Token Hết Hạn & Đã Thu Hồi' : 'Dọn dẹp Token cũ & Hết hạn'}
        description={
          mode === 'admin'
            ? `Hệ thống sẽ xóa vĩnh viễn tất cả ${inactiveCount} token đã hết hạn hoặc đã thu hồi trên toàn hệ thống để tối ưu cơ sở dữ liệu.`
            : `Xóa sạch tất cả ${inactiveCount} token đã thu hồi hoặc đã hết hạn của bạn khỏi cơ sở dữ liệu?`
        }
        confirmText={mode === 'admin' ? 'Xác Nhận Dọn Dẹp' : `Dọn dẹp ${inactiveCount} token`}
        isLoading={isCleaningUp}
        onConfirm={onCleanupConfirm}
      />

      {/* 5. Scope Details Dialog */}
      <Dialog
        open={Boolean(viewingScopeToken)}
        onOpenChange={(open) => !open && onScopeDetailsClose()}
      >
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Shield className="size-5 text-primary" />
              Chi Tiết Quyền Hạn ({viewingScopeToken?.name})
            </DialogTitle>
            <DialogDescription>
              {viewingScopeToken?.username
                ? `Chủ sở hữu: ${viewingScopeToken.username} (${viewingScopeToken.email || ''})`
                : 'Danh sách các quyền hạn được gán cho token này'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2">
            {viewingScopeToken?.scopes?.length ? (
              <div className="grid grid-cols-1 gap-2">
                {viewingScopeToken.scopes.map((scopeKey) => {
                  const scopeMeta = ALL_MCP_SCOPES.find((s) => s.key === scopeKey)
                  return (
                    <div
                      key={scopeKey}
                      className="p-2 rounded-lg border bg-muted/30 flex items-start gap-2.5 text-xs"
                    >
                      <Check className="size-4 text-emerald-600 shrink-0 mt-0.5" />
                      <div>
                        <div className="font-semibold text-foreground">
                          {scopeMeta?.label || scopeKey}
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                          {scopeMeta?.desc || scopeKey}
                        </div>
                        <div className="text-[10px] font-mono text-muted-foreground/80 mt-0.5">
                          {scopeKey}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground text-center py-4">
                Token này không có quyền hạn nào được gán.
              </p>
            )}
          </div>

          <DialogFooter>
            <Button onClick={onScopeDetailsClose}>Đóng</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
