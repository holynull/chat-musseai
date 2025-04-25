"use client";

import { ComponentPropsWithoutRef, forwardRef } from "react";

import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "../tooltip";
import { Button } from "../button";
import { cn } from "../../../utils/cn";

export type TooltipIconButtonProps = ComponentPropsWithoutRef<typeof Button> & {
	tooltip: string;
	side?: "top" | "bottom" | "left" | "right";
};

export const TooltipIconButton = forwardRef<
	HTMLButtonElement,
	TooltipIconButtonProps
>(({ children, tooltip, side = "bottom", className, ...rest }, ref) => {
	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger asChild>
					<Button
						size="sm"
						{...rest}
						className={cn("size-6 p-1", className)}
					>
						{children}
						<span className="sr-only">{tooltip}</span>
					</Button>
				</TooltipTrigger>
				<TooltipContent side={side}>{tooltip}</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
});

TooltipIconButton.displayName = "TooltipIconButton";
