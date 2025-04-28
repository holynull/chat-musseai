"use client";

import {
	MessagePrimitive,
	useMessage,
	useThreadRuntime,
} from "@assistant-ui/react";
import { type FC, ReactNode } from "react";
import Image from 'next/image';

import { MarkdownText } from "../ui/assistant-ui/markdown-text";
import { UserMessageAttachments } from "../ui/assistant-ui/attachment";
import { ToolFallback } from "../ui/assistant-ui/tool-fallback";

// 消息容器组件
type MessageContainerProps = {
	children: ReactNode;
	isUser?: boolean;
};

const MessageContainer: FC<MessageContainerProps> = ({ children, isUser = false }) => {
	return (
		<MessagePrimitive.Root
			className={`
        flex w-full md:max-w-4xl
        mx-auto max-w-[95%] md:mx-0
        py-2 md:py-4
        ${isUser ? 'pt-2 sm:pt-4' : ''}
      `}
		>
			<div className="flex flex-col space-y-2 mb-6 w-full">
				<div className={`flex items-start ${isUser ? 'justify-end' : ''}`}>
					{children}
				</div>
			</div>
		</MessagePrimitive.Root>
	);
};

// 消息气泡组件
type MessageBubbleProps = {
	children: ReactNode;
	isUser?: boolean;
};

const MessageBubble: FC<MessageBubbleProps> = ({ children, isUser = false }) => {
	const bubbleStyles = isUser
		? "bg-gradient-to-r from-blue-600 to-indigo-600 backdrop-blur-sm border-blue-500/30"
		: "bg-gray-800/80 backdrop-blur-sm border-gray-700";

	const cornerStyles = isUser ? "rounded-tr-none" : "rounded-tl-none";

	return (
		<div className={`px-4 py-3 rounded-2xl ${cornerStyles} border shadow-md ${bubbleStyles}`} style={{ lineHeight: "1.5em" }}>
			{children}
		</div>
	);
};

// 助手头像组件
const AssistantAvatar: FC = () => {
	return (
		<div className="flex h-9 w-9 shrink-0 select-none items-center justify-center rounded-full bg-gradient-to-r from-purple-500 to-blue-600 mr-2">
			<Image
				src="/images/logo.png"
				alt="System Logo"
				width={36}
				height={36}
				className="w-full h-full rounded-full object-cover"
				style={{ transform: 'scale(1.3)' }}
			/>
		</div>
	);
};

// 用户头像组件
const UserAvatar: FC = () => {
	return (
		<div className="flex h-9 w-9 shrink-0 select-none items-center justify-center rounded-full bg-gradient-to-r from-blue-500 to-purple-600 ml-2">
			<svg
				className="w-6 h-6 text-white"
				fill="currentColor"
				viewBox="0 0 24 24"
			>
				<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z" />
			</svg>
		</div>
	);
};

// 用户消息组件
export const UserMessage: FC = () => {
	return (
		<MessageContainer isUser={true}>
			<div className="flex flex-col space-y-2 max-w-[90%] sm:max-w-[80%] md:max-w-[70%]">
				<MessageBubble isUser={true}>
					<MessagePrimitive.Content />
					<UserMessageAttachments />
				</MessageBubble>
			</div>
			<UserAvatar />
		</MessageContainer>
	);
};

// 助手消息组件
export const AssistantMessage: FC = () => {
	const threadRuntime = useThreadRuntime();
	const threadState = threadRuntime.getState();
	const isLast = useMessage((m) => m.isLast);

	const shouldRenderMessageBreak =
		threadState.messages.filter((msg) => msg.role === "user")?.length > 1 && !isLast;

	return (
		<>
			<MessagePrimitive.Root className="flex w-full md:max-w-4xl md:mx-0 mx-auto max-w-[95%] md:py-4 py-6">
				<div className="flex flex-col space-y-2 mb-6">
					<div className="flex items-start">
						<AssistantAvatar />
						<div className="flex flex-col space-y-3 max-w-[90%] sm:max-w-[80%] md:max-w-[70%]">
							<div className="bg-gray-800/80 backdrop-blur-sm px-3 sm:px-5 py-3 sm:py-4 rounded-2xl rounded-tl-none border border-gray-700 shadow-md">
								<MessagePrimitive.Content components={{ Text: MarkdownText }} />
							</div>
						</div>
					</div>
				</div>
			</MessagePrimitive.Root>
			{shouldRenderMessageBreak && (
				<div className="w-full flex justify-center my-4">
					<hr className="w-[90%] max-w-[720px] border-gray-700" />
				</div>
			)}
		</>
	);
};