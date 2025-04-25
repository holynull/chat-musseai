"use client";

import React from "react";
import { GraphProvider } from "../contexts/GraphContext";
import { ChatLangChain } from "../components/ChatLangChain";
import { ChakraProvider, extendTheme } from "@chakra-ui/react";
import { AuthGuard } from "../components/AuthGuard";

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