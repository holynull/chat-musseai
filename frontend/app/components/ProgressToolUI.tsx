import { useAssistantToolUI } from "@assistant-ui/react";
import { Progress } from "./ui/progress";
import { cn } from "../utils/cn";
import { useCallback } from "react";
import { text } from "stream/consumers";

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
				<div className="flex flex-row md:max-w-[550px] w-full items-center justify-start gap-3 pb-4 ml-[-5px] mt-[16px]">
					<Progress
						value={progress}
						indicatorClassName="bg-gray-700"
						className="w-[375px]"
					/>
					<p
						className={cn(
							"text-gray-500 text-sm font-light",
							progress !== 100 ? "animate-pulse" : "",
						)}
					>
						{text}
					</p>
				</div>
			);
		}, []),
	});
