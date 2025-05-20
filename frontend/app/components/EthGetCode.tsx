"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useCallback } from "react";

export type EthGetCodeData = {
	result: string;
	method: string;
	network: string;
	network_type: string;
	address?: string;
	block_parameter?: string;
};

// 格式化代码，添加语法高亮
const formatCode = (code: string): string => {
	// 移除0x前缀用于显示
	if (code && code.startsWith("0x")) {
		code = code.substring(2);
	}
	return code;
};

// 截取长字符串
const truncateString = (str: string, maxLength: number = 20): string => {
	if (!str || str.length <= maxLength) return str;
	return `${str.substring(0, maxLength / 2)}...${str.substring(str.length - maxLength / 2)}`;
};

// 创建一个独立的展示组件来正确使用Hooks
const ContractCodeDisplay = ({ data }: { data: EthGetCodeData }) => {
	// 将Hooks移到组件顶部
	const [showFullCode, setShowFullCode] = useState(false);
	const toggleCodeDisplay = useCallback(() => {
		setShowFullCode(prev => !prev);
	}, []);

	// 如果没有数据或者发生错误，显示错误信息
	if (!data || typeof data === 'string') {
		return (
			<div className="p-4 rounded-lg border border-red-300 bg-red-50 text-red-800 dark:bg-red-900/50 dark:border-red-800 dark:text-red-300">
				<h3 className="text-lg font-medium">Error Retrieving Contract Code</h3>
				<p>{typeof data === 'string' ? data : "Invalid response from API"}</p>
			</div>
		);
	}

	// 处理代码，移除0x前缀
	const bytecode = data.result ? formatCode(data.result) : "";

	// 计算代码长度（以字节为单位）
	const byteLength = bytecode ? bytecode.length / 2 : 0;

	// 根据合约大小确定显示策略
	const displayedCode = showFullCode ? bytecode :
		bytecode.length > 1000 ? bytecode.substring(0, 500) + "..." : bytecode;

	// 确定合约是否为空（没有代码意味着这可能不是合约地址）
	const isEmptyContract = !bytecode || bytecode === "0x" || bytecode === "";

	return (
		<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full overflow-hidden">
			<h2 className="text-xl sm:text-2xl font-bold text-center">Contract Code</h2>

			{/* 合约信息 */}
			<div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
				<div className="flex justify-between p-2 border-b border-gray-700">
					<span className="text-gray-400">Network</span>
					<span className="font-medium text-white capitalize">{data.network} ({data.network_type})</span>
				</div>

				{data.address && (
					<div className="flex justify-between p-2 border-b border-gray-700">
						<span className="text-gray-400">Address</span>
						<span className="font-medium text-white">
							<span className="hidden md:inline">{data.address}</span>
							<span className="inline md:hidden">{truncateString(data.address)}</span>
						</span>
					</div>
				)}

				<div className="flex justify-between p-2 border-b border-gray-700">
					<span className="text-gray-400">Block</span>
					<span className="font-medium text-white">{data.block_parameter || "latest"}</span>
				</div>

				<div className="flex justify-between p-2 border-b border-gray-700">
					<span className="text-gray-400">Bytecode Size</span>
					<span className="font-medium text-white">{byteLength.toLocaleString()} bytes</span>
				</div>
			</div>

			{/* 合约代码 */}
			{isEmptyContract ? (
				<div className="p-3 bg-amber-800/30 rounded-md border border-amber-700/50 text-amber-200">
					<p className="text-center font-medium">No contract code found at this address.</p>
					<p className="text-center text-sm mt-1">This might be a regular wallet address or the contract does not exist.</p>
				</div>
			) : (
				<div className="mt-2">
					<div className="flex justify-between items-center mb-2">
						<h3 className="text-sm font-medium">Contract Bytecode</h3>
						<button
							onClick={toggleCodeDisplay}
							className="text-xs px-2 py-1 bg-blue-600 hover:bg-blue-700 rounded transition-colors duration-150"
						>
							{showFullCode ? "Show Less" : "Show Full Code"}
						</button>
					</div>
					<div className="relative">
						<pre className="p-3 bg-gray-900 rounded-md text-xs overflow-x-auto max-h-60 scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-gray-900">
							<code className="break-all whitespace-pre-wrap text-green-400">
								{displayedCode.length > 0 ? `0x${displayedCode}` : "No bytecode"}
							</code>
						</pre>
						{!showFullCode && bytecode.length > 1000 && (
							<div className="absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-gray-900 to-transparent pointer-events-none" />
						)}
					</div>
				</div>
			)}

			{/* 可复制按钮 */}
			{bytecode && (
				<button
					onClick={() => {
						navigator.clipboard.writeText(`0x${bytecode}`);
						// 可以添加一个复制成功的提示
					}}
					className="self-center mt-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-md text-sm transition-colors duration-150"
				>
					Copy Full Bytecode
				</button>
			)}
		</div>
	);
};

// 主要的hook函数
export const useEthGetCode = () => useAssistantToolUI({
	toolName: "eth_getCode",
	render: (input) => {
		const data: EthGetCodeData = input.args.data;
		return <ContractCodeDisplay data={data} />;
	},
});
