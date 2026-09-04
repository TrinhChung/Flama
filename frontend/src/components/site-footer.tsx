import { Link } from 'react-router-dom'
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
								Flama là nền tảng học tập đa lĩnh vực, ứng dụng phương pháp Spaced Repetition để tối
								ưu khả năng ghi nhớ và đồng hành cùng tiến độ của bạn mỗi ngày.
							</p>
						</div>

						{/* Concierge Support Block */}
						<div className="mt-6 border-t border-white/[0.04] pt-4 lg:border-t-0 lg:pt-0">
							<span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-white/30">
								Hỗ trợ trực tiếp
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
								<span>Phản hồi trong 24–48h</span>
							</div>
						</div>
					</div>

					{/* Link Columns: Balanced 2-Column Matrix on Mobile, 4 Columns on MD, Direct Grid Items on LG */}
					<div className="grid grid-cols-2 gap-x-6 gap-y-8 sm:grid-cols-2 md:grid-cols-4 lg:contents">

						{/* Col 2 — Học tập & Quản lý */}
						<FooterColumn title="Học tập & Quản lý">
							{user ? (
								<>
									<FooterLink to={bootstrap.links.dashboard || '/dashboard'}>Tổng quan học tập</FooterLink>
									<FooterLink to={bootstrap.links.study || '/study'}>Học flashcard</FooterLink>
									<FooterLink to="/browse">Kho từ vựng &amp; Thẻ</FooterLink>
									<FooterLink to="/statistics">Thống kê &amp; Lịch học</FooterLink>
									{user.is_admin ? <FooterLink to="/import">Nhập dữ liệu CSV/TSV</FooterLink> : null}
									<FooterLink to={bootstrap.links.note_types || '/note-types'}>Quản lý NoteTypes</FooterLink>
								</>
							) : (
								<>
									<FooterLink to="/">Trang giới thiệu</FooterLink>
									<FooterLink to="/login">Đăng nhập</FooterLink>
									<FooterLink to="/register">Đăng ký tài khoản</FooterLink>
								</>
							)}
						</FooterColumn>

						{/* Col 3 — Chợ bộ thẻ & Đóng góp */}
						<FooterColumn title="Chợ bộ thẻ & Đóng góp">
							<FooterLink to={bootstrap.links.shared_decks || '/marketplace/decks'}>Khám phá Decks</FooterLink>
							<FooterLink to={bootstrap.links.shared_note_types || '/marketplace/note-types'}>Khám phá NoteTypes</FooterLink>
							{user && (
								<>
									<FooterLink to="/marketplace/decks/publish">Đăng bộ thẻ lên Chợ</FooterLink>
									<FooterLink to="/marketplace/note-types/publish">Chia sẻ NoteType</FooterLink>
									<FooterLink to="/installed-decks">Bộ thẻ đã cài</FooterLink>
									<FooterLink to="/orders">Lịch sử đơn hàng</FooterLink>
								</>
							)}
						</FooterColumn>

						{/* Col 4 — Công cụ & Tích hợp */}
						<FooterColumn title="Công cụ & Tích hợp">
							<FooterLink to="/settings/yomitan">Tích hợp Yomitan</FooterLink>
							<FooterLink to="/guide/tts-key">Hướng dẫn Key TTS</FooterLink>
							<FooterLink to="/feedback">Gửi góp ý &amp; Báo lỗi</FooterLink>
							{user?.is_admin && (
								<FooterLink to={bootstrap.links.admin_users || '/admin/users'}>Quản trị hệ thống</FooterLink>
							)}
						</FooterColumn>

						{/* Col 5 — Pháp lý & Hỗ trợ */}
						<FooterColumn title="Pháp lý & Hỗ trợ">
							<FooterLink to={bootstrap.links.terms || '/terms'}>Điều khoản sử dụng</FooterLink>
							<FooterLink to={bootstrap.links.privacy || '/privacy'}>Chính sách bảo mật</FooterLink>
							<FooterLink to={bootstrap.links.cookies || '/cookies'}>Chính sách cookie</FooterLink>
							<FooterLink to={bootstrap.links.support || '/support'}>Ủng hộ hệ thống</FooterLink>
						</FooterColumn>
					</div>
				</div>

				{/* ── Bottom Bar: Copyright & Editorial Back to Top ── */}
				<div className="flex flex-col items-center justify-between gap-4 pt-6 text-xs text-white/35 sm:flex-row">
					<div>
						© {new Date().getFullYear()} Flama. Được phát triển với ❤️ bởi Chung Trịnh.
					</div>

					<button
						type="button"
						onClick={handleScrollToTop}
						className="group inline-flex items-center gap-1.5 text-xs uppercase tracking-wider text-white/40 transition-colors hover:text-white"
					>
						<span>Lên đầu trang</span>
						<span className="inline-block transition-transform duration-200 group-hover:-translate-y-0.5">↑</span>
					</button>
				</div>
			</div>
		</footer>
	)
}
