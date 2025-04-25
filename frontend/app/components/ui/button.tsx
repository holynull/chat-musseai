import { ReactNode } from "react";
import Link from "next/link";
import { LoadingSpinner } from "./loading-spinner";

interface ButtonProps {
	children: ReactNode;
	href?: string;
	onClick?: () => void;
	variant?: "primary" | "secondary" | "outline";
	size?: "sm" | "md" | "lg";
	loading?: boolean;
	disabled?: boolean;
	className?: string;
}

const variants = {
	primary: "bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-800 text-white",
	secondary: "bg-gray-800 hover:bg-gray-700 text-white",
	outline: "border border-gray-700 hover:border-blue-500 text-gray-300 hover:text-white"
};

const sizes = {
	sm: "px-4 py-2 text-sm",
	md: "px-6 py-3",
	lg: "px-8 py-4 text-lg"
};

export function Button({
	children,
	href,
	onClick,
	variant = "primary",
	size = "md",
	loading = false,
	disabled = false,
	className = ""
}: ButtonProps) {
	const baseStyles = `
    inline-flex items-center justify-center
    rounded-lg font-semibold
    transition-all duration-300
    hover:shadow-lg hover:shadow-blue-500/20
    disabled:opacity-50 disabled:cursor-not-allowed
    ${variants[variant]}
    ${sizes[size]}
    ${className}
  `;

	const content = (
		<>
			{loading && <LoadingSpinner className="mr-2" />}
			{children}
		</>
	);

	if (href) {
		return (
			<Link href={href} className={baseStyles}>
				{content}
			</Link>
		);
	}

	return (
		<button
			onClick={onClick}
			disabled={disabled || loading}
			className={baseStyles}
		>
			{content}
		</button>
	);
}