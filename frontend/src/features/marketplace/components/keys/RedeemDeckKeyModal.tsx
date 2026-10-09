import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import {
  CheckCircle2,
  KeyRound,
  LoaderCircle,
  User,
  Clock,
  BookOpen,
} from 'lucide-react'
import { appApi } from '@/app/api'
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface KeyValidationResponse {
  valid: boolean
  error?: string
  already_installed?: boolean
  installed_deck_id?: number
  deck_item_id?: string
  title?: string
  description?: string
  primary_category?: string
  author?: string
  sample_cards_count?: number
  access_duration_days?: number | null
  expires_at?: string | null
}

interface RedeemResponse {
  success?: boolean
  already_installed?: boolean
  installed_deck_id?: number
  deck_item_id?: string
  title?: string
  access_expires_at?: string | null
  message?: string
}

interface RedeemDeckKeyModalProps {
  isOpen: boolean
  onClose: () => void
  initialKey?: string
  deckItemId?: string
}

export function RedeemDeckKeyModal({
  isOpen,
  onClose,
  initialKey = '',
}: RedeemDeckKeyModalProps) {
  const { t } = useTranslation('marketplace')
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [keyCode, setKeyCode] = useState(initialKey)
  const [validationData, setValidationData] = useState<KeyValidationResponse | null>(null)
  const [isValidating, setIsValidating] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successData, setSuccessData] = useState<RedeemResponse | null>(null)

  useEffect(() => {
    if (initialKey) {
      setKeyCode(initialKey.trim().toUpperCase())
      handleValidate(initialKey.trim().toUpperCase())
    }
  }, [initialKey])

  const handleValidate = async (codeToValidate: string) => {
    const clean = codeToValidate.trim().toUpperCase()
    if (!clean) {
      setValidationData(null)
      setErrorMessage(null)
      return
    }

    setIsValidating(true)
    setErrorMessage(null)
    try {
      const res = await appApi.mutate<KeyValidationResponse>(
        '/api/marketplace/keys/validate',
        'POST',
        { key_code: clean },
      )
      if (res.valid) {
        setValidationData(res)
        setErrorMessage(null)
      } else {
        setValidationData(null)
        setErrorMessage(res.error || t('redeem_modal.invalid_error', 'Mã kích hoạt không hợp lệ.'))
      }
    } catch (err: any) {
      setValidationData(null)
      setErrorMessage(err?.message || t('redeem_modal.invalid_or_expired', 'Mã kích hoạt không hợp lệ hoặc đã hết hạn.'))
    } finally {
      setIsValidating(false)
    }
  }

  const redeemMutation = useMutation({
    mutationFn: () =>
      appApi.mutate<RedeemResponse>('/api/marketplace/keys/redeem', 'POST', {
        key_code: keyCode.trim().toUpperCase(),
      }),
    onSuccess: (data: RedeemResponse) => {
      setSuccessData(data)
      queryClient.invalidateQueries({ queryKey: ['installed-decks'] })
      queryClient.invalidateQueries({ queryKey: ['shared-deck-detail'] })
      toast.success(data.message || t('redeem_modal.success_toast', 'Kích hoạt thành công!'))
    },
    onError: (err: any) => {
      toast.error(err?.message || t('common.error', 'Không thể kích hoạt mã. Vui lòng thử lại.'))
    },
  })

  const handleClose = () => {
    setKeyCode('')
    setValidationData(null)
    setErrorMessage(null)
    setSuccessData(null)
    onClose()
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-md rounded-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base sm:text-lg">
            <KeyRound className="size-5 text-primary" />
            {t('redeem_modal.title', 'Nhập Mã kích hoạt Bộ thẻ')}
          </DialogTitle>
          <DialogDescription className="text-xs">
            {t(
              'redeem_modal.desc',
              'Nhập mã truy cập nhận được từ giáo viên hoặc tác giả để tải bộ thẻ về tài khoản.'
            )}
          </DialogDescription>
        </DialogHeader>

        {successData ? (
          <div className="py-6 text-center space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="mx-auto size-14 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-500">
              <CheckCircle2 className="size-8" />
            </div>
            <div className="space-y-1.5">
              <h3 className="font-bold text-base text-foreground">
                {successData.already_installed
                  ? t('redeem_modal.ready_title', 'Bộ thẻ đã sẵn sàng!')
                  : t('redeem_modal.success_title', 'Kích hoạt thành công!')}
              </h3>
              <p className="text-xs text-muted-foreground max-w-xs mx-auto">
                {t('redeem_modal.installed_desc', {
                  title: successData.title,
                  defaultValue: `Bộ thẻ "${successData.title}" đã được cài đặt vào Thư viện học tập của bạn.`,
                })}
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={handleClose}
                className="rounded-xl flex-1 text-xs"
              >
                {t('redeem_modal.btn_close', 'Đóng')}
              </Button>
              <Button
                type="button"
                onClick={() => {
                  handleClose()
                  if (successData.installed_deck_id) {
                    navigate(`/study?deck_id=${successData.installed_deck_id}`)
                  } else {
                    navigate('/flashcards/installed-decks')
                  }
                }}
                className="rounded-xl flex-1 text-xs font-semibold gap-1.5 shadow-sm"
              >
                <BookOpen className="size-3.5" />
                {t('redeem_modal.btn_study_now', 'Vào học ngay')}
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4 py-2">
            {/* Input Key Code */}
            <div className="space-y-1.5">
              <Label htmlFor="input-key-code" className="text-xs font-semibold">
                {t('redeem_modal.key_label', 'Mã kích hoạt (Access Key)')}
              </Label>
              <div className="flex gap-2">
                <Input
                  id="input-key-code"
                  placeholder={t('redeem_modal.placeholder', 'VD: FLM-XXXX-XXXX-XXXX')}
                  value={keyCode}
                  onChange={(e) => {
                    const val = e.target.value.toUpperCase()
                    setKeyCode(val)
                    if (val.length >= 8) {
                      handleValidate(val)
                    } else {
                      setValidationData(null)
                      setErrorMessage(null)
                    }
                  }}
                  className="font-mono text-sm uppercase rounded-xl h-11 tracking-wider font-semibold"
                />
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => handleValidate(keyCode)}
                  disabled={!keyCode.trim() || isValidating}
                  className="rounded-xl h-11 px-4 text-xs font-semibold shrink-0"
                >
                  {isValidating ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    t('redeem_modal.btn_check', 'Kiểm tra')
                  )}
                </Button>
              </div>
              {errorMessage && (
                <p className="text-xs text-destructive font-medium mt-1 animate-in fade-in duration-150">
                  {errorMessage}
                </p>
              )}
            </div>

            {/* Deck Preview Card */}
            {validationData && validationData.valid && (
              <div className="rounded-2xl border border-primary/20 bg-primary/5 p-4 space-y-3 animate-in fade-in duration-200">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <Badge variant="outline" className="text-[10px] bg-primary/10 text-primary border-primary/20 mb-1">
                      {validationData.primary_category || t('redeem_modal.default_category', 'Lớp học')}
                    </Badge>
                    <h4 className="font-bold text-sm text-foreground line-clamp-1">
                      {validationData.title}
                    </h4>
                  </div>
                  {validationData.already_installed && (
                    <Badge className="bg-amber-500/15 text-amber-600 border-amber-500/30 text-[10px] shrink-0">
                      {t('redeem_modal.already_installed', 'Đã có trong thư viện')}
                    </Badge>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground pt-1 border-t border-border/40">
                  <div className="flex items-center gap-1.5">
                    <User className="size-3.5 text-primary" />
                    <span>
                      {t('redeem_modal.author_label', 'Tác giả:')}{' '}
                      <strong className="text-foreground">{validationData.author}</strong>
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Clock className="size-3.5 text-primary" />
                    <span>
                      {validationData.access_duration_days
                        ? t('redeem_modal.access_duration', {
                            days: validationData.access_duration_days,
                            defaultValue: `Học trong ${validationData.access_duration_days} ngày`,
                          })
                        : t('redeem_modal.access_forever', 'Học vĩnh viễn')}
                    </span>
                  </div>
                </div>
              </div>
            )}

            <DialogFooter className="gap-2 sm:gap-0 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={handleClose}
                className="rounded-xl"
              >
                {t('redeem_modal.btn_cancel', 'Hủy')}
              </Button>
              <Button
                type="button"
                onClick={() => redeemMutation.mutate()}
                disabled={!validationData?.valid || redeemMutation.isPending}
                className="rounded-xl font-semibold gap-1.5"
              >
                {redeemMutation.isPending ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <KeyRound className="size-4" />
                )}
                {t('redeem_modal.btn_confirm', 'Kích hoạt & Cài đặt')}
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
