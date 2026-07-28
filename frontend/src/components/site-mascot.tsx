import { Link, useLocation } from 'react-router-dom'

const visiblePaths = new Set(['/', '/dashboard'])

export function SiteMascot() {
	const { pathname } = useLocation()

	if (!visiblePaths.has(pathname)) return null

	return (
		<Link
			to="/support"
			aria-label="Trang ủng hộ"
			className="fixed right-4 bottom-4 z-50 rounded-full outline-offset-2 focus-visible:outline-2 focus-visible:outline-orange-400 max-md:right-2 max-md:bottom-2 max-sm:right-1 max-sm:bottom-1"
		>
			<img
				src="/pet.svg"
				alt=""
				aria-hidden="true"
				className="block w-[124px] select-none max-md:w-24 max-sm:w-[78px]"
			/>
		</Link>
	)
}
