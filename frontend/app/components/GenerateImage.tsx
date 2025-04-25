"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import Image from "next/image";
import { useState, useEffect } from "react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Skeleton } from "./ui/skeleton";

// Create a proper React component that can use hooks
interface GenerateImageInput {
	args: {
		data: string | { url: string } | Array<string | { url: string }>;
	};
}

const GenerateImageComponent = ({ input }: { input: GenerateImageInput }) => {
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [imageUrl, setImageUrl] = useState<string | null>(null);

	useEffect(() => {
		// Reset states when input changes
		setIsLoading(true);
		setError(null);

		try {
			const data = input.args.data;

			// Check if data is a string (direct URL)
			if (typeof data === 'string') {
				setImageUrl(data);
			}
			// Check if data is an object with url property
			else if (data && typeof data === 'object' && 'url' in data) {
				setImageUrl(data.url);
			}
			// Check if data is an array of results
			else if (Array.isArray(data) && data.length > 0) {
				// Take the first image if it's an array
				setImageUrl(typeof data[0] === 'string' ? data[0] : data[0]?.url || null);
			} else {
				throw new Error("Invalid image data format");
			}
		} catch (err) {
			console.error("Error parsing image data:", err);
			setError("Failed to load image data");
		} finally {
			setIsLoading(false);
		}
	}, [input.args.data]);

	const handleImageLoad = () => {
		setIsLoading(false);
	};

	const handleImageError = () => {
		setIsLoading(false);
		setError("Failed to load image");
	};

	const handleDownload = () => {
		if (!imageUrl) return;

		const link = document.createElement('a');
		link.href = imageUrl;
		link.download = `generated-image-${Date.now()}.png`;
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
	};

	if (!imageUrl) return null;

	return (
		<Card className="overflow-hidden max-w-full w-full p-2 flex flex-col items-center">
			{isLoading && (
				<div className="w-full aspect-square max-w-xl">
					<Skeleton className="h-full w-full rounded-md" />
				</div>
			)}

			{error && (
				<div className="text-red-500 p-4 text-center">
					<p>{error}</p>
					<p className="text-sm mt-1 text-gray-500">Raw data: {JSON.stringify(input.args.data)}</p>
				</div>
			)}

			{imageUrl && !error && (
				<div className="relative w-full flex flex-col items-center">
					<div className="relative max-w-xl w-full">
						<Image
							src={imageUrl}
							alt="Generated image"
							className="w-full rounded-md object-contain"
							width={500}
							height={500}
							style={{ maxHeight: "500px" }}
							onLoad={handleImageLoad}
							onError={handleImageError as any}
						/>
					</div>

					<div className="mt-2 flex justify-end w-full max-w-xl">
						<Button
							onClick={handleDownload}
							variant="outline"
							size="sm"
							className="text-sm"
						>
							Download
						</Button>
					</div>
				</div>
			)}
		</Card>
	);
};

// Export the custom hook with proper structure
export const useGenerateImage = () => useAssistantToolUI({
	toolName: "gen_images",
	render: (input) => <GenerateImageComponent input={input} />
});