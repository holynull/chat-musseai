"use client";

import React from "react";
import { GraphProvider } from "../contexts/GraphContext";
import { ChatLangChain } from "../components/ChatLangChain";
import { ChakraProvider, extendTheme } from "@chakra-ui/react";
import { AuthGuard } from "../components/AuthGuard";
import { BackgroundDecoration } from "../components/ui/background-decoration";

const theme = extendTheme({
	styles: {
		global: {
			body: {
				color: '#f8f8f8',
				lineHeight: '.8em',
			},
		},
	},
});

export default function Page(): React.ReactElement {
	return (
		<main className="w-full h-full">
			{/* 添加背景装饰 */}
			<BackgroundDecoration />

			{/* 添加渐变背景 */}
			<div className="absolute inset-0 bg-gradient-to-b from-blue-900/30 to-purple-900/30 z-0"></div>
			<React.Suspense fallback={null}>
				<ChakraProvider theme={theme}>
					<AuthGuard>
						<GraphProvider>
							<ChatLangChain />
						</GraphProvider>
					</AuthGuard>
				</ChakraProvider>
			</React.Suspense>
		</main>);
}