import { Link } from 'react-router-dom'
import { Clock, Mail } from 'lucide-react'
import { Brand } from '@/shared/components/Brand'
import type { FrontendBootstrap } from '@/shared/types/api'

const updates = [
	{ tag: 'Giao diện', text: 'Màn học được tối ưu lại để gọn hơn và ít gây xao nhãng.' },
	{ tag: 'Tập trung', text: 'Thêm chế độ toàn màn hình để bạn tập trung trong suốt buổi ôn.' },
	{ tag: 'Chỉnh sửa', text: 'Cập nhật thẻ an toàn hơn, giảm nguy cơ ghi đè nhầm dữ liệu cũ.' },
	{ tag: 'VoiceVox', text: 'Thêm tạo âm thanh tiếng Nhật trực tiếp từ từ vựng với VoiceVox.' },
]

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
				className="inline-flex items-center gap-1.5 text-white/60 transition-colors hover:text-orange-400"
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
				className="inline-flex items-center gap-1.5 break-all text-white/60 transition-colors hover:text-orange-400"
			>
				{children}
			</a>
		</li>
	)
}

function ProductLinks({ bootstrap }: { bootstrap: FrontendBootstrap }) {
	if (bootstrap.user) {
		return (
			<>
				<FooterLink to={bootstrap.links.dashboard}>Tổng quan học tập</FooterLink>
				<FooterLink to="/browse">Kho từ vựng</FooterLink>
				<FooterLink to={bootstrap.links.study}>Học flashcard</FooterLink>
				<FooterLink to={bootstrap.links.shared_note_types}>Shared NoteTypes</FooterLink>
				<FooterLink to={bootstrap.links.shared_decks}>Shared Decks</FooterLink>
			</>
		)
	}
	return (
		<>
			<FooterLink to="/">Trang giới thiệu</FooterLink>
			<FooterLink to="/login">Đăng nhập</FooterLink>
			<FooterLink to="/register">Đăng ký</FooterLink>
		</>
	)
}

function SupportLinks({ bootstrap }: { bootstrap: FrontendBootstrap }) {
	const email = bootstrap.support_contact_email
	const user = bootstrap.user

	return (
		<>
			{user?.is_admin && (
				<>
					<FooterLink to={bootstrap.links.note_types}>Quản lý loại thẻ</FooterLink>
					{bootstrap.links.admin_users && (
						<FooterLink to={bootstrap.links.admin_users}>Người dùng &amp; phân quyền</FooterLink>
					)}
				</>
			)}
			{user && !user.is_admin && (
				<>
					<FooterLink to={bootstrap.links.dashboard}>Trang học tập</FooterLink>
					<FooterLink to={bootstrap.links.shared_note_types}>Khám phá NoteTypes</FooterLink>
					<FooterLink to={bootstrap.links.shared_decks}>Khám phá Decks</FooterLink>
				</>
			)}
			{!user && (
				<FooterLink to="/login">Đăng nhập để học</FooterLink>
			)}
			{email ? (
				<>
					<MailLink email={email}>Báo lỗi / Góp ý</MailLink>
					<MailLink email={email}>Liên hệ</MailLink>
				</>
			) : (
				<li className="text-white/35">Liên hệ quản trị viên để được hỗ trợ</li>
			)}
		</>
	)
}

export function SiteFooter({ bootstrap }: { bootstrap: FrontendBootstrap }) {
	const email = bootstrap.support_contact_email

	return (
		<footer className="w-full shrink-0 border-t-[3px] border-orange-700 bg-[#1F1A17] pt-10 text-sm text-white/60">
			<div className="mx-auto max-w-7xl px-4 md:px-6">

				{/* ── 4-column grid ── */}
				<div className="grid grid-cols-1 gap-6 border-b border-white/[0.07] pb-8 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1.4fr] lg:gap-x-12 lg:gap-y-8">

					{/* Col 1 — Brand */}
					<div className="sm:col-span-2 lg:col-span-1">
						<Brand compact className="mb-3" />
						<p className="max-w-xs text-[0.82rem] leading-relaxed text-white/[0.48]">
							Flama là nền tảng học tiếng Nhật tích hợp quản lý từ vựng, học flashcard và chia sẻ bộ
							học liệu. Ứng dụng áp dụng phương pháp ôn tập ngắt quãng để tối ưu ghi nhớ và theo
							dõi tiến độ hằng ngày.
						</p>
					</div>

					{/* Col 2 — Product */}
					<FooterColumn title="Sản phẩm">
						<ProductLinks bootstrap={bootstrap} />
					</FooterColumn>

					{/* Col 3 — Support */}
					<FooterColumn title="Quản lý & hỗ trợ">
						<SupportLinks bootstrap={bootstrap} />
					</FooterColumn>

					{/* Col 4 — Legal + Contact */}
					<div>
						<FooterColumn title="Pháp lý">
							<FooterLink to={bootstrap.links.terms}>Điều khoản sử dụng</FooterLink>
							<FooterLink to={bootstrap.links.privacy}>Chính sách bảo mật</FooterLink>
							<FooterLink to={bootstrap.links.cookies}>Chính sách cookie</FooterLink>
							<FooterLink to={bootstrap.links.support}>Ủng hộ duy trì hệ thống</FooterLink>
						</FooterColumn>

						<h4 className="mb-3 mt-5 text-[0.7rem] font-bold uppercase tracking-widest text-white/35">
							Liên hệ
						</h4>
						<ul className="flex flex-col gap-2">
							{email && (
								<MailLink email={email}>
									<Mail className="size-3.5 opacity-75" />
									{email}
								</MailLink>
							)}
							<li className="flex items-center gap-1.5 break-all text-[0.78rem] text-white/35">
								<Clock className="size-3.5" />
								Phản hồi trong 24–48h (ngày làm việc)
							</li>
						</ul>
					</div>
				</div>

				{/* ── Recent updates ── */}
				<section className="border-b border-white/[0.07] py-4" aria-labelledby="footer-updates-title">
					<div className="mb-3 flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between">
						<h4
							id="footer-updates-title"
							className="text-[0.7rem] font-bold uppercase tracking-widest text-white/35"
						>
							Cập nhật gần đây · 03/2026
						</h4>
						<Link
							to="/#landing-updates"
							className="text-[0.78rem] font-bold text-orange-300 hover:text-orange-200"
						>
							Xem chi tiết
						</Link>
					</div>
					<ul className="grid grid-cols-1 gap-x-5 gap-y-2 sm:grid-cols-2">
						{updates.map((u) => (
							<li key={u.tag} className="flex items-start gap-2">
								<span className="shrink-0 rounded-full border border-orange-500/30 bg-orange-500/[0.14] px-2 py-px text-[0.66rem] font-bold uppercase tracking-wide text-orange-200">
									{u.tag}
								</span>
								<span className="break-all text-[0.8rem] leading-relaxed text-white/[0.54]">
									{u.text}
								</span>
							</li>
						))}
					</ul>
				</section>

				{/* ── Copyright ── */}
				<div className="py-4 text-center text-[0.78rem] text-white/25">
					© {new Date().getFullYear()} Flama. Được phát triển với ❤️ bởi Chung Trịnh.
				</div>
			</div>
		</footer>
	)
}
