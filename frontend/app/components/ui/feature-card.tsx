import Link from "next/link";
import { ReactNode } from "react";

interface FeatureCardProps {
	icon: ReactNode;
	title: string;
	description: string;
	link: string;
	linkText: string;
	color: "blue" | "green" | "purple";
}

const colorStyles = {
	blue: {
		icon: "text-blue-400 bg-blue-400/10",
		hover: "group-hover:text-blue-400 group-hover:border-blue-500/50 group-hover:shadow-blue-500/10"
	},
	green: {
		icon: "text-green-400 bg-green-400/10",
		hover: "group-hover:text-green-400 group-hover:border-green-500/50 group-hover:shadow-green-500/10"
	},
	purple: {
		icon: "text-purple-400 bg-purple-400/10",
		hover: "group-hover:text-purple-400 group-hover:border-purple-500/50 group-hover:shadow-purple-500/10"
	}
};

export function FeatureCard({ icon, title, description, link, linkText, color }: FeatureCardProps) {
	return (
		<div className={`p-8 bg-gray-800/60 backdrop-blur-lg border border-gray-700 rounded-xl transition-all duration-300 hover:shadow-lg hover:-translate-y-1 group ${colorStyles[color].hover}`}>
			<div className={`mb-4 p-3 rounded-full w-16 h-16 flex items-center justify-center mx-auto group-hover:scale-110 transition-transform ${colorStyles[color].icon}`}>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					className="h-10 w-10"
					fill="none"
					viewBox="0 0 24 24"
					stroke="currentColor"
				>
					{icon}
				</svg>
			</div>

			<h2 className="text-2xl font-semibold mb-3 transition-colors">
				{title}
			</h2>

			<p className="text-gray-400 group-hover:text-gray-300 transition-colors">
				{description}
			</p>

			<div className="mt-6">
				<Link
					href={link}
					className={`inline-flex items-center ${colorStyles[color].icon.split(' ')[0]} group-hover:underline`}
				>
					{linkText}
					<svg
						xmlns="http://www.w3.org/2000/svg"
						className="h-4 w-4 ml-1 transition-transform group-hover:translate-x-1"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
					>
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							strokeWidth={2}
							d="M9 5l7 7-7 7"
						/>
					</svg>
				</Link>
			</div>
		</div>
	);
}