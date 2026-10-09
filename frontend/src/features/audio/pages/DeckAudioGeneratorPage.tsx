import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  AlertTriangle,
  AudioLines,
  CheckCircle2,
  Folder,
  Layers,
  ListPlus,
  LoaderCircle,
  Play,
  Plus,
  Radio,
  RefreshCw,
  Volume2,
} from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { ContextHelpButton } from '@/features/guide'
import { DeckSelectionTreeView } from '@/features/import/components/DeckSelectionTreeView'
import { DeckAudioQueueMonitor } from '../components/DeckAudioQueueMonitor'
import { DeckAudioRuleCard } from '../components/DeckAudioRuleCard'
import { FlamaAudioConnectionGate } from '../components/FlamaAudioConnectionGate'
import { useDeckAudioQueue } from '../hooks/useDeckAudioQueue'
import { useDeckAudioScanner } from '../hooks/useDeckAudioScanner'

export function DeckAudioGeneratorPage() {
  const { t } = useTranslation('audio')
  const [isAudioHelperConnected, setIsAudioHelperConnected] = useState<boolean>(false)

  const scanner = useDeckAudioScanner()
  const queue = useDeckAudioQueue()

  const {
    deckOptions,
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
    concurrency,
    setConcurrency,
    addJobToQueue,
    pauseActiveJob,
    resumeJob,
    cancelJob,
    removeQueuedJob,
    clearCompleted,
  } = queue

  const selectedDeck = deckOptions.find((d) => d.id === selectedDeckId)

  const handleStartOrQueue = () => {
    if (!isAudioHelperConnected) {
      toast.error(t('page.toast_connect_required'))
      return
    }

    if (!selectedDeckId) {
      toast.error(t('page.toast_select_deck_required'))
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
              {t('page.title')}
            </h1>
          </div>
          <p className="text-xs sm:text-sm text-muted-foreground">
            {t('page.subtitle')}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <ContextHelpButton
            guidePath="/guide/audio/batch-generation"
            guideTitle={t('page.guide_title')}
            troubleshootPath="/guide/troubleshooting/flama-audio"
            troubleshootTitle={t('page.troubleshoot_title')}
            label={t('page.help_label')}
          />
        </div>
      </div>

      {/* Flama Audio Connection Banner */}
      <FlamaAudioConnectionGate onConnectionChange={setIsAudioHelperConnected} />

      {/* Section 1: Deck Selector (Tree View) & Smart Scan Stats */}
      <Card className="rounded-2xl border-border/70 shadow-xs overflow-hidden">
        <CardHeader className="p-4 sm:p-5 border-b bg-muted/20">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <Layers className="size-4 text-primary" />
              <CardTitle className="text-sm sm:text-base font-bold text-foreground">
                {t('page.section_status')}
              </CardTitle>
            </div>

            {selectedDeckId && scanData && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleScanDeck(selectedDeckId)}
                disabled={isScanning}
                className="h-8 text-xs gap-1.5"
              >
                <RefreshCw className={`size-3.5 ${isScanning ? 'animate-spin' : ''}`} />
                <span>{t('page.scan_button')}</span>
              </Button>
            )}
          </div>
          <CardDescription className="text-xs text-muted-foreground mt-1">
            {t('page.section_deck_tree_desc')}
          </CardDescription>
        </CardHeader>

        <CardContent className="p-4 sm:p-5">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left: Deck Selection Tree (Deck Case) */}
            <div className="lg:col-span-5 space-y-2.5">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-bold text-foreground flex items-center gap-1.5">
                  <Folder className="size-3.5 text-amber-500" />
                  {t('page.section_deck_tree_label')}
                </Label>
                {selectedDeck && (
                  <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20 text-[11px] font-semibold truncate max-w-[200px]">
                    {selectedDeck.name}
                  </Badge>
                )}
              </div>
              <DeckSelectionTreeView
                deckOptions={deckOptions}
                selectedDeckId={selectedDeckId ? String(selectedDeckId) : ''}
                onSelectDeck={(id) => setSelectedDeckId(id ? Number(id) : null)}
              />
            </div>

            {/* Right: Scan Analysis Stats & Mode Settings */}
            <div className="lg:col-span-7 flex flex-col justify-center space-y-4">
              {!selectedDeckId ? (
                <div className="flex flex-col items-center justify-center border border-dashed border-border/80 rounded-2xl p-8 text-center bg-muted/10 min-h-[260px] h-full">
                  <div className="flex size-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground/60 mb-3">
                    <Layers className="size-6" />
                  </div>
                  <p className="text-sm font-bold text-foreground">{t('page.no_deck_selected_title')}</p>
                  <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                    {t('page.no_deck_selected_desc')}
                  </p>
                </div>
              ) : isScanning ? (
                <div className="flex flex-col items-center justify-center border border-primary/20 rounded-2xl p-8 text-center bg-primary/5 min-h-[260px] h-full space-y-3 animate-pulse">
                  <LoaderCircle className="size-8 text-primary animate-spin" />
                  <div className="space-y-1">
                    <p className="text-sm font-bold text-primary">{t('page.scanning_button')}</p>
                    <p className="text-xs text-muted-foreground max-w-sm">
                      {t('page.scanning_detail_desc')}
                    </p>
                  </div>
                </div>
              ) : scanData ? (
                <div className="space-y-4">
                  {/* Selected Deck Overview Info */}
                  <div className="flex items-center justify-between p-3.5 bg-muted/30 border border-border/60 rounded-2xl">
                    <div className="min-w-0">
                      <div className="text-[11px] text-muted-foreground font-medium">{t('page.selected_deck_processing')}</div>
                      <div className="text-sm font-bold text-foreground truncate">{scanData.deck.name}</div>
                    </div>
                    <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20 font-bold shrink-0">
                      {t('page.card_count_badge', { count: scanData.total_notes })}
                    </Badge>
                  </div>

                  {/* 4 Stat Cards */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                    {/* Total Notes */}
                    <div className="p-3 rounded-xl bg-muted/30 border border-border/50 space-y-0.5">
                      <span className="text-[10px] font-medium text-muted-foreground">{t('page.stat_total_notes')}</span>
                      <p className="text-base font-black text-foreground font-mono">
                        {scanData.total_notes}
                      </p>
                    </div>

                    {/* Needs Audio */}
                    <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 space-y-0.5">
                      <span className="text-[10px] font-semibold text-amber-700 dark:text-amber-300 flex items-center gap-1">
                        <AudioLines className="size-2.5" />
                        {t('page.stat_needs_audio')}
                      </span>
                      <p className="text-base font-black text-amber-700 dark:text-amber-300 font-mono">
                        {scanData.summary.needs_audio_count}
                      </p>
                    </div>

                    {/* Missing Audio */}
                    <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 space-y-0.5">
                      <span className="text-[10px] font-semibold text-rose-700 dark:text-rose-300 flex items-center gap-1">
                        <Volume2 className="size-2.5" />
                        {t('page.stat_missing_audio')}
                      </span>
                      <p className="text-base font-black text-rose-700 dark:text-rose-300 font-mono">
                        {scanData.summary.missing_field_count}
                      </p>
                    </div>

                    {/* Broken Audio */}
                    <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 space-y-0.5">
                      <span className="text-[10px] font-semibold text-amber-700 dark:text-amber-300 flex items-center gap-1">
                        <AlertTriangle className="size-2.5" />
                        {t('page.stat_broken_audio')}
                      </span>
                      <p className="text-base font-black text-amber-700 dark:text-amber-300 font-mono">
                        {scanData.summary.broken_field_count}
                      </p>
                    </div>
                  </div>

                  {/* Mode Selector */}
                  <div className="p-3.5 rounded-2xl border border-border/60 bg-card space-y-2">
                    <Label className="text-xs font-semibold">{t('page.mode_label')}</Label>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => setGenerationMode('missing_and_broken')}
                        className={`flex flex-col text-left p-3 rounded-xl border transition-all cursor-pointer ${
                          generationMode === 'missing_and_broken'
                            ? 'border-primary/50 bg-primary/10 text-primary ring-1 ring-primary/20 shadow-xs'
                            : 'border-border/60 hover:bg-muted/40'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold">{t('page.mode_missing_broken_title')}</span>
                          {generationMode === 'missing_and_broken' && <CheckCircle2 className="size-3.5 text-primary" />}
                        </div>
                        <span className="text-[11px] text-muted-foreground mt-1">
                          {t('page.mode_missing_broken_desc', { count: scanData.summary.needs_audio_count })}
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setGenerationMode('all')}
                        className={`flex flex-col text-left p-3 rounded-xl border transition-all cursor-pointer ${
                          generationMode === 'all'
                            ? 'border-primary/50 bg-primary/10 text-primary ring-1 ring-primary/20 shadow-xs'
                            : 'border-border/60 hover:bg-muted/40'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold">{t('page.mode_all_title')}</span>
                          {generationMode === 'all' && <CheckCircle2 className="size-3.5 text-primary" />}
                        </div>
                        <span className="text-[11px] text-muted-foreground mt-1">
                          {t('page.mode_all_desc', { count: scanData.total_notes })}
                        </span>
                      </button>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Section 2: Audio Rules Configurator */}
      {scanData && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <h2 className="text-sm sm:text-base font-bold text-foreground flex items-center gap-2">
                <Volume2 className="size-4 text-primary" />
                <span>{t('page.section_rules')}</span>
              </h2>
              <p className="text-xs text-muted-foreground">
                {t('page.rule_section_desc')}
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
              <span>{t('page.add_voice_rule_button')}</span>
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
                {t('page.ready_to_generate_status', { count: rules.length })}
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
                    <span>{t('page.add_to_queue_button')}</span>
                  </>
                ) : (
                  <>
                    <Play className="size-4" />
                    <span>{t('page.start_generation_button')}</span>
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
            <span>{t('page.section_progress')}</span>
          </h2>
          <p className="text-xs text-muted-foreground">
            {t('page.queue_section_desc')}
          </p>
        </div>

        <DeckAudioQueueMonitor
          jobs={jobs}
          activeJob={activeJob}
          concurrency={concurrency}
          onConcurrencyChange={setConcurrency}
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
