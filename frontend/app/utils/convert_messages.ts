import {
	useExternalMessageConverter,
	ThreadMessageLike,
	ToolCallContentPart,
	TextContentPart,
	ReasoningContentPart,
	SourceContentPart,
	FileContentPart,
	ImageContentPart,
	Unstable_AudioContentPart,
} from "@assistant-ui/react";
import { AIMessage, BaseMessage, MessageContent, MessageContentComplex, MessageContentImageUrl, ToolMessage } from "@langchain/core/messages";

// Not exposed by `@assistant-ui/react` package, but is
// the required return type for this callback function.
type Message =
	| ThreadMessageLike
	| {
		role: "tool";
		toolCallId: string;
		toolName?: string | undefined;
		result: any;
	};

export const convertLangchainMessages: useExternalMessageConverter.Callback<
	BaseMessage
> = (message): Message | Message[] => {
	// if (!Array.isArray(message.content) && typeof message.content !== "string") {
	// 	throw new Error("Only text and array messages are supported");
	// }
	let str_content = ""
	if (Array.isArray(message.content) && message.content.length > 0) {
		let text_content = message.content[0] as any;
		str_content = text_content['text'] ? text_content['text'] : ""
	} else if (Array.isArray(message.content) && message.content.length === 0) {
		str_content = ""
	} else {
		str_content = message.content as string
	}

	switch (message.getType()) {
		case "system":
			return {
				role: "system",
				id: message.id,
				content: [{ type: "text", text: message.content as string }],
			};
		case "human":
			if (typeof message.content !== 'string') {
				let content = message.content as MessageContentComplex[];
				let _content: (TextContentPart | ReasoningContentPart | SourceContentPart | ImageContentPart | FileContentPart | Unstable_AudioContentPart)[] = [];
				for (let _c of content) {
					switch (_c.type) {
						case "text":
							_content.push({ "type": "text", "text": _c.text })
							break
						case "image_url":
							_c = _c as MessageContentImageUrl;
							_content.push({ "type": "image", "image": _c.image_url.url })
							break
						default:
							throw new Error(`Unsupported content type: ${_c.type}`);
					}
				}
				return {
					role: "user",
					id: message.id,
					content: _content,
				};
			} else {
				return {
					role: "user",
					id: message.id,
					content: message.content as string,
				};
			}

		case "ai":
			const aiMsg = message as AIMessage;
			const toolCallsContent: ToolCallContentPart[] = aiMsg.tool_calls?.length
				? aiMsg.tool_calls.map((tc) => ({
					type: "tool-call" as const,
					toolCallId: tc.id ?? "",
					toolName: tc.name,
					args: tc.args,
					argsText: JSON.stringify(tc.args),
				}))
				: [];
			return {
				role: "assistant",
				id: message.id,
				content: [
					...toolCallsContent,
					{
						type: "text",
						text: str_content,
					},
				],
			};
		case "tool":
			return {
				role: "tool",
				toolName: message.name,
				toolCallId: (message as ToolMessage).tool_call_id,
				result: str_content,
			};
		default:
			throw new Error(`Unsupported message type: ${message.getType()}`);
	}
};

export function convertToOpenAIFormat(message: BaseMessage) {
	// if (typeof message.content !== "string") {
	// 	throw new Error("Only text messages are supported");
	// }
	switch (message.getType()) {
		case "system":
			return {
				role: "system",
				content: message.content,
			};
		case "human":
			return {
				role: "user",
				content: message.content,
			};
		case "ai":
			return {
				role: "assistant",
				content: message.content,
			};
		case "tool":
			return {
				role: "tool",
				toolName: message.name,
				result: message.content,
			};
		default:
			throw new Error(`Unsupported message type: ${message.getType()}`);
	}
}
