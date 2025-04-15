import "./globals.css";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { AppKit } from './contexts/appkit';

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
	title: "Musse AI",
	description: "Chatbot for Musse AI",
};

export default function RootLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	return (
		<html lang="en" className="h-full">
			<body className={`${inter.className} h-full`}>
				<div
					className="flex flex-col h-full w-full"
					style={{ background: "rgb(38, 38, 41)" }}
				>
					<AppKit cookies={null}>
						<NuqsAdapter>{children}</NuqsAdapter>
					</AppKit>
				</div>
			</body>
		</html>
	);
}
