import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Check, Eye, EyeOff, HelpCircle, LoaderCircle } from 'lucide-react'

export interface BrowseTtsFieldMappingProps {
  ttsApiKey: string
  setTtsApiKey: (val: string) => void
  showApiKey: boolean
  setShowApiKey: (val: boolean) => void
  isKeySaved: boolean
  isSavingKey: boolean
  saveApiKeyIfValid: (key: string, force?: boolean) => void
  ttsCharacter: string
  setTtsCharacter: (val: string) => void
  ttsVoicesPending: boolean
  availableVoices: Array<{ id: string | number; label: string }>
  ttsSourceField: string
  setTtsSourceField: (val: string) => void
  availableSourceFieldNames: string[]
  ttsDestinationField: string
  setTtsDestinationField: (val: string) => void
  availableAudioFieldNames: string[]
}

export function BrowseTtsFieldMapping({
  ttsApiKey,
  setTtsApiKey,
  showApiKey,
  setShowApiKey,
  isKeySaved,
  isSavingKey,
  saveApiKeyIfValid,
  ttsCharacter,
  setTtsCharacter,
  ttsVoicesPending,
  availableVoices,
  ttsSourceField,
  setTtsSourceField,
  availableSourceFieldNames,
  ttsDestinationField,
  setTtsDestinationField,
  availableAudioFieldNames,
}: BrowseTtsFieldMappingProps) {
  const { t } = useTranslation('browse')

  return (
    <>
      {/* Web Service API Key Configuration */}
      <div className="space-y-2 p-3 bg-primary/5 rounded-xl border border-primary/10">
        <div className="flex items-center justify-between">
          <Label htmlFor="voicevox-api-key" className="text-xs font-bold text-primary">
            {t('tts_modal.api_key_label')}
          </Label>
          <a
            href="https://voicevox.su-shiki.com/profile/"
            target="_blank"
            rel="noreferrer"
            className="text-[10px] font-semibold text-primary hover:underline flex items-center gap-0.5"
          >
            <span>{t('tts_modal.get_key_free')}</span>
            <HelpCircle className="size-3" />
          </a>
        </div>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Input
              id="voicevox-api-key"
              type={showApiKey ? 'text' : 'password'}
              placeholder={t('tts_modal.api_key_placeholder')}
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
              {isKeySaved ? t('tts_modal.key_saved') : t('tts_modal.save_key')}
            </Button>
          )}
        </div>
        <p className="text-[10px] text-muted-foreground leading-relaxed">
          {t('tts_modal.api_key_note')}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {/* Character selection */}
        <div className="space-y-1.5">
          <Label htmlFor="voicevox-character" className="text-xs font-semibold">
            {t('tts_modal.character_label')}
          </Label>
          <NativeSelect
            id="voicevox-character"
            value={ttsCharacter}
            onChange={(e) => setTtsCharacter(e.target.value)}
            disabled={ttsVoicesPending}
            className="h-9 text-xs"
          >
            <option value="">{t('tts_modal.default_voice')}</option>
            {ttsCharacter && !availableVoices.some((item) => String(item.id) === String(ttsCharacter)) && (
              <option value={ttsCharacter}>
                {ttsCharacter === '3' ? 'Zundamon Normal' : t('tts_modal.selected_voice', { id: ttsCharacter })}
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
            <Label htmlFor="tts-source-field" className="text-xs font-semibold">
              {t('tts_modal.source_field_label')}
            </Label>
            <NativeSelect
              id="tts-source-field"
              value={ttsSourceField}
              onChange={(e) => setTtsSourceField(e.target.value)}
              disabled={availableSourceFieldNames.length === 0}
              className="h-9 text-xs"
            >
              {availableSourceFieldNames.length === 0 ? (
                <option value="">{t('tts_modal.no_text_field')}</option>
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
            <Label htmlFor="tts-dest-field" className="text-xs font-semibold">
              {t('tts_modal.dest_field_label')}
            </Label>
            <NativeSelect
              id="tts-dest-field"
              value={ttsDestinationField}
              onChange={(e) => setTtsDestinationField(e.target.value)}
              disabled={availableAudioFieldNames.length === 0}
              className="h-9 text-xs"
            >
              {availableAudioFieldNames.length === 0 ? (
                <option value="">{t('tts_modal.no_audio_field')}</option>
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
    </>
  )
}
