import { Link } from 'react-router-dom'
import {
  AlertCircle,
  Cpu,
  Download,
  Sliders,
  Volume2,
  LoaderCircle,
  Play,
} from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Progress } from '@/components/ui/progress'

import { useLocalAudioEngine } from '../hooks/useLocalAudioEngine'
import { AudioAdvancedSettings } from './AudioAdvancedSettings'
import { BatchProgressList } from './BatchProgressList'

type LocalAudioDialogProps = {
  isOpen: boolean
  onClose: () => void
  selectedCardIds: string[]
  activeCardId?: string | null
  availableFieldNames?: string[]
  availableAudioFieldNames?: string[]
  noteTypeName?: string
  engineId?: 'voicevox' | 'kokoro'
  defaultVoiceId?: string
  onSuccess?: () => void
}

export function LocalAudioDialog(props: LocalAudioDialogProps) {
  const { isOpen, onClose, selectedCardIds, activeCardId } = props
  const engine = useLocalAudioEngine(props)
  
  const {
    isKokoro,
    targetCardIds,
    serviceStatus,
    pairingChallengeId,
    isPairingApproved,
    selectedVoiceId,
    setSelectedVoiceId,
    dynamicFields,
    dynamicAudioFields,
    sourceField,
    setSourceField,
    destinationField,
    setDestinationField,
    volumeScale,
    setVolumeScale,
    pitch,
    setPitch,
    speed,
    setSpeed,
    intonationScale,
    setIntonationScale,
    isPreviewing,
    isProcessing,
    progressPercent,
    items,
    engineOffline,
    engineActionState,
    groupedVoiceOptions,
    handleInstallEngine,
    handleLaunchEngine,
    handleResetDefaults,
    handlePreviewAudio,
    handleStartBatch,
    handleStartPairing,
  } = engine

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="w-[95vw] sm:max-w-3xl max-h-[92vh] flex flex-col overflow-hidden p-0 rounded-xl sm:rounded-2xl border-border/60 shadow-2xl">
        {/* Modal Header */}
        <DialogHeader className="px-3.5 sm:px-6 py-3 sm:py-4 border-b bg-muted/20 shrink-0 text-left">
          <div className="flex items-center justify-between gap-2">
            <DialogTitle className="flex items-center gap-2 text-base sm:text-lg font-bold text-foreground">
              <Volume2 className="size-4 sm:size-5 text-primary shrink-0" />
              <span>Tạo âm thanh &gt; {isKokoro ? 'Đa ngôn ngữ Offline' : 'Tiếng Nhật Offline'}</span>
            </DialogTitle>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs gap-1.5 border-primary/30 text-primary hover:bg-primary/10 font-semibold"
                asChild
              >
                <Link to="/guide/flama-audio" target="_blank">
                  <Download className="size-3.5" />
                  <span>Hướng dẫn &amp; Tải App</span>
                </Link>
              </Button>
              <Badge
                variant="outline"
                className="text-[11px] sm:text-xs font-semibold bg-emerald-500/10 text-emerald-600 border-emerald-500/30 px-2 py-0.5 shrink-0"
              >
                {targetCardIds.length} thẻ
              </Badge>
            </div>
          </div>
          <DialogDescription className="text-xs text-muted-foreground mt-1">
            Tổng hợp giọng phát âm tự nhiên trực tiếp không cần mạng Internet thông qua ứng dụng Flama Audio Desktop.
          </DialogDescription>
        </DialogHeader>

        {/* Modal Body Scrollable */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5 text-xs min-h-0">
          {/* Target Card Scope Banner */}
          <div className="p-4 rounded-xl bg-muted/40 border border-border/60 flex items-center justify-between shadow-xs">
            <span className="font-semibold text-foreground text-xs">
              Phạm vi áp dụng:{' '}
              <strong className="text-primary font-bold ml-1">
                {selectedCardIds.length > 0
                  ? `${selectedCardIds.length} thẻ đã tick chọn`
                  : activeCardId
                    ? '1 thẻ đang chọn trong bảng'
                    : 'Chưa chọn thẻ nào trong bảng'}
              </strong>
            </span>
            <Badge
              variant={targetCardIds.length > 0 ? 'default' : 'destructive'}
              className="text-[11px] px-2.5 py-0.5"
            >
              {targetCardIds.length > 0 ? `${targetCardIds.length} thẻ` : 'Chưa chọn'}
            </Badge>
          </div>

          {/* Service Connection Status Banners */}
          {serviceStatus === 'checking' && (
            <div className="flex items-center gap-2 p-3.5 bg-muted/50 rounded-xl text-xs">
              <LoaderCircle className="size-4 animate-spin text-primary" />
              Đang kết nối tới ứng dụng phát âm Flama Audio Desktop...
            </div>
          )}

          {serviceStatus === 'offline' && (
            <Alert variant="destructive" className="rounded-xl">
              <AlertCircle className="size-4" />
              <AlertTitle className="font-bold">Chưa mở ứng dụng phát âm Flama Audio</AlertTitle>
              <AlertDescription className="text-xs leading-relaxed space-y-2 mt-1">
                <p>
                  Tính năng phát âm offline yêu cầu ứng dụng helper <strong>Flama Audio Desktop</strong> chạy song song trên thiết bị của bạn.
                </p>
                <div className="pt-2 flex items-center gap-2">
                  <Button variant="outline" size="sm" className="bg-white text-destructive border-destructive/20 hover:bg-rose-50" asChild>
                    <Link to="/guide/flama-audio" target="_blank">
                      Tải ứng dụng Desktop
                    </Link>
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => engine.checkHealthAndInit()} className="text-destructive hover:bg-destructive/10">
                    Thử kết nối lại
                  </Button>
                </div>
              </AlertDescription>
            </Alert>
          )}

          {serviceStatus === 'online' && !isPairingApproved && (
            <Alert className="border-amber-500/30 bg-amber-500/5 rounded-xl">
              <Cpu className="size-4 text-amber-600 dark:text-amber-400 shrink-0" />
              <AlertTitle className="font-bold text-amber-900 dark:text-amber-200">
                Chờ xác nhận ghép nối thiết bị
              </AlertTitle>
              <AlertDescription className="text-xs leading-relaxed mt-1.5 space-y-2">
                <p>
                  Mở ứng dụng <strong>Flama Audio Desktop</strong> và bấm nút{' '}
                  <strong className="text-amber-700 dark:text-amber-300">Đồng ý ghép nối (Pair)</strong> cho thiết bị có mã số dưới đây:
                </p>
                <div className="flex items-center gap-3">
                  <code className="bg-amber-500/10 text-amber-800 dark:text-amber-300 px-3 py-1.5 rounded-lg font-mono text-sm font-bold border border-amber-500/20 select-all">
                    {pairingChallengeId || 'Đang tạo mã...'}
                  </code>
                  <Button variant="ghost" size="sm" onClick={handleStartPairing} className="text-amber-700 hover:bg-amber-500/10 h-8">
                    Gửi lại yêu cầu
                  </Button>
                </div>
              </AlertDescription>
            </Alert>
          )}

          {/* Config options & Engine State */}
          {serviceStatus === 'online' && isPairingApproved && (
            <div className="space-y-4 pt-1">
              <div className="grid gap-3.5 sm:grid-cols-2">
                {/* Voice Selection */}
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold">Giọng phát âm ({isKokoro ? 'Kokoro' : 'VOICEVOX'})</Label>
                  <NativeSelect
                    value={selectedVoiceId}
                    onChange={(e) => setSelectedVoiceId(e.target.value)}
                    disabled={isProcessing}
                    className="h-10 text-xs sm:text-sm rounded-xl"
                  >
                    {Object.entries(groupedVoiceOptions).map(([groupName, options]) => (
                      <optgroup key={groupName} label={groupName}>
                        {options.map((opt) => (
                          <option key={opt.id} value={opt.id}>
                            {opt.label}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </NativeSelect>
                </div>

                {/* Fields Selection Mapping */}
                <div className="grid grid-cols-2 gap-2.5">
                  <div className="space-y-1.5">
                    <Label className="text-xs font-semibold">Cột nguồn từ</Label>
                    <NativeSelect
                      value={sourceField}
                      onChange={(e) => setSourceField(e.target.value)}
                      disabled={isProcessing || dynamicFields.length === 0}
                      className="h-10 text-xs sm:text-sm rounded-xl"
                    >
                      {dynamicFields.length === 0 ? (
                        <option value="">Note Type chưa có trường văn bản</option>
                      ) : dynamicFields.map((f) => (
                          <option key={f} value={f}>
                            {f}
                          </option>
                        ))}
                    </NativeSelect>
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs font-semibold">Ghi file audio vào</Label>
                    <NativeSelect
                      value={destinationField}
                      onChange={(e) => setDestinationField(e.target.value)}
                      disabled={isProcessing || dynamicAudioFields.length === 0}
                      className="h-10 text-xs sm:text-sm rounded-xl"
                    >
                      {dynamicAudioFields.length === 0 ? (
                        <option value="">Note Type chưa có trường audio</option>
                      ) : dynamicAudioFields.map((f) => (
                          <option key={f} value={f}>
                            {f}
                          </option>
                        ))}
                    </NativeSelect>
                  </div>
                </div>
              </div>

              {/* Engine Offline Helper Box */}
              {engineOffline && (
                <Alert variant="destructive" className="rounded-xl p-3.5">
                  <AlertCircle className="size-4 shrink-0" />
                  <div className="space-y-2">
                    <AlertTitle className="font-bold text-xs sm:text-sm">
                      {isKokoro ? 'Kokoro Engine offline' : 'VOICEVOX Engine offline'}
                    </AlertTitle>
                    <AlertDescription className="text-xs leading-relaxed">
                      {isKokoro
                        ? 'Kokoro Engine chưa được cài đặt hoặc khởi chạy trong ứng dụng Desktop.'
                        : 'Không kết nối được với VOICEVOX Engine. Có thể Engine chưa được tải hoặc bị tắt.'}
                      <div className="pt-2 flex items-center gap-2">
                        {engineActionState === 'idle' ? (
                          <>
                            <Button size="sm" variant="outline" className="bg-white text-destructive border-destructive/20 hover:bg-rose-50" onClick={handleLaunchEngine}>
                              Kích hoạt Engine
                            </Button>
                            <Button size="sm" variant="ghost" className="text-destructive hover:bg-destructive/10" onClick={handleInstallEngine}>
                              Tải &amp; Cài đặt Engine (Cần ~1.5GB)
                            </Button>
                          </>
                        ) : (
                          <span className="flex items-center gap-2 text-xs font-semibold text-destructive">
                            <LoaderCircle className="size-4 animate-spin text-destructive" />
                            {engineActionState === 'installing' ? 'Đang cài đặt Engine...' : 'Đang khởi chạy Engine...'}
                          </span>
                        )}
                      </div>
                    </AlertDescription>
                  </div>
                </Alert>
              )}

              {/* Slider Settings Accordion Block */}
              <div className="space-y-2.5 pt-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-bold text-foreground">
                    <Sliders className="size-4 text-primary" />
                    <span>Cấu hình thông số giọng đọc nâng cao</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 text-xs font-semibold text-muted-foreground hover:text-primary"
                    onClick={handleResetDefaults}
                    disabled={isProcessing}
                  >
                    Khôi phục mặc định
                  </Button>
                </div>

                <AudioAdvancedSettings
                  volumeScale={volumeScale}
                  setVolumeScale={setVolumeScale}
                  pitch={pitch}
                  setPitch={setPitch}
                  speed={speed}
                  setSpeed={setSpeed}
                  intonationScale={intonationScale}
                  setIntonationScale={setIntonationScale}
                  isProcessing={isProcessing}
                />
              </div>
            </div>
          )}

          {/* Progress Indicator */}
          {isProcessing && (
            <div className="space-y-2 border p-4 rounded-xl bg-muted/30">
              <div className="flex justify-between text-xs font-semibold">
                <span>Đang tổng hợp phát âm VOICEVOX Local...</span>
                <span className="font-mono">{progressPercent}%</span>
              </div>
              <Progress value={progressPercent} className="h-2" />
            </div>
          )}

          {/* Batch Status List */}
          {items.length > 0 && <BatchProgressList items={items} />}
        </div>

        {/* Modal Footer */}
        <DialogFooter className="px-4 sm:px-6 pt-4 pb-6 sm:pb-7 mb-0 border-t bg-muted/20 shrink-0 flex items-center justify-between gap-3">
          <Button variant="outline" size="sm" onClick={onClose} disabled={isProcessing}>
            Đóng
          </Button>

          <div className="flex items-center gap-2">
            {serviceStatus === 'online' && isPairingApproved && (
              <>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-9 text-xs gap-1.5"
                  onClick={handlePreviewAudio}
                  disabled={isPreviewing || isProcessing}
                >
                  {isPreviewing ? <LoaderCircle className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
                  <span>Nghe thử phát âm</span>
                </Button>

                <Button
                  type="button"
                  size="sm"
                  className="h-9 text-xs gap-1.5"
                  onClick={handleStartBatch}
                  disabled={
                    isProcessing
                    || targetCardIds.length === 0
                    || !sourceField
                    || !destinationField
                  }
                >
                  {isProcessing ? (
                    <LoaderCircle className="size-3.5 animate-spin" />
                  ) : (
                    <Volume2 className="size-3.5" />
                  )}
                  <span>Tạo audio ({targetCardIds.length} thẻ)</span>
                </Button>
              </>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
