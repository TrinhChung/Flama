# GT-11 — Bản nhận marketplace và phát hành template

Status 2026-10-08: **GT-11A/B/C Completed / verified** by Codex; see [CT-R2](reviews/CT-R2_TEMPLATE_UI_COMPLETION_2026-10-08.md). The phases below remain implementation criteria.
Supersedes v1 install-scoped forks. One copy per (user_id, source_template_id), shared across the user's decks/NoteTypes.
Use install only to discover local_template_id. Save, history, preview and subscription use that local ID.
Reset means the currently applied published release, never the author's live draft. History is retained.

## 1. Verified API contract

Sources: app/api/v1/flashcards/card_templates.py and app/services/template_release_service.py.
Canonical prefix /api. Use shared apiRequest/apiJson for credentials and CSRF. Encode each ID and forward AbortSignal.

| FE function | Method/path below /api | Body and response |
|---|---|---|
| fetchInstallTemplates(installId, signal?) | GET /deck-installs/{installId}/templates | {install_id, items:Subscription[], legacy_template_fallback:boolean} |
| fetchTemplateSubscription(localId, signal?) | GET /card-templates/{localId}/subscription | Subscription |
| updateTemplateSubscription(localId, enabled) | PATCH /card-templates/{localId}/subscription | {auto_update_enabled:enabled} -> Subscription |
| fetchTemplateReleases(localId, signal?) | GET /card-templates/{localId}/releases | {template_id:localId,source_template_id,items:Release[],has_more:boolean} |
| fetchTemplateRelease(localId, releaseId, signal?) | GET /card-templates/{localId}/releases/{releaseId} | Release & {version:ReleaseSnapshot} |
| prepareTemplateUpdate(localId, body) | POST /card-templates/{localId}/prepare-update | PrepareBody -> Preparation |
| applyTemplateUpdate(localId, body) | POST /card-templates/{localId}/apply-update | ApplyBody -> Subscription |
| resetReceivedTemplate(localId) | POST /card-templates/{localId}/reset-to-upstream | {} -> Subscription |

Use GT-12A library API for local detail/PATCH/preview, GT-10A A2 API for history/restore.
Do not add /fork, /marketplace/installations/.../templates, /sync-definition or definition_id.

Release: {id,template_id,version_id,sequence_no:number,version_label,parent_release_id:string|null,publish_mode:'manual'|'automatic',idempotency_key:string|null,change_note:string|null,created_by_user_id:number|null,published_at:string}.
ReleaseSnapshot: {id,template_id,version_no:number,front_html,back_html,shared_css,input_schema,content_hash,origin,change_note:string|null,created_by_user_id:number|null,created_at:string}.
Release/snapshot template_id is source ID. Timestamps UTC. Snapshot is not A2 detail: no created_by/is_current.

Subscription: {id,user_id:number,source_template_id,local_template_id,applied_release_id,seen_release_id:string|null,auto_update_enabled:boolean,pending_update_json:Preparation|null,last_sync_status:string|null,last_synced_at:string|null,created_at:string,updated_at:string,template_id,current_version_id:string|null,current_release:Release|null,applied_release:Release|null,update_available:boolean,template}.
Subscription template_id is local ID. template is all local Template columns: id,note_type_id:string|null,owner_user_id:number|null,name,description:string|null,primary_category:string|null,origin,source_template_id:string|null,source_version_id:string|null,current_version_id:string|null,front_html,back_html,shared_css,input_schema,position:number,is_default:boolean,archived_at:string|null,created_at,updated_at. No library usage counts/applications on this raw template object.

PrepareBody: {release_id,expected_applied_release_id?,expected_current_version_id?,idempotency_key?}.
Send both expected IDs from displayed subscription. Reuse a stable key for one action; change it for another target release.
Preparation: {id,from_release_id,to_release_id,expected_local_version_id,status:'ready'|'has_conflict',conflicts,idempotency_key:string|null,mode:'manual'|'automatic'}.
conflicts: Partial<Record<'front_html'|'back_html'|'shared_css'|'input_schema',{base,upstream,local}>>.
ApplyBody: {preparation_id,resolutions?:Record<conflictedKey,{mode:'keep_mine'|'keep_upstream'|'manual',value?:string|InputSchema[]}>}.
This FE phase supports keep_mine/keep_upstream; submit every conflict and no extra keys.

404: INSTALL_NOT_FOUND/TEMPLATE_NOT_FOUND/TEMPLATE_SUBSCRIPTION_NOT_FOUND/TEMPLATE_RELEASE_NOT_FOUND.
409: NO_TEMPLATE_UPDATE/APPLIED_RELEASE_STALE/LOCAL_VERSION_STALE/TEMPLATE_UPDATE_STALE/REBASE_CONFLICTS_UNRESOLVED.
400: VALIDATION_ERROR/TEMPLATE_COMPILE_ERROR. On stale, preserve draft and refetch/reprepare; no automatic write retry.
Recipients read upstream releases through owned local ID. Direct foreign source ID stays 404.
Received templates cannot duplicate/publish; explicit publication/settings returns403 MARKET_TEMPLATE_REPUBLISH_FORBIDDEN.

## 2. Phases and whitelist (max6 files)

GT-11A entity (5 files), after GT-12A:
- frontend/src/entities/card-template/model/types.ts
- frontend/src/entities/card-template/api/cardTemplateApi.ts
- frontend/src/entities/card-template/api/queryKeys.ts
- frontend/src/entities/card-template/index.ts
- frontend/src/entities/card-template/api/cardTemplateApi.test.ts
Add types/API above, keys installTemplates(id),subscription(id),releases(id),release(id,rid) under ['card-template',...].
Test encoded URL/method/body/signal/local-vs-source IDs; preserve old assertions.

GT-11B install entry (6 files), after GT-11A and editor GT-12D:
- frontend/src/features/library/pages/InstallTemplatesPage.tsx and .test.tsx
- frontend/src/features/dashboard/components/DeckCardTypesDialog.tsx and .test.tsx
- frontend/src/App.tsx
- frontend/src/layouts/AppLayout.tsx
Route /installed-decks/:installId/templates; title "Mẫu thẻ đã nhận"; query template selects source ID initially.
For installed_source+install_id replace disabled GT07 action with Link to that route, preserving class. Missing install_id stays disabled; owned/local-added actions unchanged.
GET list maps source -> local, each item links /card-templates/{local_template_id}. Show name, "Bản đã nhận {applied_release.version_label}", "Có bản mới", "Dùng chung cho các bộ của bạn".
Empty "Chưa có mẫu thẻ đã nhận."; legacy "Bộ đã cài này chưa có bản phát hành mẫu thẻ."; existing PageState loading/error. Never implicitly create copies for legacy fallback.
Test source-to-local link, repeated install shared identity, legacy/empty/error, route param changes.

GT-11C distribution panel (6 files), after GT-11B/GT-10B:
- frontend/src/features/template-distribution/ui/TemplateDistributionPanel.tsx and .test.tsx
- frontend/src/features/template-distribution/model/useTemplateDistribution.ts
- frontend/src/features/template-distribution/index.ts
- frontend/src/features/template-library/pages/TemplateDetailPage.tsx and .test.tsx
Only page composition imports new feature. Panel props {templateId:string,origin:string,currentVersionId:string|null,onSourceChanged:()=>Promise<void>|void}.
Recipient switch "Tự động kế thừa" follows response (default false); enabling may immediately apply an update.
"Có bản mới" / "Xem cập nhật" prepares current_release.id, diff compares release snapshot to local, choices "Giữ bản của tôi" / "Lấy bản của tác giả" per conflicting property. Enable "Áp dụng cập nhật" only when fully resolved.
"Dùng lại bản đã nhận" requires ConfirmDialog "Thay nội dung riêng bằng bản đã nhận?" and resets pinned applied release.
Author controls per section3: "Tự động đăng bản mới", "Đăng bản mới nhất"; never show for market_copy.
After mutations invalidate detail/library/history/subscription/releases/publication. Callback refetches full detail AND explicitly replaces draft even if response content equals cached server content. Errors preserve draft; guard late response by template/request identity.
Tests bool/expected IDs/preparation keys/resolutions/stale/unresolved/reset-history, origin-specific controls, same-server restore replacement and late responses.

## 3. Author publication (GT-11C)

Keep whitelist: implement these calls in the new hook with shared apiRequest/apiJson, no @/app/api import.
GET /card-templates/{id}/publication -> {template_id,auto_publish_enabled,current_release,current_version_id,has_unpublished_changes,last_auto_published_at,last_auto_publish_error}.
PATCH same path {auto_publish_enabled:boolean} -> same DTO.
POST /card-templates/{id}/releases body {version_label,change_note?,expected_current_release_id,expected_current_version_id}; both expected IDs required, null allowed before first head.
apiJson fourth argument {headers:{'Idempotency-Key':key}}. HTTP201 {release:Release,replayed:boolean}. Label1-50,key1-64,note<=1000.
Stale/head/duplicate-label/no-change errors preserve draft and refresh; never silently retry publication.

## 4. Checks and handoff

Targeted Vitest per whitelist; npm --prefix frontend run typecheck, lint, build; git diff --check.
No full-suite snapshot updates, backend/schema/study-runtime/renderer edits, database writes, commit or push.
Ready only when FE dependencies are accepted. Report actual changed files/output per README. Codex browser gate after Gemini UI.
