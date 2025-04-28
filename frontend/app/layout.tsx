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
	openGraph: {
		type: "website",
		locale: "en_US",
		url: "https://musseai.com",
		siteName: "Musse AI",
		title: "Musse AI - Intelligent Crypto Assistant",
		description: "Your intelligent AI assistant for cryptocurrency and blockchain information.",
		images: [
			{
				url: "/images/og-image.jpg",
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