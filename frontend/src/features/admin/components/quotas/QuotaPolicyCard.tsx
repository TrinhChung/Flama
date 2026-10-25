import { Eye, Save, ShieldAlert } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Switch } from '@/components/ui/switch'
import { useUpdateQuotaPolicy } from '../../api/quotasApi'
import { useQuotaPolicyForm } from '../../hooks/useQuotaPolicyForm'
import type { QuotaPeriod, QuotaPolicy, QuotaRole } from '../../types/quotas'
import { QUOTA_KIND_META, QUOTA_PERIOD_LABELS, QUOTA_PERIODS } from './quotaFormat'

export function QuotaModeBadge({ enforce }: { enforce: boolean }) {
  return enforce ? (
    <Badge variant="destructive" className="gap-1">
      <ShieldAlert className="size-3.5" /> Đang chặn
    </Badge>
  ) : (
    <Badge variant="secondary" className="gap-1">
      <Eye className="size-3.5" /> Chỉ theo dõi
    </Badge>
  )
}

export function QuotaPolicyCard({ policy, roles }: { policy: QuotaPolicy; roles: QuotaRole[] }) {
  const meta = QUOTA_KIND_META[policy.kind]
  const Icon = meta.icon
  const form = useQuotaPolicyForm(policy, roles)
  const mutation = useUpdateQuotaPolicy()
  const unitLabel = policy.unit === 'MB' ? 'MB' : 'request'

  const save = () => {
    if (form.invalidRole) {
      toast.error(`Hạn mức của vai trò ${form.invalidRole.name} phải là số nguyên không âm.`)
      return
    }
    mutation.mutate(
      { kind: policy.kind, payload: form.payload },
      {
        onSuccess: (data) => toast.success(data.message || 'Đã lưu chính sách quota.'),
        onError: (error: Error) => toast.error(error.message || 'Không thể lưu chính sách quota.'),
      },
    )
  }

  return (
    <Card className="flex flex-col" data-testid={`quota-policy-${policy.kind}`}>
      <CardHeader className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Icon className="size-4 text-primary" />
            {meta.label}
          </CardTitle>
          <QuotaModeBadge enforce={policy.enforce} />
        </div>
        <CardDescription className="text-xs leading-relaxed">{meta.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
          <div className="space-y-0.5">
            <Label htmlFor={`quota-enforce-${policy.kind}`} className="cursor-pointer text-sm font-semibold">
              Chặn khi vượt hạn mức
            </Label>
            <p className="text-xs text-muted-foreground">
              Tắt: vẫn đếm và ghi nhận ai vượt, nhưng không chặn ai.
            </p>
          </div>
          <Switch
            id={`quota-enforce-${policy.kind}`}
            checked={form.enforce}
            onCheckedChange={form.setEnforce}
            aria-label={`Chặn khi vượt hạn mức ${meta.label}`}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor={`quota-period-${policy.kind}`} className="text-sm">
            Chu kỳ tính hạn mức
          </Label>
          <NativeSelect
            id={`quota-period-${policy.kind}`}
            value={form.period}
            onChange={(event) => form.setPeriod(event.target.value as QuotaPeriod)}
            className="h-9 w-full"
          >
            {QUOTA_PERIODS.map((period) => (
              <NativeSelectOption key={period} value={period}>
                Theo {QUOTA_PERIOD_LABELS[period]}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium">
            Hạn mức mặc định theo vai trò ({unitLabel} / {QUOTA_PERIOD_LABELS[form.period]})
          </p>
          {roles.map((role) => {
            const draft = form.limits[role.code] ?? { unlimited: true, value: '' }
            const inputId = `quota-limit-${policy.kind}-${role.code}`
            return (
              <div key={role.code} className="grid grid-cols-[minmax(0,1fr)_7rem] items-center gap-2">
                <div className="min-w-0">
                  <Label htmlFor={inputId} className="truncate text-sm">
                    {role.name}
                  </Label>
                  <label className="mt-1 flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground">
                    <Checkbox
                      checked={draft.unlimited}
                      onCheckedChange={(checked) => form.setRoleLimit(role.code, { unlimited: checked === true })}
                      aria-label={`${role.name} không giới hạn`}
                    />
                    Không giới hạn
                  </label>
                </div>
                <Input
                  id={inputId}
                  type="number"
                  min={0}
                  inputMode="numeric"
                  value={draft.unlimited ? '' : draft.value}
                  placeholder={draft.unlimited ? '∞' : '0'}
                  disabled={draft.unlimited}
                  onChange={(event) => form.setRoleLimit(role.code, { value: event.target.value })}
                  className="h-9 text-right"
                />
              </div>
            )
          })}
          <p className="text-xs text-muted-foreground">Admin luôn không giới hạn.</p>
        </div>

        <div className="mt-auto flex justify-end">
          <Button size="sm" className="gap-1.5" onClick={save} disabled={!form.isDirty || mutation.isPending}>
            <Save className="size-3.5" />
            {mutation.isPending ? 'Đang lưu…' : 'Lưu chính sách'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
