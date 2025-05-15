"use client";

import { parsePartialJson } from "@langchain/core/output_parsers";
import {
	createContext,
	Dispatch,
	ReactNode,
	SetStateAction,
	useContext,
	useEffect,
	useState,
} from "react";
import { AIMessage, BaseMessage, HumanMessage } from "@langchain/core/messages";
import { useToast } from "../hooks/use-toast";
import { v4 as uuidv4 } from "uuid";

import { useThreads } from "../hooks/useThreads";
import { ModelOptions } from "../types";
import { useRuns } from "../hooks/useRuns";
// import { useUser } from "../hooks/useUser";
import { useUser } from "./UserContext"
import { addDocumentLinks, createClient, nodeToStep } from "./utils";
import { Thread } from "@langchain/langgraph-sdk";
import { useQueryState } from "nuqs";

import { mainnet, bsc, tron, optimism, arbitrum, sepolia, polygon, solana } from '@reown/appkit/networks'
import { useAppKit, useAppKitProvider, useAppKitAccount, useAppKitNetwork, useAppKitState, useAppKitEvents, useWalletInfo } from "@reown/appkit/react"
import { useAppKitConnection } from '@reown/appkit-adapter-solana/react'
import { json } from "stream/consumers";
import { wcModal } from "../contexts/appkit"

interface GraphData {
	messages: BaseMessage[];
	selectedModel: ModelOptions;
	setSelectedModel: Dispatch<SetStateAction<ModelOptions>>;
	setMessages: Dispatch<SetStateAction<BaseMessage[]>>;
	streamMessage: (currentThreadId: string, params: GraphInput) => Promise<void>;
	switchSelectedThread: (thread: Thread) => void;
	runingId: string | undefined
}

type UserDataContextType = ReturnType<typeof useUser>;

type ThreadsDataContextType = ReturnType<typeof useThreads>;

type GraphContentType = {
	graphData: GraphData;
	userData: UserDataContextType;
	threadsData: ThreadsDataContextType;
};

const GraphContext = createContext<GraphContentType | undefined>(undefined);

export interface GraphInput {
	messages?: Record<string, any>[];
}

export function GraphProvider({ children }: { children: ReactNode }) {
	const { user } = useUser();
	const {
		isUserThreadsLoading,
		userThreads,
		getThreadById,
		setUserThreads,
		getUserThreads,
		createThread,
		deleteThread,
	} = useThreads(user?.user_id);
	const { toast } = useToast();
	const { shareRun } = useRuns();
	const [messages, setMessages] = useState<BaseMessage[]>([]);
	const [curThreadId, setCurThreadId] = useState<string>();
	const [selectedModel, setSelectedModel] = useState<ModelOptions>(
		"anthropic_claude_3_7_sonnet",
	);
	const [_threadId, setThreadId] = useQueryState("threadId");
	const [runingId, setRuningId] = useState<string>();

	const [abortController, setAbortController] = useState<AbortController | null>(null);
	useEffect(() => {
		const controller = new AbortController();
		setAbortController(controller);

		// 清理函数，组件卸载时取消控制器
		return () => controller.abort();
	}, []);


	const { open, close } = useAppKit();
	const { address, isConnected, caipAddress, status, embeddedWalletInfo } = useAppKitAccount()
	const { caipNetwork, caipNetworkId, chainId, switchNetwork } = useAppKitNetwork()
	// const { open, selectedNetworkId } = useAppKitState()
	const events = useAppKitEvents()
	// const { walletProvider_solana } = useAppKitProvider<Provider>('solana') as any
	// const { solanaProvider } = useAppKitProvider('solana')
	const { walletInfo } = useWalletInfo()
	const { connection } = useAppKitConnection()
	const [txDataEvm, setTxDataEvm] = useState<any>(null)
	const [txDataSol, setTxDataSol] = useState<any>(null)
	const [txDataSolTW, setTxDataSolTW] = useState<any>(null)
	const [isShowSendEvmTx, setShowSendEvmTx] = useState<boolean>(false)
	const [isShowSendSolTx, setShowSendSolTx] = useState<boolean>(false)
	const [isShowSendSolTxTW, setShowSendSolTxTW] = useState<boolean>(false)
	const [walletStatus, setWalletStatus] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>(
		isConnected ? 'connected' : 'disconnected'
	);
	// 更新连接钱包函数
	const connectWallet = async () => {
		try {
			setWalletStatus('connecting');
			await open({ view: "Connect" });
			// AppKit会自动更新isConnected状态
		} catch (error) {
			setWalletStatus('error');
			// 添加错误处理
			console.error("Failed to connect wallet:", error);
		}
	}

	// 在useEffect中监听连接状态变化
	useEffect(() => {
		setWalletStatus(isConnected ? 'connected' : 'disconnected');
	}, [isConnected]);

	const CHAIN_CONFIG = {
		"ethereum": {
			"network": mainnet,
		},
		"bsc": {
			"network": bsc
		},
		"polygon": {
			"network": polygon,
		},
		"arbitrum": {
			"network": arbitrum,
		},
		"optimism": {
			"network": optimism,
		},
		"solana": {
			"network": solana,
		},
		"tron": {
			"network": tron
		}
	}

	const _change_network_to = async (chainId: string) => {
		const chainData = CHAIN_CONFIG[chainId as keyof typeof CHAIN_CONFIG] as any;
		// wcModal.switchNetwork(chainData.network)
		switchNetwork(chainData.network)
	}
	const change_network_to = async (network_data: any) => {
		if (Array.isArray(network_data) && network_data.length >= 2) {
			const chainId = network_data[1].network_name;
			await _change_network_to(chainId)
		}
	}

	const streamMessage = async (
		currentThreadId: string,
		params: GraphInput,
	): Promise<void> => {
		if (!user?.user_id) {
			toast({
				title: "Error",
				description: "User ID not found",
			});
			return;
		}
		const client = createClient();

		const input = {
			messages: params.messages?.filter((msg) => {
				if (msg.role !== "assistant") {
					return true;
				}
				const aiMsg = msg as AIMessage;
				// Filter our artifact ui tool calls from going to the server.
				if (
					aiMsg.tool_calls &&
					aiMsg.tool_calls.some((tc) => tc.name === "artifact_ui")
				) {
					return false;
				}
				return true;
			}),
			wallet_address: address ? address : "",
			chain_id: chainId ? chainId.toString() : "-1",
			wallet_is_connected: isConnected,
			time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone,
			llm: selectedModel,
			// chat_history: chatHistory,
			chat_history: [],
			// image_urls: currentImages,
			// pdf_files: currentPDFs,
		};

		const stream = client.runs.stream(currentThreadId, "musseai", {
			input,
			streamMode: "events",
			config: {
				configurable: {
					model_name: selectedModel,
				},
			},
		});

		let read_link_start_counter = 0;
		let extract_content_start_counter = 0;
		let read_link_end_counter = 0;
		let extract_content_end_counter = 0;
		let first_read_content_run_id = "";
		let first_extract_content_run_id = "";
		let runing_id = ""

		for await (const chunk of stream) {
			console.log(chunk.data)
			if (!runingId && chunk.data?.metadata?.run_id) {
				setRuningId(chunk.data.metadata.run_id)
			}
			if (chunk.data.event === "on_chain_start") {
				const node = chunk?.data?.name;//metadata?.langgraph_node;
				if (
					"node_read_content" === node
				) {
					read_link_start_counter++;
					if (!first_read_content_run_id && chunk.data?.run_id) {
						first_read_content_run_id = chunk.data?.run_id;
						setMessages((prevMessages) => {
							const newMessage = new AIMessage({
								id: first_read_content_run_id,
								content: "",
								tool_calls: [
									{
										name: "progress",
										args: {
											step: { text: "Reading Links", progress: 0 },
										},
									},
								],
							});
							return [...prevMessages, newMessage];;
						});
					}
				}
				if (
					"node_extranct_relevant_content" === node
				) {
					extract_content_start_counter++;
					if (!first_extract_content_run_id && chunk.data?.run_id) {
						first_extract_content_run_id = chunk.data?.run_id;
						console.log("first_extract_content_run_id", first_extract_content_run_id);
						setMessages((prevMessages) => {
							const newMessage = new AIMessage({
								id: first_extract_content_run_id,
								content: "",
								tool_calls: [
									{
										name: "progress",
										args: {
											step: { text: "Extract Content", progress: 0 },
										},
									},
								],
							});
							return [...prevMessages, newMessage];;
						});
					}
				}
			}

			if (chunk.data.event === "on_chat_model_stream") {

				if (chunk.data.metadata.langgraph_node === "respond" ||
					["node_llm_musseai", "node_llm_image", "node_llm_quote", "node_llm_search", "node_llm_swap", "node_llm_wallet", "node_llm_infura"]
						.includes(chunk.data.metadata.langgraph_node)) {
					const message = chunk.data.data.chunk;
					if (message.content && Array.isArray(message.content) && message.content.length > 0) {
						let content = message.content[0] as any;
						message.content = content['text'] ? content['text'] : ''
					} else if (Array.isArray(message.content) && message.content.length === 0) {
						message.content = ''
					}
					if (message.content != '') {
						setMessages((prevMessages) => {
							if (!runing_id) {
								runing_id = chunk.data.metadata.run_id;
								// const answerHeaderToolMsg = new AIMessage({
								// 	content: "",
								// 	tool_calls: [
								// 		{
								// 			name: "answer_header",
								// 			args: { node_name: chunk.data.metadata.langgraph_node },
								// 		},
								// 	],
								// });
								// prevMessages = [...prevMessages, answerHeaderToolMsg];
							}
							const existingMessageIndex = prevMessages.findIndex(
								(msg) => msg.id === message.id,
							);
							if (existingMessageIndex !== -1) {
								// Create a new array with the updated message
								return [
									...prevMessages.slice(0, existingMessageIndex),
									new AIMessage({
										...prevMessages[existingMessageIndex],
										content:
											prevMessages[existingMessageIndex].content +
											message.content,
									}),
									...prevMessages.slice(existingMessageIndex + 1),
								];
							} else {
								const newMessage = new AIMessage({
									...message,
								});
								return [...prevMessages, newMessage];
							}
						});
					}
				}
			}
			if (chunk.data.event === "on_tool_end") {
				// 辅助函数定义
				const handleSearchResult = (chunk: any) => {
					const output = chunk.data.data.output.content;
					let sources: any[] = [];
					if (output) {
						try {
							const result = JSON.parse(output);
							if ("search_result" in result) {
								sources = result["search_result"];
							} else {
								console.error("search_result not found in result");
							}
						} catch (error) {
							console.error("Error parsing JSON:", error);
						}
					}
					setMessages((prevMessages) => [
						...prevMessages,
						new AIMessage({
							content: "",
							tool_calls: [{
								name: "source_list",
								args: { sources: sources },
							}],
						})
					]);
				};

				const handleNetworkChange = (chunk: any) => {
					let content = chunk.data.data.output.content;
					const result = JSON.parse(content);
					change_network_to(result);
				};

				const handleApproveERC20 = (chunk: any) => {
					let content = chunk.data.data.output.content;
					try {
						const result = JSON.parse(content);
						let chainType: string | undefined, txData: any, txName: string = '';

						if (Array.isArray(result) && result.length >= 2) {
							txData = result[1];
							if (txData["chain_id"] != chainId && txData['chain_id'] !== 'tron') {
								_change_network_to(txData["chain_id"]);
							}

							chainType = 'evm';
							txName = txData['name'];

							setMessages((prevMessages) => [
								...prevMessages,
								new AIMessage({
									content: "",
									tool_calls: [{
										name: "generate_approve_erc20",
										args: {
											txData: txData,
											name: txName,
											orderInfo: undefined,
											tx_detail: result[1]?.tx_detail
										},
									}],
								})
							]);
						}
					} catch (e) {
						console.error(e);
					}
				};

				const handleSwapTx = (chunk: { data: { data: { output: { content: string } } } }) => {
					let content = chunk.data.data.output.content;
					try {
						let result = JSON.parse(content);
						let orderInfo: any = null;
						let chainType = "";
						let txName = '';

						if (Array.isArray(result) && result.length >= 2) {
							result = result[1];
							if (result["success"]) {
								orderInfo = result.order_info;
								const swap_data = result["swap_data"];
								txName = swap_data.name;

								if (!swap_data.chain_type) {
									throw new Error("Missing chain_type in swap data");
								}

								if (swap_data.chain_type === "evm") {
									chainType = 'evm';
									setMessages((prevMessages) => [
										...prevMessages,
										new AIMessage({
											content: "",
											tool_calls: [{
												name: "send_evm_transaction",
												args: {
													txData: swap_data.txData,
													name: txName,
													orderInfo: orderInfo,
													tx_detail: result?.tx_detail
												},
											}],
										})
									]);
								} else if (swap_data.chain_type === "solana") {
									if (!connection) {
										wcModal.switchNetwork(solana);
									}
									chainType = 'sol';
									setMessages((prevMessages) => [
										...prevMessages,
										new AIMessage({
											content: "",
											tool_calls: [{
												name: "send_solana_transaction",
												args: {
													txData: swap_data.txData,
													name: txName,
													orderInfo: orderInfo,
													tx_detail: result?.tx_detail
												},
											}],
										})
									]);
								} else {
									throw new Error(`Unsupported chain type: ${swap_data.chain_type}`);
								}
							}
						}
					} catch (e) {
						console.error(e);
					}
				};

				const handleRegularTool = (toolName: string, chunk: any) => {
					let content = chunk.data.data.output.content;
					try {
						let result = JSON.parse(content);
						setMessages((prevMessages) => [
							...prevMessages,
							new AIMessage({
								content: "",
								tool_calls: [{
									name: toolName,
									args: { data: toolName === "get_transaction_records" ? result.list : result },
								}],
							})
						]);
					} catch (e) {
						console.error(e);
					}
				};
				// 定义特殊处理的工具
				const specialTools = {
					"search_news": handleSearchResult,
					"search_webpage": handleSearchResult,
					"access_links_content": handleSearchResult,
					"connect_to_wallet": () => connectWallet(),
					"change_network_to": handleNetworkChange,
					"generate_approve_erc20": handleApproveERC20,
					"generate_swap_tx_data": handleSwapTx,
				};

				// 定义常规工具处理函数
				const regularTools = [
					"get_available_tokens", "swap_quote", "get_transaction_records",
					"get_transaction_details", "get_balance_of_address", "get_erc20_decimals",
					"allowance_erc20", "get_sol_balance", "get_spl_token_balance", "getLatestQuote",
					"buy_sell_signal", "getTokenMetadata", "getLatestContent",
					"getCommunityTrendingToken", "gen_images", "get_supported_networks", "get_eth_block_number", "get_eth_balance"
				];

				const toolName = chunk?.data?.name;

				// 处理特殊工具
				if (specialTools[toolName as keyof typeof specialTools]) {
					specialTools[toolName as keyof typeof specialTools](chunk);
				}
				// 处理常规工具
				else if (regularTools.includes(toolName)) {
					handleRegularTool(toolName, chunk);
				}
			}
			if (chunk.data.event === "on_chain_end") {
				let node = chunk?.data?.name;//metadata?.langgraph_node;
				if (
					"node_extranct_relevant_content" === node
				) {
					extract_content_end_counter++;
					setMessages((prevMessages) => {
						const existingMessageIndex = prevMessages.findIndex(
							(msg) => msg.id === first_extract_content_run_id,
						);

						if (existingMessageIndex !== -1) {
							return [
								...prevMessages.slice(0, existingMessageIndex),
								new AIMessage({
									id: first_extract_content_run_id,
									content: "",
									tool_calls: [
										{
											name: "progress",
											args: {
												step: { text: "Extract Content", progress: extract_content_end_counter / extract_content_start_counter * 100 },
											},
										},
									],
								}),
								...prevMessages.slice(existingMessageIndex + 1),
							];
						} else {
							console.warn(
								"Extract content from links: Progress message ID is defined but not found in messages",
							);
							return [...prevMessages];;
						}
					});
				}

				if (
					"node_read_content" === node
				) {
					read_link_end_counter++;
					setMessages((prevMessages) => {
						const existingMessageIndex = prevMessages.findIndex(
							(msg) => msg.id === first_read_content_run_id,
						);
						if (existingMessageIndex !== -1) {
							return [
								...prevMessages.slice(0, existingMessageIndex),
								new AIMessage({
									id: first_read_content_run_id,
									content: "",
									tool_calls: [
										{
											name: "progress",
											args: {
												step: { text: "Reading Links", progress: read_link_end_counter / read_link_start_counter * 100 },
											},
										},
									],
								}),
								...prevMessages.slice(existingMessageIndex + 1),
							];
						} else {
							console.warn(
								"Read links: Progress message ID is defined but not found in messages",
							);
							return [...prevMessages];;
						}
					});
				}

				if (node === 'node_read_content_reduce') {
					first_read_content_run_id = "";
					read_link_end_counter = 0;
					read_link_start_counter = 0;

				}
				if (node === 'node_relevant_reduce') {
					first_extract_content_run_id = ""
					extract_content_end_counter = 0;
					extract_content_start_counter = 0;
				}
			}
		}

		if (runing_id) {
			// Chain `.then` to not block the stream
			shareRun(runing_id).then((sharedRunURL) => {
				if (sharedRunURL) {
					setMessages((prevMessages) => {
						const langSmithToolCallMessage = new AIMessage({
							content: "",
							id: uuidv4(),
							tool_calls: [
								{
									name: "langsmith_tool_ui",
									args: { sharedRunURL },
									id: sharedRunURL
										?.split("https://smith.langchain.com/public/")[1]
										.split("/")[0],
								},
							],
						});
						return [...prevMessages, langSmithToolCallMessage];
					});
				}
			});
			runing_id = ""
			setRuningId("")
		}
	};

	const switchSelectedThread = (thread: Thread) => {
		setThreadId(thread.thread_id);

		// 早期返回优化
		if (!thread.values) {
			setMessages([]);
			return;
		}

		const threadValues = thread.values as Record<string, any>;
		const messageArray = threadValues.messages as Record<string, any>[] || [];

		// 提取消息处理函数
		const processMessages = () => {
			return messageArray.flatMap((msg, index, array) => {
				// 处理Human消息
				if (msg.type === "human") {
					return [
						new HumanMessage({
							...msg,
							content: msg.content,
						}),
					];
				}

				// 处理AI消息
				if (msg.type === "ai") {
					const processedContent = processAIContent(msg.content);
					return [
						new AIMessage({
							...msg,
							content: processedContent,
						})
					];
				}

				// 处理Tool消息
				if (msg.type === "tool") {
					return handleToolMessage(msg);
				}

				return []; // 未知消息类型
			});
		};

		// 处理AI内容的辅助函数
		const processAIContent = (content: any): string => {
			if (!content) return '';

			if (Array.isArray(content)) {
				if (content.length === 0) return '';

				const firstContent = content[0];
				if (typeof firstContent === 'object') {
					return 'text' in firstContent ? firstContent.text : '';
				} else if (typeof firstContent === 'string') {
					return firstContent;
				}
			}

			return String(content);
		};

		// 处理工具消息的辅助函数
		const handleToolMessage = (msg: Record<string, any>): AIMessage[] => {
			const { name, content } = msg;

			// 搜索相关工具特殊处理
			if (["search_webpage", "search_news", "access_links_content"].includes(name)) {
				return handleSearchToolMessage(msg, content);
			}

			// 交易相关工具特殊处理
			if (name === "generate_approve_erc20") {
				return handleApproveERC20Message(msg, content);
			}

			if (name === "generate_swap_tx_data") {
				return handleSwapTxMessage(msg, content);
			}

			// 通用工具消息处理
			const regularTools = [
				"get_available_tokens", "swap_quote", "get_transaction_records",
				"get_transaction_details", "get_balance_of_address", "get_erc20_decimals",
				"allowance_erc20", "get_sol_balance", "get_spl_token_balance", "getLatestQuote",
				"buy_sell_signal", "getTokenMetadata", "getLatestContent",
				"getCommunityTrendingToken", "gen_images", "get_supported_networks", "get_eth_block_number", "get_eth_balance"
			];

			if (regularTools.includes(name) && content) {
				try {
					const result = JSON.parse(content);
					return [
						new AIMessage({
							...msg,
							content: "",
							tool_calls: [{
								name,
								args: { data: name === "get_transaction_records" ? result.list : result },
							}],
						})
					];
				} catch (e) {
					console.error(`Error parsing ${name} result:`, e);
					return [];
				}
			}

			return []; // 默认返回空数组
		};

		// 处理搜索工具消息
		const handleSearchToolMessage = (msg: Record<string, any>, content: string): AIMessage[] => {
			let sources = [];
			if (content) {
				try {
					const result = JSON.parse(content);
					if ("search_result" in result) {
						sources = result["search_result"];
					}
				} catch (error) {
					console.error("Error parsing search result JSON:", error);
				}
			}

			// 返回三个消息：源列表和两个进度条（已完成）
			return [
				new AIMessage({
					...msg,
					content: "",
					tool_calls: [{
						name: "source_list",
						args: { sources },
					}],
				}),
				new AIMessage({
					...msg,
					content: "",
					tool_calls: [{
						name: "progress",
						args: { step: { text: "Reading Links", progress: 100 } },
					}],
				}),
				new AIMessage({
					...msg,
					content: "",
					tool_calls: [{
						name: "progress",
						args: { step: { text: "Extract Content", progress: 100 } },
					}],
				}),
			];
		};

		// 处理ERC20授权消息
		const handleApproveERC20Message = (msg: Record<string, any>, content: string): AIMessage[] => {
			if (!content) return [];

			try {
				const result = JSON.parse(content);
				if (Array.isArray(result) && result.length >= 2) {
					const txData = result[1];
					const txName = txData['name'];

					return [
						new AIMessage({
							...msg,
							content: "",
							tool_calls: [{
								name: "generate_approve_erc20",
								args: {
									txData,
									name: txName,
									orderInfo: undefined,
									tx_detail: result[1]?.tx_detail
								},
							}],
						})
					];
				}
			} catch (e) {
				console.error("Error parsing approve ERC20 JSON:", e);
			}

			return [];
		};

		// 处理Swap交易消息
		const handleSwapTxMessage = (msg: Record<string, any>, content: string): AIMessage[] => {
			if (!content) return [];

			try {
				let result = JSON.parse(content);
				if (!Array.isArray(result) || result.length < 2) return [];

				result = result[1];
				if (!result["success"]) return [];

				const orderInfo = result.order_info;
				const swap_data = result["swap_data"];
				const txName = swap_data.name;

				if (!swap_data.chain_type) {
					throw new Error("Missing chain_type in swap data");
				}

				if (swap_data.chain_type === "evm") {
					return [
						new AIMessage({
							...msg,
							content: "",
							tool_calls: [{
								name: "send_evm_transaction",
								args: {
									txData: swap_data.txData,
									name: txName,
									orderInfo,
									tx_detail: result?.tx_detail
								},
							}],
						})
					];
				}
				else if (swap_data.chain_type === "solana") {
					return [
						new AIMessage({
							...msg,
							content: "",
							tool_calls: [{
								name: "send_solana_transaction",
								args: {
									txData: swap_data.txData,
									name: txName,
									orderInfo,
									tx_detail: result?.tx_detail
								},
							}],
						})
					];
				}
			} catch (e) {
				console.error("Error parsing swap tx data:", e);
			}

			return [];
		};

		// 处理并设置消息
		const actualMessages = processMessages();
		setMessages(actualMessages);
	};

	const contextValue: GraphContentType = {
		userData: {
			...useUser()
		},
		threadsData: {
			isUserThreadsLoading,
			userThreads,
			getThreadById,
			setUserThreads,
			getUserThreads,
			createThread,
			deleteThread,
		},
		graphData: {
			messages,
			selectedModel,
			setSelectedModel,
			setMessages,
			streamMessage,
			switchSelectedThread,
			runingId,
		},
	};

	return (
		<GraphContext.Provider value={contextValue}>
			{children}
		</GraphContext.Provider>
	);
}

export function useGraphContext() {
	const context = useContext(GraphContext);
	if (context === undefined) {
		throw new Error("useGraphContext must be used within a GraphProvider");
	}
	return context;
}