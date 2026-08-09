import { Link } from 'react-router-dom'
import { Clock, Mail } from 'lucide-react'
import { Brand } from '@/shared/components/Brand'
import type { FrontendBootstrap } from '@/shared/types/api'

function FooterColumn({ title, children }: { title: string; children: React.ReactNode }) {
	return (
		<div>
			<h4 className="mb-3 text-[0.7rem] font-bold uppercase tracking-widest text-white/35">
				{title}
			</h4>
			<ul className="flex flex-col gap-2">
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
				className="inline-flex items-center gap-1.5 text-[0.82rem] text-white/60 transition-colors hover:text-orange-400"
			>
				{children}
			</Link>
		</li>
	)
}

function MailLink({ email, children }: { email: string; children: React.ReactNode }) {
	return (
		<li>
			<a
				href={`mailto:${email}`}
				className="inline-flex items-center gap-1.5 break-all text-[0.82rem] text-white/60 transition-colors hover:text-orange-400"
			>
				{children}
			</a>
		</li>
	)
}

export function SiteFooter({ bootstrap }: { bootstrap: FrontendBootstrap }) {
	const email = bootstrap.support_contact_email
	const user = bootstrap.user

	return (
		<footer className="w-full shrink-0 border-t-[3px] border-orange-700 bg-[#1F1A17] pt-10 text-sm text-white/60">
			<div className="mx-auto max-w-7xl px-4 md:px-6">

				{/* ── 5-column grid ── */}
				<div className="grid grid-cols-1 gap-8 border-b border-white/[0.07] pb-8 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-[1.6fr_1fr_1fr_1fr_1.1fr] lg:gap-x-8 lg:gap-y-8">

					{/* Col 1 — Brand */}
					<div className="sm:col-span-2 md:col-span-1 lg:col-span-1">
						<Brand compact className="mb-3" />
						<p className="max-w-xs text-[0.82rem] leading-relaxed text-white/[0.48]">
							Flama là nền tảng học tập đa lĩnh vực, cho phép cộng đồng cùng đóng góp và xây dựng kho
							dữ liệu bộ thẻ chuyên biệt cho mọi chủ đề. Ứng dụng áp dụng phương pháp Spaced Repetition để tối
							ưu ghi nhớ và theo dõi tiến độ hằng ngày.
						</p>
					</div>

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

					{/* Col 3 — Chợ học liệu & Đóng góp */}
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

					{/* Col 5 — Pháp lý & Contact */}
					<div>
						<FooterColumn title="Pháp lý & Hỗ trợ">
							<FooterLink to={bootstrap.links.terms || '/terms'}>Điều khoản sử dụng</FooterLink>
							<FooterLink to={bootstrap.links.privacy || '/privacy'}>Chính sách bảo mật</FooterLink>
							<FooterLink to={bootstrap.links.cookies || '/cookies'}>Chính sách cookie</FooterLink>
							<FooterLink to={bootstrap.links.support || '/support'}>Ủng hộ hệ thống</FooterLink>
						</FooterColumn>

						<h4 className="mb-2.5 mt-5 text-[0.7rem] font-bold uppercase tracking-widest text-white/35">
							Liên hệ
						</h4>
						<ul className="flex flex-col gap-2">
							{email ? (
								<MailLink email={email}>
									<Mail className="size-3.5 opacity-75" />
									{email}
								</MailLink>
							) : null}
							<li className="flex items-center gap-1.5 break-all text-[0.78rem] text-white/35">
								<Clock className="size-3.5" />
								Phản hồi trong 24–48h
							</li>
						</ul>
					</div>
				</div>

				{/* ── Copyright ── */}
				<div className="py-4 text-center text-[0.78rem] text-white/25">
					© {new Date().getFullYear()} Flama. Được phát triển với ❤️ bởi Chung Trịnh.
				</div>
			</div>
		</footer>
	)
}
