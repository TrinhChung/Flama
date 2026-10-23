import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Eye, EyeOff, KeyRound, LoaderCircle } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Button } from '@/components/ui/button'
import { DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  type ChangePasswordFormValues,
  type PasswordFieldErrors,
  getChangePasswordSchema,
} from '../schemas'

export interface ProfileEditPasswordTabProps {
  isPending: boolean
  fieldErrors: PasswordFieldErrors
  setFieldErrors: React.Dispatch<React.SetStateAction<PasswordFieldErrors>>
  onCancel: () => void
  onSave: (payload: {
    current_password: string
    new_password: string
    confirm_password: string
  }) => void
}

export function ProfileEditPasswordTab({
  isPending,
  fieldErrors,
  setFieldErrors,
  onCancel,
  onSave,
}: ProfileEditPasswordTabProps) {
  const { t } = useTranslation('profile')

  const [showCurrentPw, setShowCurrentPw] = useState(false)
  const [showNewPw, setShowNewPw] = useState(false)
  const [showConfirmPw, setShowConfirmPw] = useState(false)

  const schema = getChangePasswordSchema(t)

  const {
    register,
    handleSubmit,
    formState: { errors: formErrors, isSubmitted, isValid },
  } = useForm<ChangePasswordFormValues>({
    resolver: zodResolver(schema),
    mode: 'onChange',
    defaultValues: {
      current_password: '',
      new_password: '',
      confirm_password: '',
    },
  })

  const onSubmit = (data: ChangePasswordFormValues) => {
    setFieldErrors({})
    onSave(data)
  }

  const { onChange: onCurrentPwChange, ...currentPwReg } = register('current_password')
  const { onChange: onNewPwChange, ...newPwReg } = register('new_password')
  const { onChange: onConfirmPwChange, ...confirmPwReg } = register('confirm_password')

  const currentPwError = fieldErrors.current_password || formErrors.current_password?.message
  const newPwError = fieldErrors.new_password || formErrors.new_password?.message
  const confirmPwError = fieldErrors.confirm_password || formErrors.confirm_password?.message

  return (
    <form noValidate onSubmit={handleSubmit(onSubmit)} className="space-y-4 pt-2">
      <div className="space-y-1.5">
        <Label htmlFor="profile-cur-pw" className="text-xs">
          {t('edit.password.current_label')}
        </Label>
        <div className="relative">
          <Input
            id="profile-cur-pw"
            type={showCurrentPw ? 'text' : 'password'}
            {...currentPwReg}
            onChange={(e) => {
              void onCurrentPwChange(e)
              if (fieldErrors.current_password) {
                setFieldErrors((prev) => ({ ...prev, current_password: undefined }))
              }
            }}
            placeholder={t('edit.password.current_placeholder')}
            aria-invalid={Boolean(currentPwError)}
            className="pr-10"
            required
          />
          <button
            type="button"
            onClick={() => setShowCurrentPw(!showCurrentPw)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1 rounded-md cursor-pointer transition-colors"
            tabIndex={-1}
            aria-label={showCurrentPw ? t('edit.password.hide_password') : t('edit.password.show_password')}
          >
            {showCurrentPw ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        </div>
        {currentPwError ? (
          <p className="text-[11px] font-medium text-destructive">
            {currentPwError}
          </p>
        ) : null}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="profile-new-pw" className="text-xs">
          {t('edit.password.new_label')}
        </Label>
        <div className="relative">
          <Input
            id="profile-new-pw"
            type={showNewPw ? 'text' : 'password'}
            {...newPwReg}
            onChange={(e) => {
              void onNewPwChange(e)
              if (fieldErrors.new_password) {
                setFieldErrors((prev) => ({ ...prev, new_password: undefined }))
              }
            }}
            placeholder={t('edit.password.new_placeholder')}
            aria-invalid={Boolean(newPwError)}
            className="pr-10"
            required
          />
          <button
            type="button"
            onClick={() => setShowNewPw(!showNewPw)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1 rounded-md cursor-pointer transition-colors"
            tabIndex={-1}
            aria-label={showNewPw ? t('edit.password.hide_password') : t('edit.password.show_password')}
          >
            {showNewPw ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        </div>
        {newPwError ? (
          <p className="text-[11px] font-medium text-destructive">
            {newPwError}
          </p>
        ) : null}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="profile-conf-pw" className="text-xs">
          {t('edit.password.confirm_label')}
        </Label>
        <div className="relative">
          <Input
            id="profile-conf-pw"
            type={showConfirmPw ? 'text' : 'password'}
            {...confirmPwReg}
            onChange={(e) => {
              void onConfirmPwChange(e)
              if (fieldErrors.confirm_password) {
                setFieldErrors((prev) => ({ ...prev, confirm_password: undefined }))
              }
            }}
            placeholder={t('edit.password.confirm_placeholder')}
            aria-invalid={Boolean(confirmPwError)}
            className="pr-10"
            required
          />
          <button
            type="button"
            onClick={() => setShowConfirmPw(!showConfirmPw)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1 rounded-md cursor-pointer transition-colors"
            tabIndex={-1}
            aria-label={showConfirmPw ? t('edit.password.hide_password') : t('edit.password.show_password')}
          >
            {showConfirmPw ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        </div>
        {confirmPwError ? (
          <p className="text-[11px] font-medium text-destructive">
            {confirmPwError}
          </p>
        ) : null}
      </div>

      <DialogFooter className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={isPending}
          className="w-full sm:w-auto"
        >
          {t('edit.btn_cancel')}
        </Button>
        <Button
          type="submit"
          disabled={
            isPending || (isSubmitted && !isValid)
          }
          className="w-full sm:w-auto bg-gradient-to-r from-primary to-orange-500 font-semibold text-primary-foreground hover:opacity-95"
        >
          {isPending ? (
            <>
              <LoaderCircle className="mr-2 size-4 animate-spin" />
              {t('edit.password.btn_changing')}
            </>
          ) : (
            <>
              <KeyRound className="mr-1.5 size-4" />
              {t('edit.password.btn_change')}
            </>
          )}
        </Button>
      </DialogFooter>
    </form>
  )
}
