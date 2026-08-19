import { useState } from 'react'
import {
  AlertTriangle,
  AudioLines,
  CheckCircle2,
  HelpCircle,
  Layers,
  ListPlus,
  LoaderCircle,
  Play,
  Plus,
  Radio,
  RefreshCw,
  Sparkles,
  Volume2,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { DeckAudioQueueMonitor } from '../components/DeckAudioQueueMonitor'
import { DeckAudioRuleCard } from '../components/DeckAudioRuleCard'
import { FlamaAudioConnectionGate } from '../components/FlamaAudioConnectionGate'
import { useDeckAudioQueue } from '../hooks/useDeckAudioQueue'
import { useDeckAudioScanner } from '../hooks/useDeckAudioScanner'

export function DeckAudioGeneratorPage() {
  const [isAudioHelperConnected, setIsAudioHelperConnected] = useState<boolean>(false)

  const scanner = useDeckAudioScanner()
  const queue = useDeckAudioQueue()

  const {
    decks,
    isDecksLoading,
    selectedDeckId,
    setSelectedDeckId,
    isScanning,
    scanData,
    handleScanDeck,
    generationMode,
    setGenerationMode,
    rules,
    availableFieldNames,
    handleAddRule,
    handleRemoveRule,
    handleUpdateRule,
    handleAddFieldMapping,
    handleRemoveFieldMapping,
    handleUpdateFieldMapping,
    buildJobFromCurrentConfig,
  } = scanner

  const {
    jobs,
    activeJob,
    addJobToQueue,
    pauseActiveJob,
    resumeJob,
    cancelJob,
    removeQueuedJob,
    clearCompleted,
  } = queue

  const handleStartOrQueue = () => {
    if (!isAudioHelperConnected) {
      toast.error('Vui lòng kết nối ứng dụng Flama Audio Desktop trước khi bắt đầu.')
      return
    }

    if (!selectedDeckId) {
      toast.error('Vui lòng chọn một bộ thẻ (Deck).')
      return
    }

    const job = buildJobFromCurrentConfig()
    if (!job) return

    addJobToQueue(job)
  }

  const sampleWord = scanData?.notes[0]?.word || 'こんにちは'

  return (
    <div className="container mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8 space-y-7">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-tr from-primary to-orange-400 text-white shadow-xs">
              <AudioLines className="size-5" />
            </div>
            <h1 className="text-xl sm:text-2xl font-black tracking-tight text-foreground">
              Studio Tạo Âm Thanh Deck
            </h1>
          </div>
          <p className="text-xs sm:text-sm text-muted-foreground">
            Quét thông minh trường từ vựng và tự động tổng hợp phát âm hàng loạt cho bộ thẻ qua Flama Audio Desktop.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-xs gap-1.5"
            asChild
          >
            <Link to="/guide/flama-audio" target="_blank">
              <HelpCircle className="size-3.5 text-muted-foreground" />
              <span>Hướng dẫn sử dụng</span>
            </Link>
          </Button>
        </div>
      </div>

      {/* Flama Audio Connection Banner */}
      <FlamaAudioConnectionGate onConnectionChange={setIsAudioHelperConnected} />

      {/* Section 1: Deck Selector & Smart Scan Stats */}
      <Card className="rounded-2xl border-border/70 shadow-xs">
        <CardHeader className="p-4 sm:p-5 border-b bg-muted/20">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <Layers className="size-4 text-primary" />
              <CardTitle className="text-sm sm:text-base font-bold text-foreground">
                1. Chọn bộ thẻ (Deck) &amp; Quét phân tích
              </CardTitle>
            </div>

            {selectedDeckId && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleScanDeck(selectedDeckId)}
                disabled={isScanning}
                className="h-8 text-xs gap-1.5"
              >
                <RefreshCw className={`size-3.5 ${isScanning ? 'animate-spin' : ''}`} />
                <span>Quét lại Deck</span>
              </Button>
            )}
          </div>
          <CardDescription className="text-xs text-muted-foreground mt-1">
            Chọn bộ thẻ bạn muốn tạo âm thanh. Hệ thống sẽ tự động quét các trường audio, đối soát trường gốc và kiểm tra file hỏng.
          </CardDescription>
        </CardHeader>

        <CardContent className="p-4 sm:p-5 space-y-5">
          {/* Deck Select Dropdown */}
          <div className="space-y-1.5 max-w-md">
            <Label className="text-xs font-semibold">Chọn Deck mục tiêu</Label>
            <NativeSelect
              value={selectedDeckId || ''}
              onChange={(e) => setSelectedDeckId(e.target.value ? Number(e.target.value) : null)}
              disabled={isDecksLoading || isScanning}
              className="h-10 text-xs sm:text-sm rounded-xl font-semibold"
            >
              <option value="">-- Chọn một bộ thẻ flashcard --</option>
              {decks.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </NativeSelect>
          </div>

          {/* Scanning Indicator */}
          {isScanning && (
            <div className="flex items-center gap-2 p-4 rounded-xl bg-muted/40 text-xs font-semibold text-primary animate-pulse">
              <LoaderCircle className="size-4 animate-spin" />
              <span>Đang phân tích cấu trúc thẻ và kiểm tra file âm thanh trong Deck...</span>
            </div>
          )}

          {/* Scan Results Stats */}
          {scanData && !isScanning && (
            <div className="space-y-4 pt-1">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {/* Total Notes */}
                <div className="p-3.5 rounded-xl bg-muted/30 border border-border/50 space-y-1">
                  <span className="text-[11px] font-medium text-muted-foreground">Tổng số từ trong Deck</span>
                  <p className="text-lg font-black text-foreground font-mono">
                    {scanData.total_notes}
                  </p>
                </div>

                {/* Needs Audio */}
                <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 space-y-1">
                  <span className="text-[11px] font-semibold text-amber-700 dark:text-amber-300 flex items-center gap-1">
                    <Sparkles className="size-3" />
                    Cần tạo âm thanh
                  </span>
                  <p className="text-lg font-black text-amber-700 dark:text-amber-300 font-mono">
                    {scanData.summary.needs_audio_count}
                  </p>
                </div>

                {/* Missing Audio */}
                <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 space-y-1">
                  <span className="text-[11px] font-semibold text-rose-700 dark:text-rose-300 flex items-center gap-1">
                    <Volume2 className="size-3" />
                    Chưa có âm thanh
                  </span>
                  <p className="text-lg font-black text-rose-700 dark:text-rose-300 font-mono">
                    {scanData.summary.missing_field_count}
                  </p>
                </div>

                {/* Broken Audio */}
                <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 space-y-1">
                  <span className="text-[11px] font-semibold text-amber-700 dark:text-amber-300 flex items-center gap-1">
                    <AlertTriangle className="size-3" />
                    File âm thanh lỗi/mất
                  </span>
                  <p className="text-lg font-black text-amber-700 dark:text-amber-300 font-mono">
                    {scanData.summary.broken_field_count}
                  </p>
                </div>
              </div>

              {/* Generation Mode Selector */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-xl bg-muted/20 border border-border/50">
                <div className="space-y-0.5">
                  <span className="text-xs font-bold text-foreground">
                    Chế độ áp dụng:
                  </span>
                  <p className="text-[11px] text-muted-foreground">
                    {generationMode === 'missing_and_broken'
                      ? 'Chỉ tạo cho các từ đang thiếu audio hoặc file âm thanh bị lỗi/mất (Tiết kiệm thời gian).'
                      : 'Tạo lại toàn bộ file âm thanh mới cho tất cả các từ trong Deck (Ghi đè).'}
                  </p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <Button
                    type="button"
                    variant={generationMode === 'missing_and_broken' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setGenerationMode('missing_and_broken')}
                    className="h-8 text-xs"
                  >
                    <CheckCircle2 className="size-3 mr-1" />
                    Chỉ bù thiếu &amp; hỏng
                  </Button>
                  <Button
                    type="button"
                    variant={generationMode === 'all' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setGenerationMode('all')}
                    className="h-8 text-xs"
                  >
                    Tạo lại tất cả
                  </Button>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Section 2: Audio Rules Configurator */}
      {scanData && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <h2 className="text-sm sm:text-base font-bold text-foreground flex items-center gap-2">
                <Volume2 className="size-4 text-primary" />
                <span>2. Thiết lập cấu hình giọng đọc &amp; Ánh xạ trường</span>
              </h2>
              <p className="text-xs text-muted-foreground">
                Tự động nhận diện từ đuôi &ldquo;Audio&rdquo; / &ldquo;_audio&rdquo;. Bạn có thể thêm cấu hình giọng đọc riêng cho từng trường (+ Thêm).
              </p>
            </div>

            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleAddRule}
              className="h-8 text-xs gap-1.5 border-primary/30 text-primary hover:bg-primary/10 font-semibold"
            >
              <Plus className="size-3.5" />
              <span>Thêm cấu hình giọng đọc</span>
            </Button>
          </div>

          {/* Rules List */}
          <div className="space-y-4">
            {rules.map((rule, idx) => (
              <DeckAudioRuleCard
                key={rule.id}
                rule={rule}
                index={idx}
                availableFieldNames={availableFieldNames}
                canDelete={rules.length > 1}
                sampleWord={sampleWord}
                onUpdateRule={handleUpdateRule}
                onDeleteRule={handleRemoveRule}
                onAddMapping={handleAddFieldMapping}
                onRemoveMapping={handleRemoveFieldMapping}
                onUpdateMapping={handleUpdateFieldMapping}
              />
            ))}
          </div>

          {/* Action Bar */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-4 rounded-2xl bg-muted/30 border border-border/70">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="bg-primary/10 text-primary border-primary/30 font-bold">
                {scanData.deck.name}
              </Badge>
              <span className="text-xs text-muted-foreground">
                Sẵn sàng tạo âm thanh với {rules.length} cấu hình giọng đọc
              </span>
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <Button
                type="button"
                size="sm"
                onClick={handleStartOrQueue}
                disabled={!isAudioHelperConnected}
                className="h-9 text-xs sm:text-sm font-bold gap-2 w-full sm:w-auto shadow-sm"
              >
                {activeJob ? (
                  <>
                    <ListPlus className="size-4" />
                    <span>Thêm Deck này vào hàng đợi</span>
                  </>
                ) : (
                  <>
                    <Play className="size-4" />
                    <span>Bắt đầu tạo âm thanh cho Deck này</span>
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Section 3: Queue & Live Progress Monitor */}
      <div className="space-y-4 pt-2">
        <div className="space-y-0.5">
          <h2 className="text-sm sm:text-base font-bold text-foreground flex items-center gap-2">
            <Radio className="size-4 text-primary" />
            <span>3. Tiến trình &amp; Hàng đợi nhiều Deck (Queue Monitor)</span>
          </h2>
          <p className="text-xs text-muted-foreground">
            Hệ thống tự động xử lý lần lượt từng Deck trong hàng đợi. Tiến trình được lưu liên tục và có thể tiếp tục khi tải lại trang web.
          </p>
        </div>

        <DeckAudioQueueMonitor
          jobs={jobs}
          activeJob={activeJob}
          onPause={pauseActiveJob}
          onResume={resumeJob}
          onCancel={cancelJob}
          onRemove={removeQueuedJob}
          onClearCompleted={clearCompleted}
        />
      </div>
    </div>
  )
}
