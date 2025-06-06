import { Client } from "@langchain/langgraph-sdk";
import { RemoteRunnable } from "langchain/runnables/remote"

export function createClient() {
	// const remoteChain = new RemoteRunnable({
	// 	url: process.env.NEXT_PUBLIC_CHAT_URL ? process.env.NEXT_PUBLIC_CHAT_URL : "",
	// 	options: {
	// 		timeout: 3000000,
	// 	},
	// });
	// return remoteChain;
	const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3000/api";
	return new Client({
		apiUrl,
		defaultHeaders: typeof window !== 'undefined' ? {
			Authorization: `Bearer ${localStorage.getItem("auth_token")}`
		} : {}
	});
}

export function nodeToStep(node: string) {
	switch (node) {
		case "analyze_and_route_query":
			return 0;
		case "create_research_plan":
			return 1;
		case "conduct_research":
			return 2;
		case "respond":
			return 3;
		default:
			return 0;
	}
}

export function addDocumentLinks(
	text: string,
	inputDocuments: Record<string, any>[],
): string {
	return text.replace(/\[(\d+)\]/g, (match, number) => {
		const index = parseInt(number, 10);
		if (index >= 0 && index < inputDocuments.length) {
			const document = inputDocuments[index];
			if (document && document.metadata && document.metadata.source) {
				return `[[${number}]](${document.metadata.source})`;
			}
		}
		// Return the original match if no corresponding document is found
		return match;
	});
}
