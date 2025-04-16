"use client";

import React from "react";
import { GraphProvider } from "./contexts/GraphContext";
import { ChatLangChain } from "./components/ChatLangChain";
import { ChakraProvider, extendTheme } from "@chakra-ui/react";


const theme = extendTheme({
	styles: {
		global: {
			body: {
				color: '#f8f8f8', // 这将会修改 --chakra-colors-chakra-body-text
			},
		},
	},
});

export default function Page(): React.ReactElement {
	return (
		<main className="w-full h-full">
			<React.Suspense fallback={null}>
				<ChakraProvider theme={theme}>
					<GraphProvider>
						<ChatLangChain />
					</GraphProvider>
				</ChakraProvider>
			</React.Suspense>
		</main>
	);
}
