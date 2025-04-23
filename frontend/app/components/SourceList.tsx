import "react-toastify/dist/ReactToastify.css";
import { useAssistantToolUI } from "@assistant-ui/react";
import { Key, useState } from "react";
import { LoaderCircle, Globe, Plus } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Sheet, SheetContent, SheetTrigger } from "./ui/sheet";
import { TooltipIconButton } from "./ui/assistant-ui/tooltip-icon-button";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "./ui/tooltip";

export type Source = {
	link: string;
	title: string;
	imageUrl: string;
	snippet: string;
};
function imageTag(img_src: string) {
	if (img_src) {
		return <img src={img_src} className="w-full h-[120px] object-cover rounded-sm" alt="" />
	} else {
		return <div className="w-full h-[120px] bg-gray-700 flex items-center justify-center rounded-sm">
			<Globe className="w-8 h-8 text-gray-400" />
		</div>
	}
}
const filterSources = (sources: Source[]) => {
	const filtered: Source[] = [];
	const urlMap = new Map<string, number>();
	const indexMap = new Map<number, number>();
	sources.forEach((source, i) => {
		const { link } = source;
		const index = urlMap.get(link);
		if (index === undefined) {
			urlMap.set(link, i);
			indexMap.set(i, filtered.length);
			filtered.push(source);
		} else {
			const resolvedIndex = indexMap.get(index);
			if (resolvedIndex !== undefined) {
				indexMap.set(i, resolvedIndex);
			}
		}
	});
	return { filtered, indexMap };
};

export function SourceBubble(
	{ source: source }: { source: Source },
) {
	return (
		<a
			href={source.link}
			target="_blank"
			rel="noopener noreferrer"
			className="no-underline"
		>
			<Card className="md:w-[250px] sm:w-[250px] w-full md:max-w-full bg-inherit border-gray-500 flex flex-col gap-2 hover:border-blue-400 transition-colors">
				<CardHeader className="flex-shrink-0 px-3 pt-2 pb-0">
					<TooltipProvider>
						<Tooltip>
							<TooltipTrigger asChild>
								<CardTitle className="text-sm font-light text-gray-300 line-clamp-2 overflow-hidden">
									{source.title}
								</CardTitle>
							</TooltipTrigger>
							<TooltipContent className="max-w-[600px] whitespace-pre-wrap">
								<p>{source.title}</p>
							</TooltipContent>
						</Tooltip>
					</TooltipProvider>
				</CardHeader>
				<CardContent className="flex flex-col flex-grow px-3 pb-2 justify-between mt-auto">
					<div className="flex flex-col gap-1 mt-auto">
						{imageTag(source.imageUrl)}
						<p className="text-sm font-light text-gray-300 line-clamp-3 overflow-hidden mt-2">
							{source.snippet}
						</p>
					</div>
				</CardContent>
			</Card>
		</a>
	);
}
export const useSourceList = () => useAssistantToolUI({
	toolName: "source_list",
	render: (input) => {
		// const expert_name = nodeToExpertName(input.args.node_name);
		const sources: Source[] = input.args.sources;
		const { filtered, indexMap } = filterSources(sources);
		const [highlighedSourceLinkStates, setHighlightedSourceLinkStates] = useState(
			filtered.map(() => false),
		);
		return (
			<div className="flex flex-col mb-4 sm:mt-6 md:mt-8">
				<span className="flex flex-row gap-2 items-center justify-start pb-4 text-gray-300">
					<Globe className="w-5 h-5" />
					<p className="text-xl">Search Result</p>
				</span>
				<div className="mb-10">
					<div className="flex flex-wrap items-start justify-start gap-4">
						{filtered.map((source: Source, index) => (
							<SourceBubble
								key={`${source.link}-${index}`}
								source={source}
							/>
						))}
					</div>
				</div>
			</div>
		)
	},
});
