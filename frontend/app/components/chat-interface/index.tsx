"use client";

import { ThreadPrimitive } from "@assistant-ui/react";
import { type FC } from "react";
import Image from 'next/image';

import { ArrowDownIcon, Wallet } from "lucide-react";
import { useAnswerHeaderToolUI } from "../AnswerHeaderToolUI";
import { useProgressToolUI } from "../ProgressToolUI";
import { SelectModel } from "../SelectModel";
import { SuggestedQuestions } from "../SuggestedQuestions";
import { TooltipIconButton } from "../ui/assistant-ui/tooltip-icon-button";
import { AssistantMessage, UserMessage } from "./messages";
import { ChatComposer, ChatComposerProps } from "./chat-composer";
import { cn } from "@/app/utils/cn";
import { useSourceList } from "../SourceList";
import { useLangSmithLinkToolUI } from "../LangSmithLinkToolUI"
import { WalletIndicator } from "../WalletIndicator";
import { useSendEVMTransaction } from "../SendEVMTransation";
import { useSendSolanaTransaction } from "../SendSolanaTransation";
import { useAvailableTokens } from "../AvailableTokens";
import { useSwapQuote } from "../SwapQuote";
import { useTransactionRecords } from "../TransactionRecords";
import { useTransactionDetail } from "../TransactionDetail";
import { useGenerateApproveERC20 } from "../GenerateApproveERC20";
import { useGetBalanceOfAddress } from "../GetBalanceOfAddress";
import { useGetERC20Decimals } from "../GetERC20Decimals";
import { useAllowanceERC20 } from "../AllowanceERC20";
import { useGetSOLBalanceOfAddress } from "../GetSOLBalanceOfAddress";
import { useGetSPLBalanceOfAddress } from "../GetSPLBalanceOfAddress";
import { useLatestQuote } from "../LatestQuote";
import { useBuySellSignal } from "../BuySellSignal";
import { useGetTokenMetadata } from "../GetTokenMetadata";
import { useGetLatestContent } from "../GetLatestContent";
import { useGetCommunityTrendingToken } from "../GetCommunityTrendingToken";
import { useGenerateImage } from "../GenerateImage";

export interface ThreadChatProps extends ChatComposerProps {
	currentThreadId: string | null
}



export const ThreadChat: FC<ThreadChatProps> = (props: ThreadChatProps) => {
	const isEmpty = props.messages.length === 0;

	useAnswerHeaderToolUI();
	useProgressToolUI();
	useSourceList();
	useLangSmithLinkToolUI();
	useSendEVMTransaction();
	useSendSolanaTransaction();
	useAvailableTokens();
	useSwapQuote();
	useTransactionRecords();
	useTransactionDetail();
	useGenerateApproveERC20();
	useGetBalanceOfAddress();
	useGetERC20Decimals();
	useAllowanceERC20();
	useGetSOLBalanceOfAddress();
	useGetSPLBalanceOfAddress();
	useLatestQuote();
	useBuySellSignal();
	useGetTokenMetadata();
	useGetLatestContent();
	useGetCommunityTrendingToken();
	useGenerateImage();

	return (
		<ThreadPrimitive.Root className="flex flex-col h-screen overflow-hidden w-full h-full">
			{!isEmpty ? (
				<ThreadPrimitive.Viewport autoScroll={true}
					className={cn(
						"flex-1 overflow-y-auto scroll-smooth bg-inherit transition-all duration-300 ease-in-out w-full h-full",
						isEmpty ? "pb-[30vh] sm:pb-[50vh]" : "pb-12 pt-12 sm:pb-12 md:pb-10",
						"scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-transparent",
					)}
				>
					<div className="px-2 sm:px-4 md:pl-8 lg:pl-24 mt-2 max-w-full">
						<ThreadPrimitive.Messages
							components={{
								UserMessage: UserMessage,
								AssistantMessage: AssistantMessage,
							}}
						/>
					</div>
				</ThreadPrimitive.Viewport>
			) : null}
			<ThreadChatScrollToBottom />
			{isEmpty ? (
				<div className="flex items-center justify-center flex-grow my-auto">
					<div className="flex flex-col items-center mx-4 md:mt-0 mt-12 mb-4 sm:my-auto">
						<div className="logo-container relative mb-8">
							{/* 发光效果 */}
							<div className="absolute inset-0 rounded-full bg-gradient-to-r from-blue-500/30 to-purple-500/30 blur-xl animate-pulse-slow"></div>

							{/* 旋转的外环 */}
							<div className="absolute inset-0 rounded-full border-2 border-blue-400/30 animate-spin-slow"></div>

							{/* Logo图片容器 */}
							<div className="relative z-10 w-28 h-28 rounded-full overflow-hidden">
								<Image
									src="/images/logo.png"
									alt="Musse AI Logo"
									fill
									priority
									className="object-fill rounded-full"
									style={{ transform: 'scale(1.1)' }}
								/>
							</div>
						</div>
						<div className="mb-4 sm:mb-[24px] mt-1 sm:mt-2 flex items-center gap-2 justify-center">
							<SelectModel />
							<WalletIndicator />
						</div>
						<div className="md:mb-8 mb-4">
							<SuggestedQuestions />
						</div>
						<ChatComposer
							submitDisabled={props.submitDisabled}
							messages={props.messages}
							currentThreadId={props.currentThreadId}
						/>
					</div>
				</div>
			) : (
				<ChatComposer
					submitDisabled={props.submitDisabled}
					messages={props.messages}
					currentThreadId={props.currentThreadId}
				/>
			)}
		</ThreadPrimitive.Root>
	);
};

const ThreadChatScrollToBottom: FC = () => {
	return (
		<ThreadPrimitive.ScrollToBottom asChild>
			<TooltipIconButton
				tooltip="Scroll to bottom"
				variant="outline"
				className="absolute bottom-28 left-1/2 transform -translate-x-1/2 rounded-full disabled:invisible bg-white bg-opacity-75"
			>
				<ArrowDownIcon className="text-gray-600 hover:text-gray-800 transition-colors ease-in-out" />
			</TooltipIconButton>
		</ThreadPrimitive.ScrollToBottom>
	);
};
