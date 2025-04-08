import { useAssistantToolUI } from "@assistant-ui/react";
import { BrainCog } from "lucide-react";

export const nodeToExpertName = (node_name: string): string => {
	switch (node_name) {
		case "node_llm_musseai":
			return "Musse AI";
		case "node_llm_image":
			return "Image Generator";
		case "node_llm_quote":
			return "Market Analysis";
		case "node_llm_search":
			return "Search";
		case "node_llm_swap":
			return "Swap Expert";
		case "node_llm_wallet":
			return "Cryptocurrency Wallet";
		default:
			return "Musse AI";
	}
};

export const useAnswerHeaderToolUI = () =>
	useAssistantToolUI({
		toolName: "answer_header",
		render: (input) => {
			const expert_name = nodeToExpertName(input.args.node_name);
			return (
				<div className="flex flex-row gap-2 items-center justify-start pb-4 text-gray-300">
					<BrainCog className="w-5 h-5" />
					<p className="text-xl">{expert_name}</p>
				</div>
			);
		},
	});
