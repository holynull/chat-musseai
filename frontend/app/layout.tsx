import "./globals.css";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { AppKit } from './contexts/appkit';
import { UserProvider } from './contexts/UserContext';

const inter = Inter({
	subsets: ["latin"],
	display: 'swap',
	variable: '--font-inter',
});

export const metadata: Metadata = {
	title: "Musse AI - Intelligent Crypto Assistant",
	description: "Your intelligent AI assistant for cryptocurrency and blockchain information, providing real-time insights and seamless transactions.",
	keywords: "AI, cryptocurrency, blockchain, trading, crypto assistant, token swap",
	authors: [{ name: "Musse AI Team" }],
	icons: {
		icon: '/images/favicon.ico', // 基于public目录的路径
		// 可选：添加更多格式和尺寸
		// apple: '/images/apple-icon.png',
		// shortcut: '/images/favicon.ico',
	},
	openGraph: {
		type: "website",
		locale: "en_US",
		url: "https://musseai.com",
		siteName: "Musse AI",
		title: "Musse AI - Intelligent Crypto Assistant",
		description: "Your intelligent AI assistant for cryptocurrency and blockchain information.",
		images: [
			{
				url: "https://musseai.com/images/logo.png",
				width: 1200,
				height: 630,
				alt: "Musse AI Preview"
			}
		]
	},
	twitter: {
		card: "summary_large_image",
		title: "Musse AI - Intelligent Crypto Assistant",
		description: "Your intelligent AI assistant for cryptocurrency and blockchain information.",
		images: ["/images/twitter-image.jpg"]
	}
};

export default function RootLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	return (
		<html lang="en" className={`${inter.variable}`}>
			<head><link rel="icon" href="/images/favicon.ico" /></head>
			<body className="font-sans antialiased">
				<div
					className="flex flex-col w-full"
					style={{ background: "rgb(38, 38, 41)" }}
				>
					<AppKit cookies={null}>
						<UserProvider>
							<NuqsAdapter>{children}</NuqsAdapter>
						</UserProvider>
					</AppKit>
				</div>
			</body>
		</html>
	);
}