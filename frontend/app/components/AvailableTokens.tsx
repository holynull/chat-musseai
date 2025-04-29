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

	const [currentPage, setCurrentPage] = useState<number>(1);
	const [itemsPerPage, setItemsPerPage] = useState<number>(5);

	const paginatedTokens = filteredTokens?.slice(
		0,
		currentPage * itemsPerPage
	);

	// 计算是否还有更多记录可以加载
	const hasMoreTokens = filteredTokens?.length > currentPage * itemsPerPage;

	// 添加加载更多的处理函数
	const loadMoreTokens = () => {
		setCurrentPage(prev => prev + 1);
	};

	// 当选择的链变化时重置页码
	useEffect(() => {
		setCurrentPage(1);
	}, [selectedChain]);

	return filteredTokens && filteredTokens.length > 0 && (
		<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-3xl sm:mt-6 md:mt-8 overflow-hidden">
			{/* 标题和链筛选器 */}
			<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
				<h3 className="text-lg sm:text-xl font-semibold mb-2 sm:mb-3">Available Tokens List</h3>
				<div className="flex gap-1.5 sm:gap-2 flex-wrap">
					{chains.map(chain => (
						<button
							key={chain}
							onClick={() => setSelectedChain(chain)}
							className={`px-2 sm:px-4 py-1 sm:py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-all duration-200 ${selectedChain === chain
								? 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-md hover:shadow-lg'
								: 'bg-gray-700 text-gray-300 hover:bg-gray-600'
								}`}
						>
							{chain}
						</button>
					))}
				</div>
			</div>

			{/* 桌面版表格 - 在中等屏幕以上显示 */}
			<div className="hidden md:block bg-gray-900 rounded-lg p-4">
				{/* 表格头部 */}
				<div className="grid grid-cols-5 gap-4 p-3 bg-gray-800 font-medium text-gray-300 rounded-t-lg mb-2">
					<div>Token</div>
					<div>Chain</div>
					<div>Contract Addr</div>
					<div>Decimals</div>
					<div>Cross Chain</div>
				</div>

				{/* 表格内容 */}
				<div className="divide-y divide-gray-700">
					{filteredTokens?.map((token, index) => (
						<div
							key={index}
							className="grid grid-cols-5 gap-4 p-3 hover:bg-gray-700 items-center transition-colors duration-150 rounded"
						>
							<div className="flex items-center gap-3">
								{token.logoURI && (
									<div className="w-8 h-8 rounded-full overflow-hidden bg-gray-700 border border-gray-600 shadow-sm flex-shrink-0">
										<Image
											src={token.logoURI}
											alt={token.symbol}
											width={32}
											height={32}
											className="w-full h-full object-contain"
											onError={(e) => {
												(e.target as HTMLImageElement).src = 'https://placehold.co/28x28?text=' + token.symbol.charAt(0);
											}}
										/>
									</div>
								)}
								<div>
									<div className="font-semibold text-gray-100">{token.symbol}</div>
									<div className="text-xs text-gray-400">{token.name}</div>
								</div>
							</div>
							<div className="text-gray-300">{token.chain}</div>
							<div className="flex items-center">
								<span className="bg-gray-700 rounded-md px-2.5 py-1.5 text-xs font-mono text-gray-300 border border-gray-600" title={token.address}>
									{truncateAddress(token.address)}
								</span>
								<button
									className="ml-2 text-gray-400 hover:text-blue-400 transition-colors"
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
							<div className="text-gray-300">{token.decimals}</div>
							<div>
								<span className={`px-3 py-1.5 rounded-full text-xs font-medium ${token.isCrossEnable
									? 'bg-gradient-to-r from-green-900 to-green-700 text-green-200 border border-green-600'
									: 'bg-gray-700 text-gray-300 border border-gray-600'
									}`}>
									{token.isCrossEnable ? 'Support' : 'Unsupport'}
								</span>
							</div>
						</div>
					))}
				</div>
			</div>

			{/* 移动版卡片列表 - 只在小屏幕显示 */}
			<div className="md:hidden bg-gray-900 rounded-lg p-3">
				<div className="space-y-4">
					{paginatedTokens?.map((token, index) => (
						<div
							key={index}
							className="p-3 bg-gray-800 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors"
						>
							{/* 代币基本信息行 */}
							<div className="flex items-center justify-between mb-3">
								<div className="flex items-center gap-2">
									{token.logoURI && (
										<div className="w-8 h-8 rounded-full overflow-hidden bg-gray-700 border border-gray-600 shadow-sm flex-shrink-0">
											<Image
												src={token.logoURI}
												alt={token.symbol}
												width={32}
												height={32}
												className="w-full h-full object-contain"
												onError={(e) => {
													(e.target as HTMLImageElement).src = 'https://placehold.co/28x28?text=' + token.symbol.charAt(0);
												}}
											/>
										</div>
									)}
									<div>
										<div className="font-semibold text-gray-100">{token.symbol}</div>
										<div className="text-xs text-gray-400">{token.name}</div>
									</div>
								</div>
								<span className={`px-2.5 py-1 rounded-full text-xs font-medium ${token.isCrossEnable
									? 'bg-gradient-to-r from-green-900 to-green-700 text-green-200 border border-green-600'
									: 'bg-gray-700 text-gray-300 border border-gray-600'
									}`}>
									{token.isCrossEnable ? 'Support' : 'Unsupport'}
								</span>
							</div>

							{/* 详细信息列表 */}
							<div className="space-y-2 text-sm">
								<div className="flex justify-between">
									<span className="text-gray-400">Chain:</span>
									<span className="text-gray-200">{token.chain}</span>
								</div>
								<div className="flex justify-between">
									<span className="text-gray-400">Decimals:</span>
									<span className="text-gray-200">{token.decimals}</span>
								</div>
								<div className="flex flex-col">
									<span className="text-gray-400 mb-1">Contract:</span>
									<div className="flex items-center justify-between bg-gray-700 rounded-md px-2.5 py-2 text-xs font-mono text-gray-300 border border-gray-600">
										<span title={token.address} className="truncate">
											{truncateAddress(token.address)}
										</span>
										<button
											className="ml-2 text-gray-400 hover:text-blue-400 transition-colors p-1"
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
								</div>
							</div>
						</div>
					))}

					{filteredTokens?.length === 0 && (
						<div className="p-8 text-center text-gray-400">
							No tokens available for this chain
						</div>
					)}
				</div>
				{hasMoreTokens && (
					<div className="mt-4 text-center">
						<button
							onClick={loadMoreTokens}
							className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors text-sm font-medium"
						>
							Load More
						</button>
					</div>
				)}
			</div>
		</div>
	);
};