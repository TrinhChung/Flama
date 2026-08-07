import React, { useState } from 'react'
import {
  Key,
  Eye,
  EyeOff,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Trash2,
  LogOut,
  ShieldCheck,
  Loader2,
  WifiOff,
} from 'lucide-react'
import { useFlamaConnect } from '@/context/FlamaConnectContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface FlamaConnectModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export const FlamaConnectModal: React.FC<FlamaConnectModalProps> = ({ open, onOpenChange }) => {
  const {
    status,
    account,
    error,
    maskedKey,
    connect,
    forgetKey,
    disconnect,
    testConnection,
  } = useFlamaConnect()

  const [inputKey, setInputKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [rememberKey, setRememberKey] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isChangingKey, setIsChangingKey] = useState(false)

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputKey.trim()) return
    setIsSubmitting(true)
    const success = await connect(inputKey, rememberKey)
    setIsSubmitting(false)
    if (success) {
      setInputKey('')
      setIsChangingKey(false)
    }
  }

  const handleForgetKey = async () => {
    if (confirm('Bạn có chắc chắn muốn xóa Flama Connect Key khỏi thiết bị này? Thao tác này không xóa dữ liệu thẻ đã đồng bộ.')) {
      await forgetKey()
      setIsChangingKey(false)
      setInputKey('')
    }
  }

  const handleTestConnection = async () => {
    setIsSubmitting(true)
    await testConnection()
    setIsSubmitting(false)
  }

  const getStatusBadge = () => {
    switch (status) {
      case 'Connected':
        return <Badge className="bg-emerald-500/15 text-emerald-600 border-emerald-500/30 gap-1"><CheckCircle2 className="size-3" /> Đã kết nối Flama</Badge>
      case 'Connecting':
        return <Badge variant="outline" className="text-amber-600 border-amber-500/30 gap-1"><Loader2 className="size-3 animate-spin" /> Đang kết nối...</Badge>
      case 'ConnectionLost':
        return <Badge variant="destructive" className="gap-1"><WifiOff className="size-3" /> Mất kết nối</Badge>
      case 'AuthenticationFailed':
      case 'AuthenticationRequired':
        return <Badge variant="destructive" className="gap-1"><AlertCircle className="size-3" /> Xác thực thất bại</Badge>
      default:
        return <Badge variant="secondary" className="gap-1">Chưa kết nối</Badge>
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <DialogTitle className="flex items-center gap-2 text-lg font-bold">
              <ShieldCheck className="size-5 text-primary" /> Kết nối Flama Connect
            </DialogTitle>
            {getStatusBadge()}
          </div>
          <DialogDescription className="text-xs text-muted-foreground mt-1">
            Xác thực bằng Flama Connect Key để cho phép đồng bộ dữ liệu thẻ, loại thẻ và media với Flama Cloud.
          </DialogDescription>
        </DialogHeader>

        {status === 'Connected' && !isChangingKey ? (
          <div className="space-y-4 py-2">
            <div className="p-4 rounded-xl border bg-card/60 backdrop-blur space-y-3">
              <div className="flex items-center justify-between border-b pb-3">
                <span className="text-xs text-muted-foreground font-medium">Tài khoản kết nối</span>
                <span className="text-sm font-bold text-foreground">
                  Connected to Flama
                </span>
              </div>

              <div className="space-y-1">
                <div className="text-xs text-muted-foreground">Account</div>
                <div className="text-sm font-semibold text-primary">
                  {account?.displayName || 'Flama User'} <span className="text-xs font-normal text-muted-foreground">(@{account?.username})</span>
                </div>
              </div>

              <div className="space-y-1">
                <div className="text-xs text-muted-foreground">Flama Connect Key</div>
                <div className="text-xs font-mono bg-muted/60 p-2 rounded border truncate select-none">
                  {maskedKey}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground pt-1">
                <div>Workspace: <span className="font-semibold text-foreground">{account?.workspace || 'default'}</span></div>
                <div>Upload tối đa: <span className="font-semibold text-foreground">{(account?.uploadLimit || 1048576) / 1024 / 1024} MB</span></div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 pt-2">
              <Button size="sm" variant="outline" onClick={handleTestConnection} disabled={isSubmitting} className="flex-1">
                {isSubmitting ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <RefreshCw className="mr-1.5 size-3.5" />}
                Kiểm tra kết nối
              </Button>
              <Button size="sm" variant="outline" onClick={() => setIsChangingKey(true)} className="flex-1">
                <Key className="mr-1.5 size-3.5" />
                Đổi Key
              </Button>
              <Button size="sm" variant="outline" onClick={disconnect} className="text-amber-600 hover:text-amber-700">
                <LogOut className="mr-1.5 size-3.5" />
                Ngắt kết nối
              </Button>
              <Button size="sm" variant="outline" onClick={handleForgetKey} className="text-destructive hover:text-destructive">
                <Trash2 className="mr-1.5 size-3.5" />
                Xóa Key
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleConnect} className="space-y-4 py-2">
            {error && (
              <Alert variant="destructive" className="py-2.5">
                <AlertCircle className="size-4" />
                <AlertTitle className="text-xs font-bold">Lỗi xác thực</AlertTitle>
                <AlertDescription className="text-xs">{error}</AlertDescription>
              </Alert>
            )}

            <div className="space-y-2">
              <Label htmlFor="flama-key-input" className="text-xs font-semibold flex items-center justify-between">
                <span>Flama Connect Key</span>
                {isChangingKey && (
                  <button type="button" onClick={() => setIsChangingKey(false)} className="text-xs text-primary hover:underline font-normal">
                    Hủy đổi key
                  </button>
                )}
              </Label>
              <div className="relative">
                <Input
                  id="flama-key-input"
                  type={showKey ? 'text' : 'password'}
                  value={inputKey}
                  onChange={(e) => setInputKey(e.target.value)}
                  placeholder="flama_yt_xxxxxxxx_..."
                  className="pr-10 font-mono text-xs"
                  autoFocus
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  title={showKey ? 'Ẩn key' : 'Hiện key'}
                >
                  {showKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <Checkbox
                id="remember-key-checkbox"
                checked={rememberKey}
                onCheckedChange={(checked) => setRememberKey(Boolean(checked))}
              />
              <Label htmlFor="remember-key-checkbox" className="text-xs font-normal text-muted-foreground cursor-pointer">
                Lưu mã xác thực an toàn trên thiết bị này (Remember this key on this device)
              </Label>
            </div>

            <DialogFooter className="pt-2">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
                Hủy (Cancel)
              </Button>
              <Button type="submit" disabled={isSubmitting || !inputKey.trim()}>
                {isSubmitting && <Loader2 className="mr-2 size-4 animate-spin" />}
                Kết nối (Connect)
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
