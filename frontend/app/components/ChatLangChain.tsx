"use client";

import React, { FC, useCallback, useEffect, useRef, useState } from "react";
import {
	AppendMessage,
	AssistantRuntimeProvider,
	CompositeAttachmentAdapter,
	SimpleImageAttachmentAdapter,
	SimpleTextAttachmentAdapter,
	useExternalStoreRuntime,
} from "@assistant-ui/react";
import { v4 as uuidv4 } from "uuid";
import { useExternalMessageConverter } from "@assistant-ui/react";
import { BaseMessage, HumanMessage } from "@langchain/core/messages";
import { useToast } from "../hooks/use-toast";
import {
	convertToOpenAIFormat,
	convertLangchainMessages,
} from "../utils/convert_messages";
import { ThreadChat } from "./chat-interface";
import { SelectModel } from "./SelectModel";
import { ThreadHistory } from "./thread-history";
import { Toaster } from "./ui/toaster";
import { useGraphContext } from "../contexts/GraphContext";
import { useQueryState } from "nuqs";
import { createClient } from "../contexts/utils";
import { WalletIndicator } from "./WalletIndicator";

function ChatLangChainComponent(): React.ReactElement {
	const { toast } = useToast();
	const { threadsData, userData, graphData } = useGraphContext();
	const { user } = userData;
	const { getUserThreads, createThread, getThreadById } = threadsData;
	const { messages, setMessages, streamMessage, switchSelectedThread, runingId } =
		graphData;
	const [isRunning, setIsRunning] = useState(false);
	const [threadId, setThreadId] = useQueryState("threadId");

	const hasCheckedThreadIdParam = useRef(false);
	useEffect(() => {
		if (typeof window === "undefined" || hasCheckedThreadIdParam.current)
			return;
		if (!threadId) {
			hasCheckedThreadIdParam.current = true;
			return;
		}

		hasCheckedThreadIdParam.current = true;

		try {
			getThreadById(threadId).then((thread) => {
				if (!thread) {
					setThreadId(null);
					return;
				}

				switchSelectedThread(thread);
			});
		} catch (e) {
			console.error("Failed to fetch thread in query param", e);
			setThreadId(null);
		}
	}, [threadId, getThreadById, setThreadId, switchSelectedThread]);

	const isSubmitDisabled = !user?.user_id;

	const onNew = useCallback(async (message: AppendMessage): Promise<void> => {
		if (isSubmitDisabled) {
			toast({
				title: "Failed to send message",
				description: "Unable to find user ID. Please try again later.",
			});
			return;
		}
		// if (message.content[0]?.type !== "text") {
		// 	throw new Error("Only text messages are supported");
		// }

		setIsRunning(true);

		let currentThreadId = threadId;
		if (!currentThreadId) {
			const thread = await createThread(user.user_id);
			if (!thread) {
				toast({
					title: "Error",
					description: "Thread creation failed.",
				});
				return;
			}
			setThreadId(thread.thread_id);
			currentThreadId = thread.thread_id;
		}

		try {
			const humanMessage = new HumanMessage({
				// content: "text" in message.content[0] ? message.content[0].text : "",
				content: "",
				id: uuidv4()
			});
			if (message.attachments && message.attachments.length > 0) {
				let content: any = [];
				if (message.content[0] && "text" in message.content[0]) {
					content.push({ "type": "text", "text": message.content[0].text });
				}
				for (let attachment of message.attachments) {
					let _content: any = attachment.content && attachment.contentType.indexOf("image") === 0 && attachment.content.length > 0 ? attachment.content[0] : undefined;
					if (content) {
						content.push({ "type": "image_url", "image_url": { "url": _content.image } });
					}
				}
				humanMessage.content = content;
			} else {
				humanMessage.content = "text" in message.content[0] ? message.content[0].text : "";
			}

			setMessages((prevMessages) => [...prevMessages, humanMessage]);

			await streamMessage(currentThreadId, {
				messages: [convertToOpenAIFormat(humanMessage)],
			});
		} finally {
			setIsRunning(false);
			// Re-fetch threads so that the current thread's title is updated.
			await getUserThreads(user.user_id);
		}

	}, [isSubmitDisabled, threadId, user, createThread, setThreadId, streamMessage, toast, getUserThreads, setMessages]);

	const threadMessages = useExternalMessageConverter<BaseMessage>({
		callback: convertLangchainMessages,
		messages: messages,
		isRunning,
	});
	const client = createClient();
	const runtime = useExternalStoreRuntime({
		messages: threadMessages,
		isRunning,
		onNew,
		onCancel: async () => {
			console.log("Cancel the Thread.")
			if (threadId && runingId) {
				await client.runs.cancel(threadId, runingId, false)
			} else {
				console.warn("No threadId: " + threadId)
			}
		},
		adapters: {
			attachments: new CompositeAttachmentAdapter([
				new SimpleImageAttachmentAdapter(),
				new SimpleTextAttachmentAdapter(),
			]),
		},
	});


	return (
		<div className="overflow-hidden w-full flex md:flex-row flex-col relative">
			{/* {messages.length > 0 ? (
				<div className="fixed top-2 sm:top-4 right-2 sm:right-4 z-[100] flex flex-row gap-2 items-center">
					<SelectModel />
					<WalletIndicator />
				</div>
			) : null} */}
			<div className="md:sticky md:top-0 md:left-0 md:h-screen shrink-0 z-50">
				<ThreadHistory />
			</div>
			<div className="w-full overflow-hidden">
				<AssistantRuntimeProvider runtime={runtime}>
					<ThreadChat submitDisabled={isSubmitDisabled} messages={messages} currentThreadId={threadId} />
				</AssistantRuntimeProvider>
			</div>
			<Toaster />
		</div>
	);
}

export const ChatLangChain = React.memo(ChatLangChainComponent);
