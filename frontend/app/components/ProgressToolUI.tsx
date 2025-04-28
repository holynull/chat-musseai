import { useAssistantToolUI } from "@assistant-ui/react";
import { Progress } from "./ui/progress";
import { cn } from "../utils/cn";
import { useCallback } from "react";

export const stepToProgressFields = (step: { text: string, progress: number }) => {
	if (step.progress >= 100) {
		return {
			text: step.text + ", Done!",
			progress: 100,
		}
	} else {
		return {
			text: step.text,
			progress: step.progress,
		}
	}
};

export const useProgressToolUI = () =>
	useAssistantToolUI({
		toolName: "progress",
		// Wrap the component in a useCallback to keep the identity stable.
		// Allows the component to be interactable and not be re-rendered on every state change.
		render: useCallback((input) => {
			const { text, progress } = stepToProgressFields(input.args.step);

			return (
				<div className="flex flex-col sm:flex-row w-full max-w-full items-start sm:items-center justify-start gap-2 sm:gap-3 pb-3 sm:pb-4 px-1 mt-3 sm:mt-[16px]">
					<Progress
						value={progress}
						indicatorClassName="bg-gray-700"
						className="w-full max-w-[375px]"
					/>
					<p
						className={cn(
							"text-gray-500 text-sm font-light break-words",
							progress !== 100 ? "animate-pulse" : "",
						)}
					>
						{text}
					</p>
				</div>
			);
		}, []),
	});