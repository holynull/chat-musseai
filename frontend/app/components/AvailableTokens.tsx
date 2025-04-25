"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import Image from "next/image";
import { useState, useEffect } from "react";

export type AvailableToken = {
	chain: string;
	symbol: string;
	name: string;
	address: string;
	decimals: number;
	logoURI: string;
	isCrossEnable: boolean;
	withdrawGas: string;
};

export const useAvailableTokens = () => useAssistantToolUI({
	toolName: "get_available_tokens",
	render: (input) => {
		// 将原来的render逻辑封装为独立组件
		return <AvailableTokensDisplay input={input} />;
	},
});
const AvailableTokensDisplay = ({ input }: { input: any }) => {
	const data: AvailableToken[] = input.args.data;

	// 获取所有唯一的链
	const chains = Array.from(new Set(data?.map(token => token.chain)));

	// 初始化状态，默认选择第一个链
	const [selectedChain, setSelectedChain] = useState<string>(chains[0] || "");

	// 确保始终有一个选定的链
	useEffect(() => {
		if (chains.length > 0 && !selectedChain) {
			setSelectedChain(chains[0]);
		}
	}, [chains, selectedChain]);

	// 根据选择的链过滤代币
	const filteredTokens = data?.filter(token => token.chain === selectedChain);

	// 截断地址显示
	const truncateAddress = (address: string) => {
		if (!address) return "";
		return `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
	};

	return filteredTokens && filteredTokens.length > 0 && (
		<div className="rounded-lg border border-gray-200 overflow-hidden bg-white shadow-sm sm:mt-6 md:mt-8">
			{/* 链筛选器 */}
			<div className="p-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
				<h3 className="text-lg font-medium text-gray-800 mb-3">Available Tokens List</h3>
				<div className="flex gap-2 flex-wrap">
					{chains.map(chain => (
						<button
							key={chain}
							onClick={() => setSelectedChain(chain)}
							className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 ${selectedChain === chain
								? 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-md hover:shadow-lg'
								: 'bg-gray-200 text-gray-700 hover:bg-gray-300'
								}`}
						>
							{chain}
						</button>
					))}
				</div>
			</div>

			{/* 表格头部 */}
			<div className="grid grid-cols-5 gap-4 p-4 bg-gradient-to-r from-gray-100 to-gray-50 font-medium text-gray-700 border-b border-gray-200">
				<div>Token</div>
				<div>Chain</div>
				<div>Contract Addr</div>
				<div>Decimals</div>
				<div>Cross Chain</div>
			</div>

			{/* 表格内容 */}
			<div className="divide-y divide-gray-100">
				{filteredTokens?.map((token, index) => (
					<div
						key={index}
						className="grid grid-cols-5 gap-4 p-4 hover:bg-blue-50 items-center transition-colors duration-150"
					>
						<div className="flex items-center gap-3">
							{token.logoURI && (
								<div className="w-8 h-8 rounded-full overflow-hidden bg-white border border-gray-200 shadow-sm flex-shrink-0">
									<Image
										src={token.logoURI}
										alt={token.symbol}
										width={32}
										height={32}
										className="w-full h-full object-contain"
										onError={(e) => {
											// Next.js Image组件不支持直接修改src，需要另外处理
											// 可以考虑使用默认图片或条件渲染
											(e.target as HTMLImageElement).src = 'https://placehold.co/28x28?text=' + token.symbol.charAt(0);
										}}
									/>
								</div>
							)}
							<div>
								<div className="font-semibold text-gray-800">{token.symbol}</div>
								<div className="text-xs text-gray-500">{token.name}</div>
							</div>
						</div>
						<div className="text-gray-700">{token.chain}</div>
						<div className="flex items-center">
							<span className="bg-gray-100 rounded-md px-2.5 py-1.5 text-xs font-mono text-gray-700 border border-gray-200" title={token.address}>
								{truncateAddress(token.address)}
							</span>
							<button
								className="ml-2 text-gray-400 hover:text-blue-600 transition-colors"
								title="Copy address"
								onClick={() => {
									navigator.clipboard.writeText(token.address);
								}}
							>
								<svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
								</svg>
							</button>
						</div>
						<div className="text-gray-700">{token.decimals}</div>
						<div>
							<span className={`px-3 py-1.5 rounded-full text-xs font-medium ${token.isCrossEnable
								? 'bg-gradient-to-r from-green-100 to-green-200 text-green-800 border border-green-300'
								: 'bg-gray-100 text-gray-600 border border-gray-200'
								}`}>
								{token.isCrossEnable ? 'Support' : 'Unsupport'}
							</span>
						</div>
					</div>
				))}

				{filteredTokens?.length === 0 && (
					<div className="p-12 text-center text-gray-500">
						No tokens available for this chain
					</div>
				)}
			</div>
		</div>
	);
};