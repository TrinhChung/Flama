import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Checkbox } from '@/components/ui/checkbox'
import {
  AlertTriangle,
  Check,
  Eye,
  EyeOff,
  HelpCircle,
  LoaderCircle,
  Play,
  Volume2,
} from 'lucide-react'
import type { useBrowseState } from '../hooks/useBrowseState'

interface BrowseTtsModalProps {
  browse: ReturnType<typeof useBrowseState>
}

export function BrowseTtsModal({ browse }: BrowseTtsModalProps) {
  const {
    isTtsModalOpen,
    setIsTtsModalOpen,
    ttsVoicesQuery,
    ttsApiKey,
    setTtsApiKey,
    showApiKey,
    setShowApiKey,
    isKeySaved,
    isSavingKey,
    saveApiKeyIfValid,
    ttsCharacter,
    setTtsCharacter,
    ttsSourceField,
    setTtsSourceField,
    ttsDestinationField,
    setTtsDestinationField,
    ttsVolumeScale,
    setTtsVolumeScale,
    ttsPitch,
    setTtsPitch,
    ttsSpeed,
    setTtsSpeed,
    ttsIntonationScale,
    setTtsIntonationScale,
    ttsInitialSilence,
    setTtsInitialSilence,
    ttsFinalSilence,
    setTtsFinalSilence,
    ttsAppendAudio,
    setTtsAppendAudio,
    ttsUseOpus,
    setTtsUseOpus,
    handlePreviewVoiceVox,
    handleResetTtsDefaults,
    generateTtsMutation,
    targetTtsCardIds,
    selectedCards,
    selectedDeckId,
    selectedDeck,
    cards,
    isPreviewing,
    availableSourceFieldNames,
    availableAudioFieldNames,
  } = browse

  const availableVoices = ttsVoicesQuery.data?.items || []

  const isDeckScope = selectedCards.length === 0 && Boolean(selectedDeckId)
  const isMixedNoteTypes = isDeckScope && Boolean(selectedDeck?.has_mixed_note_types)
  const deckCardCount = selectedDeck?.counts?.total ?? cards.length
  const effectiveCardCount = isDeckScope ? deckCardCount : targetTtsCardIds.length

  const handleGenerate = () => {
    generateTtsMutation.mutate({
      card_ids: isDeckScope ? undefined : targetTtsCardIds,
      deck_id: isDeckScope && selectedDeckId ? selectedDeckId : undefined,
      source_field: ttsSourceField,
      destination_field: ttsDestinationField,
      character_id: ttsCharacter || undefined,
      api_key: ttsApiKey || undefined,
      append_audio: ttsAppendAudio,
      use_opus: ttsUseOpus,
      settings: {
        volume_scale: ttsVolumeScale,
        pitch: ttsPitch,
        speed_scale: ttsSpeed,
        intonation_scale: ttsIntonationScale,
        initial_silence: ttsInitialSilence,
        final_silence: ttsFinalSilence,
      },
    })
  }

  return (
    <Dialog open={isTtsModalOpen} onOpenChange={setIsTtsModalOpen}>
      <DialogContent className="w-[95vw] sm:max-w-xl max-h-[92vh] flex flex-col overflow-hidden p-0 rounded-xl sm:rounded-2xl border-border/60 shadow-2xl">
        <DialogHeader className="px-4 sm:px-6 py-3.5 border-b bg-muted/20 text-left shrink-0">
          <DialogTitle className="flex items-center gap-2 text-base sm:text-lg font-bold text-foreground">
            <Volume2 className="size-4.5 sm:size-5 text-primary shrink-0" />
            <span>Tạo âm thanh đọc thẻ (VoiceVox Web Service)</span>
          </DialogTitle>
          <DialogDescription className="text-xs mt-1 text-muted-foreground">
            Tích hợp dịch vụ TTS VoiceVox trên đám mây để tạo giọng đọc hàng loạt cho thẻ học của bạn.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-4 space-y-4 text-xs min-h-0">
          {/* Target Cards Selection Count banner */}
          <div className="p-3 bg-muted/40 border border-border/60 rounded-xl flex items-center justify-between shadow-3xs">
            <span className="font-semibold text-foreground">
              Phạm vi áp dụng:{' '}
              <strong className="text-primary font-bold ml-1">
                {isDeckScope
                  ? `Cả bộ deck "${selectedDeck?.name || 'này'}" (${deckCardCount} thẻ)`
                  : `${targetTtsCardIds.length} thẻ được chọn`}
              </strong>
            </span>
            <Badge variant="outline" className="text-[10px] bg-primary/5 text-primary border-primary/20 font-bold px-2.5 py-0.5 rounded-full shrink-0">
              {effectiveCardCount} thẻ {isDeckScope ? '(Cả deck)' : ''}
            </Badge>
          </div>

          {/* Mixed Note Types Warning Banner */}
          {isMixedNoteTypes && (
            <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-start gap-2.5 text-amber-800 dark:text-amber-200">
              <AlertTriangle className="size-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              <div className="text-xs space-y-0.5">
                <p className="font-bold">
                  Bộ deck đang chọn chứa nhiều note type nên không thể thực hiện thao tác.
                </p>
                <p className="text-[11px] text-amber-700/90 dark:text-amber-300/90">
                  {selectedDeck?.note_type_names?.length
                    ? `Các Note Type phát hiện: ${selectedDeck.note_type_names.join(', ')}.`
                    : ''}{' '}
                  Vui lòng chọn từng thẻ cụ thể hoặc chọn thư mục con có cùng một Note Type để tạo âm thanh đồng loạt.
                </p>
              </div>
            </div>
          )}

          {/* Web Service API Key Configuration */}
          <div className="space-y-2 p-3 bg-primary/5 rounded-xl border border-primary/10">
            <div className="flex items-center justify-between">
              <Label htmlFor="voicevox-api-key" className="text-xs font-bold text-primary">
                VoiceVox Web API Key
              </Label>
              <a
                href="https://voicevox.su-shiki.com/profile/"
                target="_blank"
                rel="noreferrer"
                className="text-[10px] font-semibold text-primary hover:underline flex items-center gap-0.5"
              >
                <span>Lấy khóa miễn phí</span>
                <HelpCircle className="size-3" />
              </a>
            </div>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input
                  id="voicevox-api-key"
                  type={showApiKey ? 'text' : 'password'}
                  placeholder="Dán API Key từ Su-Shiki VoiceVox…"
                  value={ttsApiKey}
                  onChange={(e) => setTtsApiKey(e.target.value)}
                  className="h-9 pr-9 rounded-lg text-xs bg-background"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 text-muted-foreground hover:text-foreground rounded-full hover:bg-muted"
                >
                  {showApiKey ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
                </button>
              </div>

              {ttsApiKey.trim() && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => saveApiKeyIfValid(ttsApiKey, true)}
                  disabled={isSavingKey}
                  className="h-9 font-semibold shrink-0"
                >
                  {isSavingKey ? (
                    <LoaderCircle className="size-3.5 animate-spin" />
                  ) : isKeySaved ? (
                    <Check className="size-3.5 text-green-600 mr-1 shrink-0" />
                  ) : null}
                  {isKeySaved ? 'Đã lưu' : 'Lưu Key'}
                </Button>
              )}
            </div>
            <p className="text-[10px] text-muted-foreground leading-relaxed">
              * Khóa được mã hóa lưu trữ bảo mật trên máy chủ đám mây. Bạn chỉ cần nhập một lần duy nhất.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {/* Character selection */}
            <div className="space-y-1.5">
              <Label htmlFor="voicevox-character" className="text-xs font-semibold">Giọng nhân vật (Character)</Label>
              <NativeSelect
                id="voicevox-character"
                value={ttsCharacter}
                onChange={(e) => setTtsCharacter(e.target.value)}
                disabled={ttsVoicesQuery.isPending}
                className="h-9 text-xs"
              >
                <option value="">Giọng mặc định (Zundamon Normal)</option>
                {ttsCharacter && !availableVoices.some((item) => String(item.id) === String(ttsCharacter)) && (
                  <option value={ttsCharacter}>
                    {ttsCharacter === '3' ? 'Zundamon Normal' : `Giọng đã chọn (#${ttsCharacter})`}
                  </option>
                )}
                {availableVoices.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </NativeSelect>
            </div>

            {/* Source & Destination Mapping fields */}
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5">
                <Label htmlFor="tts-source-field" className="text-xs font-semibold">Trường từ nguồn</Label>
                <NativeSelect
                  id="tts-source-field"
                  value={ttsSourceField}
                  onChange={(e) => setTtsSourceField(e.target.value)}
                  disabled={availableSourceFieldNames.length === 0}
                  className="h-9 text-xs"
                >
                  {availableSourceFieldNames.length === 0 ? (
                    <option value="">Note Type chưa có trường văn bản</option>
                  ) : (
                    <>
                      {ttsSourceField && !availableSourceFieldNames.includes(ttsSourceField) && (
                        <option value={ttsSourceField}>{ttsSourceField}</option>
                      )}
                      {availableSourceFieldNames.map((f) => (
                        <option key={f} value={f}>
                          {f}
                        </option>
                      ))}
                    </>
                  )}
                </NativeSelect>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="tts-dest-field" className="text-xs font-semibold">Trường ghi đè</Label>
                <NativeSelect
                  id="tts-dest-field"
                  value={ttsDestinationField}
                  onChange={(e) => setTtsDestinationField(e.target.value)}
                  disabled={availableAudioFieldNames.length === 0}
                  className="h-9 text-xs"
                >
                  {availableAudioFieldNames.length === 0 ? (
                    <option value="">Note Type chưa có trường audio</option>
                  ) : (
                    <>
                      {ttsDestinationField && !availableAudioFieldNames.includes(ttsDestinationField) && (
                        <option value={ttsDestinationField}>{ttsDestinationField}</option>
                      )}
                      {availableAudioFieldNames.map((f) => (
                        <option key={f} value={f}>
                          {f}
                        </option>
                      ))}
                    </>
                  )}
                </NativeSelect>
              </div>
            </div>
          </div>

          {/* Voice Advanced tuning Sliders */}
          <div className="space-y-3.5 pt-1">
            <div className="flex items-center justify-between text-xs font-bold">
              <span>Tinh chỉnh giọng đọc nâng cao</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleResetTtsDefaults}
                className="h-7 text-[10px] text-muted-foreground hover:text-primary rounded-md font-semibold"
              >
                Đặt lại mặc định
              </Button>
            </div>

            <div className="grid gap-3.5 sm:grid-cols-2">
              {/* Volume Scale */}
              <div className="p-3 bg-muted/20 border rounded-xl space-y-1.5 hover:border-primary/30 transition-colors">
                <div className="flex items-center justify-between text-[11px] font-medium text-foreground">
                  <span>Âm lượng</span>
                  <span className="font-mono font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded-md">
                    {ttsVolumeScale.toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.05"
                  className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  value={ttsVolumeScale}
                  onChange={(e) => setTtsVolumeScale(parseFloat(e.target.value))}
                />
              </div>

              {/* Pitch */}
              <div className="p-3 bg-muted/20 border rounded-xl space-y-1.5 hover:border-primary/30 transition-colors">
                <div className="flex items-center justify-between text-[11px] font-medium text-foreground">
                  <span>Cao độ (Pitch)</span>
                  <span className="font-mono font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded-md">
                    {ttsPitch.toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min="-0.15"
                  max="0.15"
                  step="0.01"
                  className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  value={ttsPitch}
                  onChange={(e) => setTtsPitch(parseFloat(e.target.value))}
                />
              </div>

              {/* Speed */}
              <div className="p-3 bg-muted/20 border rounded-xl space-y-1.5 hover:border-primary/30 transition-colors">
                <div className="flex items-center justify-between text-[11px] font-medium text-foreground">
                  <span>Tốc độ đọc</span>
                  <span className="font-mono font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded-md">
                    {ttsSpeed.toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="1.5"
                  step="0.05"
                  className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  value={ttsSpeed}
                  onChange={(e) => setTtsSpeed(parseFloat(e.target.value))}
                />
              </div>

              {/* Intonation Scale */}
              <div className="p-3 bg-muted/20 border rounded-xl space-y-1.5 hover:border-primary/30 transition-colors">
                <div className="flex items-center justify-between text-[11px] font-medium text-foreground">
                  <span>Luyến điệu (Intonation)</span>
                  <span className="font-mono font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded-md">
                    {ttsIntonationScale.toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.05"
                  className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  value={ttsIntonationScale}
                  onChange={(e) => setTtsIntonationScale(parseFloat(e.target.value))}
                />
              </div>
            </div>

            <div className="grid gap-3.5 sm:grid-cols-2">
              {/* Initial Silence */}
              <div className="p-3 bg-muted/20 border rounded-xl space-y-1.5 hover:border-primary/30 transition-colors">
                <div className="flex items-center justify-between text-[11px] font-medium text-foreground">
                  <span>Thời gian chờ đầu</span>
                  <span className="font-mono font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded-md">
                    {ttsInitialSilence.toFixed(2)}s
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1.5"
                  step="0.05"
                  className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  value={ttsInitialSilence}
                  onChange={(e) => setTtsInitialSilence(parseFloat(e.target.value))}
                />
              </div>

              {/* Final Silence */}
              <div className="p-3 bg-muted/20 border rounded-xl space-y-1.5 hover:border-primary/30 transition-colors">
                <div className="flex items-center justify-between text-[11px] font-medium text-foreground">
                  <span>Thời gian chờ cuối</span>
                  <span className="font-mono font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded-md">
                    {ttsFinalSilence.toFixed(2)}s
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1.5"
                  step="0.05"
                  className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  value={ttsFinalSilence}
                  onChange={(e) => setTtsFinalSilence(parseFloat(e.target.value))}
                />
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4 pt-1 text-xs">
            <label className="flex items-center gap-2 cursor-pointer font-medium">
              <Checkbox
                checked={ttsAppendAudio}
                onCheckedChange={(checked) => setTtsAppendAudio(Boolean(checked))}
              />
              <span>Chèn nối tiếp vào trường đích (thay vì ghi đè)</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer font-medium">
              <Checkbox
                checked={ttsUseOpus}
                onCheckedChange={(checked) => setTtsUseOpus(Boolean(checked))}
              />
              <span>Định dạng Opus nén cao (Khuyên dùng)</span>
            </label>
          </div>
        </div>

        <DialogFooter className="px-4 sm:px-6 py-4 border-t bg-muted/20 flex items-center justify-between gap-3 shrink-0">
          <Button variant="outline" size="sm" onClick={() => setIsTtsModalOpen(false)}>
            Đóng
          </Button>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handlePreviewVoiceVox}
              disabled={isPreviewing || generateTtsMutation.isPending}
            >
              {isPreviewing ? <LoaderCircle className="size-3.5 mr-1 animate-spin" /> : <Play className="size-3.5 mr-1" />}
              Nghe thử (Thẻ đầu)
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={handleGenerate}
              disabled={
                generateTtsMutation.isPending
                || isMixedNoteTypes
                || effectiveCardCount === 0
                || availableSourceFieldNames.length === 0
                || availableAudioFieldNames.length === 0
                || !ttsSourceField
                || !ttsDestinationField
              }
            >
              {generateTtsMutation.isPending ? <LoaderCircle className="size-3.5 mr-1 animate-spin" /> : null}
              Bắt đầu tạo ({effectiveCardCount} thẻ)
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
