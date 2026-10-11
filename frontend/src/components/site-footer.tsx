import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { Brand } from '@/shared/components/Brand'
import type { FrontendBootstrap } from '@/shared/types/api'

function FooterColumn({ title, children }: { title: string; children: React.ReactNode }) {
	return (
		<div>
			<h4 className="mb-3 flex min-h-[1.75rem] items-center text-xs font-semibold uppercase tracking-wider text-white/40">
				{title}
			</h4>
			<ul className="flex flex-col space-y-2 text-xs">
				{children}
			</ul>
		</div>
	)
}

function FooterLink({ to, children }: { to: string; children: React.ReactNode }) {
	return (
		<li>
			<Link
				to={to}
				className="inline-block py-0.5 text-xs text-white/55 transition-colors duration-150 hover:text-white active:text-orange-400"
			>
				{children}
			</Link>
		</li>
	)
}

export function SiteFooter({ bootstrap }: { bootstrap: FrontendBootstrap }) {
	const { t } = useTranslation('shell')
	const email = bootstrap.support_contact_email
	const user = bootstrap.user

	const handleScrollToTop = () => {
		window.scrollTo({ top: 0, behavior: 'smooth' })
	}

	return (
		<footer className="w-full shrink-0 border-t border-white/[0.08] bg-[#181513] pt-10 pb-[calc(1.5rem+env(safe-area-inset-bottom,0px))] text-xs text-white/60">
			<div className="mx-auto max-w-7xl px-4 md:px-6">

				{/* ── Main Footer Grid ── */}
				<div className="grid grid-cols-1 gap-8 border-b border-white/[0.06] pb-10 lg:grid-cols-[1.5fr_1fr_1fr_1fr_1fr] lg:gap-8">

					{/* Col 1 — Brand & Editorial Voice */}
					<div className="flex flex-col justify-between border-b border-white/[0.06] pb-8 lg:border-b-0 lg:pb-0">
						<div>
							<Brand compact className="mb-3" />
							<p className="max-w-xs text-xs leading-relaxed text-white/45">
								{t('footer.brand_desc')}
							</p>
						</div>

						{/* Concierge Support Block */}
						<div className="mt-6 border-t border-white/[0.04] pt-4 lg:border-t-0 lg:pt-0">
							<span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-white/30">
								{t('footer.support_concierge')}
							</span>
							{email ? (
								<a
									href={`mailto:${email}`}
									className="inline-flex items-center text-xs text-white/60 underline decoration-white/20 underline-offset-4 transition-colors hover:text-white hover:decoration-white"
								>
									{email}
								</a>
							) : null}
							<div className="mt-2 flex items-center gap-1.5 text-xs text-white/35">
								<span className="size-1.5 shrink-0 rounded-full bg-emerald-500/80" />
								<span>{t('footer.response_sla')}</span>
							</div>
						</div>
					</div>

					{/* Link Columns: Balanced 2-Column Matrix on Mobile, 4 Columns on MD, Direct Grid Items on LG */}
					<div className="grid grid-cols-2 gap-x-6 gap-y-8 sm:grid-cols-2 md:grid-cols-4 lg:contents">

						{/* Col 2 — Học tập & Quản lý */}
						<FooterColumn title={t('footer.col_learning')}>
							{user ? (
								<>
									<FooterLink to={bootstrap.links.dashboard || '/dashboard'}>{t('footer.link_dashboard')}</FooterLink>
									<FooterLink to={bootstrap.links.study || '/study'}>{t('footer.link_study')}</FooterLink>
									<FooterLink to="/browse">{t('footer.link_browse')}</FooterLink>
									<FooterLink to="/statistics">{t('footer.link_stats')}</FooterLink>
									<FooterLink to="/import">{t('footer.link_import')}</FooterLink>
								</>
							) : (
								<>
									<FooterLink to="/">{t('footer.link_home')}</FooterLink>
									<FooterLink to={bootstrap.links.shared_decks || '/marketplace/decks'}>{t('footer.link_explore_guest')}</FooterLink>
									<FooterLink to="/guide">{t('footer.link_guide_guest')}</FooterLink>
									<FooterLink to="/login">{t('footer.link_login')}</FooterLink>
									<FooterLink to="/register">{t('footer.link_register')}</FooterLink>
								</>
							)}
						</FooterColumn>

						{/* Col 3 — Chợ bộ thẻ & Đóng góp */}
						<FooterColumn title={t('footer.col_market')}>
							<FooterLink to={bootstrap.links.shared_decks || '/marketplace/decks'}>{t('footer.link_explore_decks')}</FooterLink>
							{user && (
								<>
									<FooterLink to="/marketplace/decks/publish">{t('footer.link_publish_deck')}</FooterLink>
									<FooterLink to="/installed-decks">{t('footer.link_installed')}</FooterLink>
									<FooterLink to="/flashcards/change-requests/incoming">{t('footer.link_change_requests')}</FooterLink>
									<FooterLink to="/orders">{t('footer.link_orders')}</FooterLink>
								</>
							)}
						</FooterColumn>

						{/* Col 4 — Công cụ & Tích hợp */}
						<FooterColumn title={t('footer.col_tools')}>
							<FooterLink to="/settings/yomitan">{t('footer.link_yomitan')}</FooterLink>
							<FooterLink to="/settings/asbplayer">{t('footer.link_asbplayer')}</FooterLink>
							<FooterLink to="/guide/flama-audio">{t('footer.link_flama_audio')}</FooterLink>
							<FooterLink to="/sync">{t('footer.link_anki_sync')}</FooterLink>
							<FooterLink to="/guide">{t('footer.link_guide')}</FooterLink>
							{user?.is_admin && (
								<FooterLink to={bootstrap.links.admin_users || '/admin/users'}>{t('footer.link_admin')}</FooterLink>
							)}
						</FooterColumn>

						{/* Col 5 — Pháp lý & Hỗ trợ */}
						<FooterColumn title={t('footer.col_legal')}>
							<FooterLink to={bootstrap.links.terms || '/terms'}>{t('footer.link_terms')}</FooterLink>
							<FooterLink to={bootstrap.links.privacy || '/privacy'}>{t('footer.link_privacy')}</FooterLink>
							<FooterLink to="/marketplace-guidelines">{t('footer.link_market_guidelines')}</FooterLink>
							<FooterLink to="/community-guidelines">{t('footer.link_community')}</FooterLink>
							<FooterLink to={bootstrap.links.cookies || '/cookies'}>{t('footer.link_cookies')}</FooterLink>
							<FooterLink to="/feedback">{t('footer.link_feedback')}</FooterLink>
							<FooterLink to={bootstrap.links.support || '/support'}>{t('footer.link_support')}</FooterLink>
						</FooterColumn>
					</div>
				</div>

				{/* ── Bottom Bar: Copyright & Editorial Back to Top ── */}
				<div className="flex flex-col items-center justify-between gap-4 pt-6 text-xs text-white/35 sm:flex-row">
					<div className="flex flex-wrap items-center gap-x-3 gap-y-1">
						<span>{t('footer.copyright', { year: new Date().getFullYear() })}</span>
					</div>

					<button
						type="button"
						onClick={handleScrollToTop}
						className="group inline-flex items-center gap-1.5 text-xs uppercase tracking-wider text-white/40 transition-colors hover:text-white cursor-pointer"
					>
						<span>{t('footer.back_to_top')}</span>
						<span className="inline-block transition-transform duration-200 group-hover:-translate-y-0.5">↑</span>
					</button>
				</div>
			</div>
		</footer>
	)
}
