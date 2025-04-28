import "react-toastify/dist/ReactToastify.css";
import { useAssistantToolUI } from "@assistant-ui/react";
import { Key, useState } from "react";
import { LoaderCircle, Globe, Plus } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Sheet, SheetContent, SheetTrigger } from "./ui/sheet";
import { TooltipIconButton } from "./ui/assistant-ui/tooltip-icon-button";
import Image from "next/image";
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

// 修改 imageTag 函数，使图片高度响应式
function imageTag(img_src: string) {
    if (img_src) {
        return (
            <div className="relative w-full h-[200px] mt-2 overflow-hidden rounded">
                <Image
                    src={img_src}
                    fill={true}
                    sizes="(max-width: 768px) 100vw, 50vw"
                    className="object-cover"
                    alt="Source image"
                    loading="lazy"
                />
            </div>
        );
    } else {
        return (
            <div className="w-full h-[200px] bg-gray-700 flex items-center justify-center rounded mt-2">
                <Globe className="w-6 h-6 text-gray-400" />
            </div>
        );
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

export function SourceBubble({ source }: { source: Source }) {
	return (
		<a
			href={source.link}
			target="_blank"
			rel="noopener noreferrer"
			// 修改宽度控制，确保在移动端不会过宽
			className="no-underline block w-full"
		>
			<Card className="w-full border-gray-500 hover:border-blue-400 transition-colors">
				<CardHeader className="px-3 pt-2 pb-0">
					<TooltipProvider>
						<Tooltip>
							<TooltipTrigger asChild>
								<CardTitle className="text-sm font-medium text-gray-300 line-clamp-2">
									{source.title}
								</CardTitle>
							</TooltipTrigger>
							<TooltipContent side="top" className="max-w-[280px]">
								<p>{source.title}</p>
							</TooltipContent>
						</Tooltip>
					</TooltipProvider>
				</CardHeader>
				<CardContent className="px-3 pb-2 pt-1">
					{imageTag(source.imageUrl)}
					<p className="text-xs sm:text-sm text-gray-300 line-clamp-3 mt-2">
						{source.snippet}
					</p>
				</CardContent>
			</Card>
		</a>
	);
}

const SourceListComponent = ({ sources }: { sources: Source[] }) => {
	const { filtered } = filterSources(sources);

	return (
		<div className="flex flex-col mb-4 mt-4 w-full max-w-full">
			<span className="flex flex-row gap-2 items-center mb-3 px-3">
				<Globe className="w-4 h-4" />
				<p className="text-md text-gray-300">Search Result</p>
			</span>
			{/* 添加最大宽度限制和内边距控制 */}
			<div className="w-full px-3">
				<div className="flex flex-col gap-3">
					{filtered.map((source: Source, index) => (
						<SourceBubble
							key={`${source.link}-${index}`}
							source={source}
						/>
					))}
				</div>
			</div>
		</div>
	);
};

// 在useAssistantToolUI中使用这个组件
export const useSourceList = () => useAssistantToolUI({
	toolName: "source_list",
	render: (input) => {
		const sources: Source[] = input.args.sources;
		return <SourceListComponent sources={sources} />;
	},
});