import { ExternalLink } from "lucide-react";
import { LangSmithSVG } from "./icons/langsmith";
import { TooltipIconButton } from "./ui/assistant-ui/tooltip-icon-button";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useCallback } from "react";

export const useLangSmithLinkToolUI = () =>
  useAssistantToolUI({
    toolName: "langsmith_tool_ui",
    render: useCallback((input) => {
      return (
        <TooltipIconButton
          tooltip="View run in LangSmith"
          variant="ghost"
          size="sm"
          className="inline-flex items-center gap-1.5 px-2 py-1 text-xs hover:bg-accent/50 transition-all duration-200"
          onClick={() => window.open(input.args.sharedRunURL, "_blank")}
        >
          <ExternalLink className="w-3 h-3 text-muted-foreground" />
          <LangSmithSVG className="w-4 h-4 text-orange-600 hover:text-orange-700 transition-colors" />
        </TooltipIconButton>
      );
    }, []),
  });