import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  AlertCircle,
  BarChart3,
  Bot,
  Brain,
  Check,
  Edit3,
  FileText,
  Flame,
  Folder,
  FolderPlus,
  Layers,
  Loader2,
  PlusCircle,
  ShieldCheck,
  Trash2,
  Zap,
} from 'lucide-react'
import { toast } from 'sonner'

import { AmbientBackground } from '@/components/ambient-background'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useBootstrap } from '@/shared/api/bootstrap'
import {
  fetchConsentInfo,
  submitConsentDecision,
  type OAuthDecisionPayload,
} from '../api/oauthConsent'

function getScopeIcon(id: string) {
  if (id === 'deck:write') return <FolderPlus className="size-4 text-orange-500" />
  if (id.startsWith('deck:')) return <Folder className="size-4 text-orange-500" />
  if (id === 'note:create') return <PlusCircle className="size-4 text-emerald-500" />
  if (id === 'note:update') return <Edit3 className="size-4 text-indigo-500" />
  if (id === 'note:delete') return <Trash2 className="size-4 text-rose-500" />
  if (id === 'note:read' || id === 'note:check') return <FileText className="size-4 text-blue-500" />
  if (id === 'study:write') return <Zap className="size-4 text-purple-500" />
  if (id.startsWith('study:')) return <Brain className="size-4 text-purple-500" />
  if (id.startsWith('stats:')) return <BarChart3 className="size-4 text-amber-500" />
  if (id.startsWith('note-type:')) return <Layers className="size-4 text-sky-500" />
  return <Check className="size-4 text-primary" />
}

export function OAuthConsentPage() {
  const [searchParams] = useSearchParams()
  const { data: bootstrap, isLoading: isBootstrapLoading } = useBootstrap()

  const clientId = searchParams.get('client_id') || ''
  const redirectUri = searchParams.get('redirect_uri') || ''
  const scope = searchParams.get('scope') || ''
  const state = searchParams.get('state') || ''
  const codeChallenge = searchParams.get('code_challenge') || ''
  const codeChallengeMethod = searchParams.get('code_challenge_method') || 'S256'
  const responseType = searchParams.get('response_type') || 'code'

  const [decisionPending, setDecisionPending] = useState(false)

  // Fetch client and scope metadata
  const {
    data: consentInfo,
    isLoading: isInfoLoading,
    error: infoError,
  } = useQuery({
    queryKey: ['oauth-consent-info', clientId, scope, redirectUri],
    queryFn: () => fetchConsentInfo({ client_id: clientId, scope, redirect_uri: redirectUri }),
    enabled: Boolean(clientId),
    staleTime: 60_000,
  })

  // Decision mutation
  const decisionMutation = useMutation({
    mutationFn: submitConsentDecision,
    onSuccess: (data) => {
      if (data.redirect_url) {
        window.location.href = data.redirect_url
      } else if (data.error) {
        toast.error(`Ủy quyền thất bại: ${data.error_description || data.error}`)
        setDecisionPending(false)
      }
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.error_description || err?.message || 'Có lỗi xảy ra khi xử lý ủy quyền'
      toast.error(msg)
      setDecisionPending(false)
    },
  })

  const handleDecision = (action: 'approve' | 'deny') => {
    if (decisionPending) return
    setDecisionPending(true)

    const payload: OAuthDecisionPayload = {
      client_id: clientId,
      redirect_uri: redirectUri,
      response_type: responseType,
      scope,
      state,
      code_challenge: codeChallenge,
      code_challenge_method: codeChallengeMethod,
      action,
    }

    decisionMutation.mutate(payload)
  }

  const currentUser = consentInfo?.user || bootstrap?.user
  const clientName = consentInfo?.client?.client_name || 'ChatGPT Assistant'
  const scopesList = consentInfo?.scopes || []

  // Check login
  if (!isBootstrapLoading && !bootstrap?.user) {
    const currentUrl = window.location.pathname + window.location.search
    window.location.href = `/login?next=${encodeURIComponent(currentUrl)}`
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="size-8 animate-spin text-primary" />
      </div>
    )
  }

  // Missing client_id error
  if (!clientId) {
    return (
      <div className="relative min-h-screen flex items-center justify-center p-4">
        <AmbientBackground intensity="subtle" />
        <Card className="max-w-md w-full border-border/60 bg-card/90 backdrop-blur-xl shadow-2xl rounded-3xl p-6 text-center space-y-4">
          <div className="mx-auto size-12 rounded-2xl bg-destructive/10 text-destructive flex items-center justify-center">
            <AlertCircle className="size-6" />
          </div>
          <h2 className="text-xl font-bold">Yêu cầu không hợp lệ</h2>
          <p className="text-sm text-muted-foreground">
            Thiếu tham số <code>client_id</code> trong yêu cầu kết nối OAuth. Vui lòng kiểm tra lại cấu hình từ ứng dụng của bạn.
          </p>
        </Card>
      </div>
    )
  }

  if (isInfoLoading) {
    return (
      <div className="relative min-h-screen flex items-center justify-center p-4">
        <AmbientBackground intensity="subtle" />
        <Card className="max-w-md w-full border-border/60 bg-card/90 backdrop-blur-xl shadow-2xl rounded-3xl p-10 text-center space-y-4">
          <Loader2 className="size-10 animate-spin text-primary mx-auto" />
          <p className="text-sm font-medium text-muted-foreground">Đang tải thông tin ứng dụng kết nối…</p>
        </Card>
      </div>
    )
  }

  if (infoError) {
    return (
      <div className="relative min-h-screen flex items-center justify-center p-4">
        <AmbientBackground intensity="subtle" />
        <Card className="max-w-md w-full border-border/60 bg-card/90 backdrop-blur-xl shadow-2xl rounded-3xl p-6 text-center space-y-4">
          <div className="mx-auto size-12 rounded-2xl bg-destructive/10 text-destructive flex items-center justify-center">
            <AlertCircle className="size-6" />
          </div>
          <h2 className="text-xl font-bold">Không thể tải thông tin ủy quyền</h2>
          <p className="text-sm text-muted-foreground">
            {(infoError as any)?.response?.data?.error_description || (infoError as any)?.message || 'Ứng dụng client_id không tồn tại hoặc đã bị hủy.'}
          </p>
        </Card>
      </div>
    )
  }

  const userInitial = (currentUser?.username?.charAt(0) || 'F').toUpperCase()

  return (
    <div className="relative min-h-screen flex items-center justify-center px-4 py-8 sm:py-12">
      {/* Flama Ambient Background */}
      <AmbientBackground intensity="vibrant" />

      <div className="relative z-10 w-full max-w-lg animate-in fade-in-50 slide-in-from-bottom-4 duration-500">
        <Card className="border-border/60 bg-card/95 backdrop-blur-2xl shadow-2xl rounded-3xl overflow-hidden border">
          <CardContent className="p-6 sm:p-8 space-y-6">
            {/* 1. Connector Bridge Hero */}
            <div className="flex items-center justify-center gap-3 sm:gap-4 pt-2">
              {/* ChatGPT Icon */}
              <div
                className="size-13 sm:size-14 rounded-2xl bg-emerald-600 text-white flex items-center justify-center shadow-md shrink-0 transition-transform hover:scale-105"
                title="ChatGPT / OpenAI"
              >
                <Bot className="size-7 sm:size-8" />
              </div>

              {/* Connecting Bridge */}
              <div className="flex flex-col items-center gap-1">
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-primary/20 bg-primary/5 text-primary text-[11px] font-bold tracking-wide">
                  <span className="size-2 rounded-full bg-emerald-500 animate-pulse" />
                  OAuth 2.1 • Remote MCP
                </div>
              </div>

              {/* Flama Logo */}
              <div
                className="size-13 sm:size-14 rounded-2xl bg-gradient-to-br from-primary via-orange-500 to-rose-500 text-white flex items-center justify-center shadow-lg shadow-orange-500/25 shrink-0 transition-transform hover:scale-105"
                title="Flama Study Platform"
              >
                <img
                  src="/logo.png"
                  alt="Flama"
                  className="size-9 object-contain drop-shadow"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none'
                    e.currentTarget.nextElementSibling?.classList.remove('hidden')
                  }}
                />
                <Flame className="size-8 hidden" />
              </div>
            </div>

            {/* 2. Header Text */}
            <div className="text-center space-y-2">
              <h1 className="text-2xl sm:text-[26px] font-extrabold tracking-tight text-foreground">
                Cấp quyền cho{' '}
                <span className="bg-gradient-to-r from-primary via-orange-500 to-amber-500 bg-clip-text text-transparent">
                  {clientName}
                </span>
              </h1>
              <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed max-w-md mx-auto">
                Ứng dụng yêu cầu kết nối an toàn với kho thẻ Flama của bạn để hỗ trợ tra cứu từ vựng, tạo flashcard và đồng bộ tiến độ học tập.
              </p>
            </div>

            {/* 3. Current User Box */}
            <div className="flex items-center justify-between gap-3 p-3 sm:p-3.5 rounded-2xl bg-muted/60 border border-border/50">
              <div className="flex items-center gap-3 min-w-0">
                <div className="size-9 sm:size-10 rounded-full bg-gradient-to-tr from-primary to-orange-400 text-white font-bold text-sm sm:text-base flex items-center justify-center shadow-sm shrink-0">
                  {userInitial}
                </div>
                <div className="min-w-0">
                  <div className="text-xs sm:text-sm font-bold truncate text-foreground">
                    {currentUser?.username}
                  </div>
                  {currentUser?.email && (
                    <div className="text-[11px] sm:text-xs text-muted-foreground truncate">
                      {currentUser?.email}
                    </div>
                  )}
                </div>
              </div>

              <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20 text-[11px] font-semibold shrink-0 gap-1">
                <Check className="size-3" />
                Tài khoản Flama
              </Badge>
            </div>

            {/* 4. Scopes List */}
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-muted-foreground">
                <span>Quyền hạn được cấp phép</span>
                <span className="font-mono lowercase text-[11px] bg-muted px-2 py-0.5 rounded-md">
                  {scopesList.length} quyền
                </span>
              </div>

              <div className="space-y-2 max-h-56 overflow-y-auto pr-1 no-scrollbar">
                {scopesList.map((sc) => (
                  <div
                    key={sc.id}
                    className="flex items-start gap-3 p-3 rounded-2xl border border-border/40 bg-muted/30 hover:bg-muted/60 transition-colors"
                  >
                    <div className="size-7 rounded-xl bg-card border border-border/60 flex items-center justify-center shrink-0 mt-0.5 shadow-2xs">
                      {getScopeIcon(sc.id)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2 mb-0.5">
                        <span className="text-xs sm:text-[13px] font-bold text-foreground truncate">
                          {sc.title}
                        </span>
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-primary/10 text-primary border border-primary/20 shrink-0">
                          {sc.id}
                        </span>
                      </div>
                      <p className="text-[11px] sm:text-xs text-muted-foreground leading-relaxed">
                        {sc.desc}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 5. Security & Confirmation Guarantee */}
            <div className="flex items-start gap-3 p-3 sm:p-3.5 rounded-2xl border border-primary/20 bg-primary/5 text-foreground">
              <ShieldCheck className="size-5 text-primary shrink-0 mt-0.5" />
              <div className="text-[11px] sm:text-xs text-muted-foreground leading-relaxed">
                <strong className="text-foreground">Bảo mật & Quyền riêng tư:</strong> Flama áp dụng cơ chế xác nhận an toàn cho các tác vụ xóa. AI không thể xóa dữ liệu mà không có sự phê duyệt trực tiếp của bạn. Bạn có thể thu hồi quyền bất kỳ lúc nào trong mục Cài đặt.
              </div>
            </div>

            {/* 6. Action Buttons */}
            <div className="flex flex-col-reverse sm:flex-row gap-3 pt-2">
              <Button
                type="button"
                variant="secondary"
                disabled={decisionPending}
                onClick={() => handleDecision('deny')}
                className="flex-1 h-12 rounded-2xl font-bold text-sm"
              >
                Từ chối
              </Button>

              <Button
                type="button"
                disabled={decisionPending}
                onClick={() => handleDecision('approve')}
                className="flex-1 h-12 rounded-2xl font-bold text-sm bg-gradient-to-r from-primary via-orange-500 to-amber-500 text-white shadow-lg shadow-orange-500/25 hover:shadow-orange-500/40 hover:scale-[1.01] transition-all gap-2"
              >
                {decisionPending ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    <span>Đang kết nối…</span>
                  </>
                ) : (
                  <>
                    <Check className="size-4 stroke-[3]" />
                    <span>Cho phép kết nối</span>
                  </>
                )}
              </Button>
            </div>

            {/* Footer */}
            <div className="text-center text-[11px] text-muted-foreground/80">
              Flama Study Platform • Tuân thủ chuẩn OAuth 2.1 & RFC 9728
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
