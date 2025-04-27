"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import Image from "next/image";
import { useState, useEffect } from "react";

export type Balance = {
	success: boolean,
	balance: string,
	wallet_address: string,
	token_address: string,
	symbol: string,
	decimals: number,
	chainId: number,
};

// Format number function
const formatNumber = (value: string, decimals: number = 6): string => {
	const num = parseFloat(value);
	if (isNaN(num)) return value;

	const maxDecimals = Math.min(decimals, 8);

	return num.toLocaleString('en-US', {
		minimumFractionDigits: 2,
		maximumFractionDigits: maxDecimals
	});
};

// Format wallet address to show only first and last characters
const formatAddress = (address: string, chars: number = 6): string => {
	if (!address || address.length <= chars * 2) return address;
	return `${address.substring(0, chars)}...${address.substring(address.length - chars)}`;
};

// Get chain name based on chainId
const getChainName = (chainId: number): string => {
	const chains: Record<number, string> = {
		1: "Ethereum",
		56: "BSC",
		137: "Polygon",
		250: "Fantom",
		43114: "Avalanche",
		42161: "Arbitrum",
		10: "Optimism",
		// Add more chains
	};

	return chains[chainId] || `Chain ID: ${chainId}`;
};

export const useGetBalanceOfAddress = () => useAssistantToolUI({
	toolName: "get_balance_of_address",
	render: (input) => {
		const data: Balance = input.args.data;

		if (!data || !data.success) {
			// return (
			// 	<div className="rounded-lg border border-red-500 bg-red-900 p-4 text-red-200">
			// 		<p className="font-medium">Balance Query Failed</p>
			// 		<p className="text-sm">Unable to retrieve balance information for this address</p>
			// 	</div>
			// );
			return <></>
		}

		// Calculate formatted balance
		const formattedBalance = formatNumber(
			(parseFloat(data.balance) / Math.pow(10, data.decimals)).toString(),
			data.decimals
		);

		const chainName = getChainName(data.chainId);

		return (
			<div className="flex flex-col space-y-6 p-4 rounded-lg border border-gray-700 bg-gray-800 text-white max-w-3xl sm:mt-6 md:mt-8">
				<h2 className="text-2xl font-bold text-center">Wallet Balance Query</h2>

				{/* Main balance information */}
				<div className="bg-gray-900 rounded-lg p-4">
					<h3 className="text-xl font-semibold mb-3">Balance Information</h3>
					<div className="flex items-center justify-between mb-4">
						<div>
							<p className="text-sm text-gray-400">Token Balance</p>
							<p className="text-3xl font-bold text-white">
								{formattedBalance}
								<span className="text-gray-400 text-base ml-1">{data.symbol}</span>
							</p>
						</div>
						<div className="flex items-center">
							<span className="text-sm font-medium text-gray-400 mr-2">{chainName}</span>
							<div className="w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center text-white text-xs font-bold">
								{data.chainId}
							</div>
						</div>
					</div>
				</div>

				{/* Address Information */}
				<div className="bg-gray-900 rounded-lg p-4">
					<h3 className="text-xl font-semibold mb-3">Address Information</h3>
					<div className="grid grid-cols-1 gap-2 text-sm">
						<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-800 transition-colors duration-150">
							<span className="text-gray-400">Wallet Address</span>
							<span className="font-medium text-white flex items-center">
								<span className="text-xs font-mono bg-gray-800 px-2 py-1 rounded">{formatAddress(data.wallet_address)}</span>
								<button
									className="ml-2 text-blue-400 hover:text-blue-300"
									onClick={() => {
										navigator.clipboard.writeText(data.wallet_address);
									}}
								>
									<svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
									</svg>
								</button>
							</span>
						</div>
						{data.token_address && (
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-800 transition-colors duration-150">
								<span className="text-gray-400">Token Contract</span>
								<span className="font-medium text-white flex items-center">
									<span className="text-xs font-mono bg-gray-800 px-2 py-1 rounded">{formatAddress(data.token_address)}</span>
									<button
										className="ml-2 text-blue-400 hover:text-blue-300"
										onClick={() => {
											navigator.clipboard.writeText(data.token_address);
										}}
									>
										<svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
											<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
										</svg>
									</button>
								</span>
							</div>
						)}
						<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-800 transition-colors duration-150">
							<span className="text-gray-400">Network</span>
							<span className="font-medium text-white">{chainName}</span>
						</div>
						<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-800 transition-colors duration-150">
							<span className="text-gray-400">Token Decimals</span>
							<span className="font-medium text-white">{data.decimals}</span>
						</div>
					</div>
				</div>

				{/* Raw JSON data (collapsible) */}
				<details className="bg-gray-900 rounded-lg p-4">
					<summary className="text-sm font-medium text-gray-300 cursor-pointer hover:text-blue-400">
						View Raw Data
					</summary>
					<div className="p-2 mt-2 bg-gray-800 rounded border border-gray-700 overflow-auto max-h-40">
						<pre className="text-gray-300 whitespace-pre-wrap break-words">
							{JSON.stringify(data, null, 2)}
						</pre>
					</div>
				</details>
			</div>
		);
	},
});