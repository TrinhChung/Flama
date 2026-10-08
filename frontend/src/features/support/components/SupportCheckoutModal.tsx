import {
  Check,
  Copy,
  CreditCard,
  ExternalLink,
  Heart,
  QrCode,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog'
import type { CheckoutResult, SupportDonation } from '../types'

interface SupportCheckoutModalProps {
  isOpen: boolean
  onOpenChange: (open: boolean) => void
  activeCheckout: CheckoutResult | null
  amount: number
  support: SupportDonation
  modalStatusQuery: any
  copiedField: string | null
  onCopy: (text: string, fieldName: string) => void
  onSuccessClose: () => void
}

export function SupportCheckoutModal({
  isOpen,
  onOpenChange,
  activeCheckout,
  amount,
  support,
  modalStatusQuery,
  copiedField,
  onCopy,
  onSuccessClose,
}: SupportCheckoutModalProps) {
  const { t } = useTranslation('support')
  const isPaid = modalStatusQuery.data?.status === 'paid'

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md p-0 overflow-hidden border-primary/20 shadow-2xl rounded-2xl sm:rounded-3xl">
        {/* Header with gradient */}
        <div className="bg-gradient-to-r from-primary via-orange-500 to-amber-500 p-4 sm:p-5 text-primary-foreground">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="flex size-8 items-center justify-center rounded-lg bg-white/20 backdrop-blur-sm">
                <CreditCard className="size-4 text-white" />
              </span>
              <div>
                <DialogTitle className="text-base sm:text-lg font-bold text-white leading-tight">
                  {t('donation.modal.title')}
                </DialogTitle>
                <DialogDescription className="text-xs text-white/80">
                  {t('donation.modal.subtitle')}
                </DialogDescription>
              </div>
            </div>
            <Badge
              variant="secondary"
              className="bg-white/20 text-white border-0 text-[11px] font-semibold"
            >
              <ShieldCheck className="size-3 mr-1" /> {t('donation.modal.safe_badge')}
            </Badge>
          </div>
        </div>

        <div className="p-4 sm:p-6 space-y-4 max-h-[80vh] overflow-y-auto">
          {isPaid ? (
            /* Success Celebration View */
            <div className="py-6 flex flex-col items-center text-center space-y-4">
              <div className="relative">
                <div className="absolute -inset-2 bg-emerald-500/20 rounded-full blur-xl animate-pulse" />
                <span className="relative flex size-20 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/30 shadow-inner">
                  <Heart className="size-10 fill-emerald-500 text-emerald-500 animate-bounce" />
                </span>
              </div>
              <div className="space-y-1.5">
                <Badge
                  variant="outline"
                  className="border-emerald-500/30 text-emerald-700 bg-emerald-500/10 text-xs px-2.5 py-0.5 font-bold"
                >
                  {t('donation.modal.success_badge')}
                </Badge>
                <h3 className="text-lg sm:text-xl font-black text-foreground">
                  {t('donation.modal.success_title')}
                </h3>
                <p className="text-xs sm:text-sm text-muted-foreground max-w-xs mx-auto leading-relaxed">
                  {t('donation.modal.success_desc')}
                </p>
              </div>

              <div className="w-full rounded-2xl border bg-muted/30 p-4 space-y-2 text-xs">
                <div className="flex justify-between items-center border-b pb-2">
                  <span className="text-muted-foreground">
                    {t('donation.modal.donated_amount')}
                  </span>
                  <span className="font-bold text-primary text-base">
                    {(
                      modalStatusQuery.data?.total_amount_minor ||
                      activeCheckout?.checkout?.amount_minor ||
                      amount
                    ).toLocaleString('vi-VN')}{' '}
                    VND
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">
                    {t('donation.modal.order_code')}
                  </span>
                  <span className="font-mono font-semibold">
                    #
                    {modalStatusQuery.data?.merchant_order_code ||
                      activeCheckout?.checkout?.merchant_order_code ||
                      '—'}
                  </span>
                </div>
              </div>

              <Button
                className="w-full font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20"
                onClick={onSuccessClose}
              >
                {t('donation.modal.complete')}
              </Button>
            </div>
          ) : (
            /* QR Code & Transfer Instructions View */
            <>
              {/* Amount Banner */}
              <div className="flex items-center justify-between rounded-xl bg-primary/10 border border-primary/20 p-3">
                <div>
                  <span className="text-[10px] uppercase font-bold text-muted-foreground">
                    {t('donation.modal.amount_to_transfer')}
                  </span>
                  <p className="text-lg font-black text-primary leading-tight">
                    {(
                      activeCheckout?.checkout?.amount_minor || amount
                    ).toLocaleString('vi-VN')}{' '}
                    VND
                  </p>
                </div>
                {activeCheckout?.checkout?.merchant_order_code && (
                  <span className="font-mono text-xs text-muted-foreground">
                    #{activeCheckout.checkout.merchant_order_code}
                  </span>
                )}
              </div>

              {/* QR Code Container */}
              <div className="flex flex-col items-center justify-center rounded-2xl border bg-card p-3 shadow-inner">
                {(() => {
                  const ch = activeCheckout?.checkout
                  let qrSrc = support.qr_image_url
                  if (
                    ch?.qr_code &&
                    (ch.qr_code.startsWith('http') || ch.qr_code.startsWith('data:'))
                  ) {
                    qrSrc = ch.qr_code
                  } else if (ch?.bank_bin && ch?.account_no) {
                    const ref = ch.payment_reference || ''
                    const accName = ch.account_name || support.account_name || ''
                    const amt = ch.amount_minor || amount
                    qrSrc = `https://img.vietqr.io/image/${ch.bank_bin}-${ch.account_no}-compact2.png?amount=${amt}&addInfo=${encodeURIComponent(
                      ref
                    )}&accountName=${encodeURIComponent(accName)}`
                  }
                  return qrSrc ? (
                    <div className="relative group">
                      <img
                        src={qrSrc}
                        alt={t('donation.modal.vietqr_alt', 'Mã VietQR thanh toán')}
                        className="size-52 sm:size-60 rounded-xl border bg-white p-2 shadow-sm object-contain mx-auto"
                      />
                    </div>
                  ) : (
                    <div className="size-52 flex items-center justify-center text-muted-foreground text-xs">
                      {t('donation.modal.qr_generating')}
                    </div>
                  )
                })()}
                <p className="mt-2 text-[11px] text-muted-foreground flex items-center gap-1">
                  <QrCode className="size-3.5" /> {t('donation.modal.qr_scan_hint')}
                </p>
              </div>

              {/* Account Details with Copy Buttons */}
              <div className="space-y-2 text-xs">
                {/* Bank Account */}
                <div className="flex items-center justify-between rounded-xl border bg-muted/40 p-2.5">
                  <div>
                    <span className="text-[10px] text-muted-foreground font-semibold uppercase block">
                      {t('donation.modal.bank_account')}
                    </span>
                    <span className="font-mono font-bold text-sm text-foreground">
                      {activeCheckout?.checkout?.account_no || support.account_number}
                    </span>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 px-2 text-xs"
                    onClick={() =>
                      onCopy(
                        activeCheckout?.checkout?.account_no || support.account_number,
                        t('donation.modal.bank_account')
                      )
                    }
                  >
                    {copiedField === t('donation.modal.bank_account') ? (
                      <Check className="size-3.5 text-emerald-600 mr-1" />
                    ) : (
                      <Copy className="size-3.5 text-muted-foreground mr-1" />
                    )}
                    {t('donation.manual_card.copy')}
                  </Button>
                </div>

                {/* Transfer Reference / Content */}
                {activeCheckout?.checkout?.payment_reference && (
                  <div className="flex items-center justify-between rounded-xl border-2 border-primary/30 bg-primary/5 p-2.5">
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] text-primary font-bold uppercase">
                          {t('donation.modal.transfer_reference')}
                        </span>
                        <Badge variant="destructive" className="h-4 px-1 text-[9px]">
                          {t('donation.modal.required_badge')}
                        </Badge>
                      </div>
                      <span className="font-mono font-bold text-sm text-primary tracking-wide">
                        {activeCheckout.checkout.payment_reference}
                      </span>
                    </div>
                    <Button
                      size="sm"
                      variant="default"
                      className="h-7 px-2.5 text-xs font-bold"
                      onClick={() =>
                        onCopy(
                          activeCheckout.checkout?.payment_reference || '',
                          t('donation.modal.transfer_reference')
                        )
                      }
                    >
                      {copiedField === t('donation.modal.transfer_reference') ? (
                        <Check className="size-3.5 text-white mr-1" />
                      ) : (
                        <Copy className="size-3.5 text-white mr-1" />
                      )}
                      {t('donation.manual_card.copy')}
                    </Button>
                  </div>
                )}

                {/* Account Name */}
                <div className="flex items-center justify-between rounded-xl border bg-muted/40 p-2.5">
                  <div>
                    <span className="text-[10px] text-muted-foreground font-semibold uppercase block">
                      {t('donation.manual_card.account_name')}
                    </span>
                    <span className="font-semibold text-xs text-foreground">
                      {activeCheckout?.checkout?.account_name || support.account_name}
                    </span>
                  </div>
                </div>
              </div>

              {/* Real-time Status Card with Pulse */}
              <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="relative flex size-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full size-3 bg-amber-500"></span>
                  </span>
                  <div className="text-xs text-amber-800 dark:text-amber-300">
                    <p className="font-semibold leading-none">
                      {t('donation.modal.waiting_title')}
                    </p>
                    <p className="text-[11px] opacity-80 mt-0.5">
                      {t('donation.modal.waiting_desc')}
                    </p>
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 px-2 text-[11px] gap-1"
                  disabled={modalStatusQuery.isFetching}
                  onClick={() => modalStatusQuery.refetch()}
                >
                  <RefreshCw
                    className={`size-3 ${
                      modalStatusQuery.isFetching ? 'animate-spin' : ''
                    }`}
                  />
                  {t('donation.modal.check_status')}
                </Button>
              </div>

              {/* Footer Buttons */}
              <div className="space-y-2 pt-2">
                {(activeCheckout?.checkout_url ||
                  activeCheckout?.checkout?.checkout_url) && (
                  <Button
                    variant="outline"
                    size="sm"
                    asChild
                    className="w-full text-xs text-muted-foreground hover:text-foreground h-9"
                  >
                    <a
                      href={
                        activeCheckout.checkout_url ||
                        activeCheckout.checkout?.checkout_url ||
                        '#'
                      }
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-center gap-1.5"
                    >
                      <span>{t('donation.modal.open_payos')}</span>
                      <ExternalLink className="size-3.5" />
                    </a>
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full text-xs text-muted-foreground h-8"
                  onClick={() => onOpenChange(false)}
                >
                  {t('donation.modal.close')}
                </Button>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
