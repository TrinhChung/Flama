import { apiJson, apiRequest } from '@/shared/api/client'

export type OAuthScopeItem = {
  id: string
  title: string
  desc: string
  category: string
  icon: string
}

export type OAuthClientInfo = {
  client_id: string
  client_name: string
  is_trusted?: boolean
}

export type OAuthUserInfo = {
  id: number
  username: string
  email: string
}

export type OAuthConsentInfoResponse = {
  client: OAuthClientInfo
  scopes: OAuthScopeItem[]
  user: OAuthUserInfo | null
}

export type OAuthDecisionPayload = {
  client_id: string
  redirect_uri: string
  response_type?: string
  scope?: string
  state?: string
  code_challenge?: string
  code_challenge_method?: string
  action: 'approve' | 'deny'
}

export type OAuthDecisionResponse = {
  redirect_url: string
  error?: string
  error_description?: string
}

export async function fetchConsentInfo(params: {
  client_id: string
  scope?: string
  redirect_uri?: string
}): Promise<OAuthConsentInfoResponse> {
  const searchParams = new URLSearchParams()
  if (params.client_id) searchParams.set('client_id', params.client_id)
  if (params.scope) searchParams.set('scope', params.scope)
  if (params.redirect_uri) searchParams.set('redirect_uri', params.redirect_uri)

  return apiRequest<OAuthConsentInfoResponse>(
    `/api/oauth/consent-info?${searchParams.toString()}`,
  )
}

export async function submitConsentDecision(
  payload: OAuthDecisionPayload,
): Promise<OAuthDecisionResponse> {
  return apiJson<OAuthDecisionResponse>(
    '/api/oauth/consent-decision',
    'POST',
    payload,
  )
}
