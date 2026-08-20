import React, { useId } from 'react'
import { RefreshCw, Wifi, WifiOff, HelpCircle, Loader2 } from 'lucide-react'
import type { AnkiConnectStatus } from '@/lib/ankiConnectClient'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'

interface AnkiConnectionBarProps {
  endpoint: string
  onEndpointChange: (val: string) => void
  connectionStatus: AnkiConnectStatus
  ankiVersion: number | null
  connectionError: string | null
  isCheckingConn: boolean
  onCheckConnection: () => void
  onOpenGuide?: () => void
}

const statusLabels: Record<AnkiConnectStatus, string> = {
  Connected: 'Đã kết nối',
  'Anki is not running': 'Anki chưa chạy',
  'AnkiConnect is not installed': 'Chưa cài AnkiConnect',
  'Connection refused': 'Lỗi kết nối',
  'Unsupported AnkiConnect version': 'Phiên bản không hỗ trợ',
  'Invalid response': 'Phản hồi không hợp lệ',
  Timeout: 'Quá thời gian kết nối',
}

export const AnkiConnectionBar: React.FC<AnkiConnectionBarProps> = ({
  endpoint,
  onEndpointChange,
  connectionStatus,
  ankiVersion,
  connectionError,
  isCheckingConn,
  onCheckConnection,
  onOpenGuide,
}) => {
  const endpointInputId = useId()
  const isConnected = connectionStatus === 'Connected'

  return (
    <Card className="border-border/70 shadow-xs rounded-2xl overflow-hidden bg-card/80 backdrop-blur-xs">
      <CardContent className="p-3.5 sm:p-4 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 sm:gap-4">
        {/* Left Status Info */}
        <div className="flex items-center gap-3 min-w-0">
          <div
            className={`relative size-10 rounded-xl flex items-center justify-center shrink-0 transition-colors ${
              isConnected
                ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                : 'bg-destructive/10 text-destructive border border-destructive/20'
            }`}
          >
            {isConnected ? <Wifi className="size-5" /> : <WifiOff className="size-5" />}
            {isConnected && (
              <span className="absolute -top-1 -right-1 flex size-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full size-3 bg-emerald-500" />
              </span>
            )}
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs sm:text-sm font-bold text-foreground tracking-tight">
                AnkiConnect Local API
              </span>
              {isConnected ? (
                <Badge className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[10px] sm:text-[11px] font-semibold py-0.5 px-2">
                  Đã kết nối {ankiVersion ? `(v${ankiVersion})` : ''}
                </Badge>
              ) : (
                <Badge variant="destructive" className="text-[10px] sm:text-[11px] font-medium py-0.5 px-2">
                  {statusLabels[connectionStatus] || connectionStatus}
                </Badge>
              )}
            </div>
            {!isConnected ? (
              <div className="text-[11px] sm:text-xs mt-1 leading-relaxed">
                <span className="text-destructive font-medium">
                  {connectionError || 'Không thể kết nối đến Anki Desktop.'}
                </span>{' '}
                {onOpenGuide && (
                  <Button
                    type="button"
                    variant="link"
                    onClick={onOpenGuide}
                    className="p-0 h-auto font-bold text-primary hover:underline inline-flex items-center gap-0.5 cursor-pointer ml-1 text-[11px] sm:text-xs"
                  >
                    Xem hướng dẫn sửa lỗi kết nối / CORS &rarr;
                  </Button>
                )}
              </div>
            ) : (
              <p className="text-[11px] sm:text-xs text-muted-foreground mt-0.5 truncate max-w-xl">
                Kết nối trực tiếp Anki Desktop qua AnkiConnect (Port 8765 local).
              </p>
            )}
          </div>
        </div>

        {/* Right Input and Controls */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 w-full md:w-auto shrink-0 pt-2 md:pt-0 border-t md:border-t-0 border-border/60">
          <div className="flex-1 sm:w-44 md:w-52">
            <Input
              id={endpointInputId}
              value={endpoint}
              onChange={(e) => onEndpointChange(e.target.value)}
              placeholder="http://127.0.0.1:8765"
              className="h-8 text-xs font-mono bg-background/80"
            />
          </div>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={onCheckConnection}
              disabled={isCheckingConn}
              className="h-8 text-xs font-semibold flex-1 sm:flex-initial"
            >
              {isCheckingConn ? (
                <Loader2 className="size-3.5 animate-spin mr-1.5" />
              ) : (
                <RefreshCw className="size-3.5 mr-1.5" />
              )}
              Kiểm tra
            </Button>

            {onOpenGuide && !isConnected && (
              <Button
                size="sm"
                variant="secondary"
                onClick={onOpenGuide}
                className="h-8 text-xs font-semibold bg-amber-500/10 text-amber-700 hover:bg-amber-500/20 dark:text-amber-300 dark:hover:bg-amber-500/30 flex-1 sm:flex-initial shrink-0"
              >
                <HelpCircle className="size-3.5 mr-1 text-amber-500" />
                Sửa lỗi CORS
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
