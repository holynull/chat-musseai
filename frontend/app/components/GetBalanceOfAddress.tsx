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
	// 在移动端显示更少的字符
	const displayChars = window.innerWidth < 640 ? 4 : chars;
	return `${address.substring(0, displayChars)}...${address.substring(address.length - displayChars)}`;
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


// Create a proper React component
const BalanceDisplay: React.FC<{ input: { args: { data: Balance } } }> = ({ input }) => {
	const data: Balance = input.args.data;
	const [isMobile, setIsMobile] = useState(false);

	useEffect(() => {
		const checkMobile = () => {
			setIsMobile(window.innerWidth < 640);
		};

		checkMobile();
		window.addEventListener('resize', checkMobile);
		return () => window.removeEventListener('resize', checkMobile);
	}, []);

	if (!data || !data.success) {
		return null;
	}

	const formattedBalance = formatNumber(
		(parseFloat(data.balance) / Math.pow(10, data.decimals)).toString(),
		data.decimals
	);

	const chainName = getChainName(data.chainId);

	return (
		<div className="flex flex-col space-y-4 sm:space-y-6 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-3xl mx-auto">
			<h2 className="text-xl sm:text-2xl font-bold text-center">Wallet Balance Query</h2>

			{/* Main balance information */}
			<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
				<h3 className="text-lg sm:text-xl font-semibold mb-2 sm:mb-3">Balance Information</h3>
				<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:mb-4">
					<div>
						<p className="text-xs sm:text-sm text-gray-400">Token Balance</p>
						<p className="text-2xl sm:text-3xl font-bold text-white">
							{formattedBalance}
							<span className="text-gray-400 text-sm sm:text-base ml-1">{data.symbol}</span>
						</p>
					</div>
					<div className="flex items-center mt-1 sm:mt-0">
						<span className="text-xs sm:text-sm font-medium text-gray-400 mr-2">{chainName}</span>
						<div className="w-5 h-5 sm:w-6 sm:h-6 bg-blue-500 rounded-full flex items-center justify-center text-white text-xs font-bold">
							{data.chainId}
						</div>
					</div>
				</div>
			</div>

			{/* Address Information */}
			<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
				<h3 className="text-lg sm:text-xl font-semibold mb-2 sm:mb-3">Address Information</h3>
				<div className="grid grid-cols-1 gap-2 text-xs sm:text-sm">
					<div className="flex flex-col sm:flex-row sm:justify-between p-2 border-b border-gray-700 hover:bg-gray-800 transition-colors duration-150">
						<span className="text-gray-400 mb-1 sm:mb-0">Wallet Address</span>
						<span className="font-medium text-white flex items-center">
							<span className="text-xs font-mono bg-gray-800 px-2 py-1 rounded break-all sm:break-normal">
								{formatAddress(data.wallet_address, isMobile ? 4 : 6)}
							</span>
							<button
								className="ml-2 text-blue-400 hover:text-blue-300"
								onClick={() => {
									navigator.clipboard.writeText(data.wallet_address);
								}}
								aria-label="Copy address"
							>
								<svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
								</svg>
							</button>
						</span>
					</div>
					{data.token_address && (
						<div className="flex flex-col sm:flex-row sm:justify-between p-2 border-b border-gray-700 hover:bg-gray-800 transition-colors duration-150">
							<span className="text-gray-400 mb-1 sm:mb-0">Token Contract</span>
							<span className="font-medium text-white flex items-center">
								<span className="text-xs font-mono bg-gray-800 px-2 py-1 rounded break-all sm:break-normal">
									{formatAddress(data.token_address, isMobile ? 4 : 6)}
								</span>
								<button
									className="ml-2 text-blue-400 hover:text-blue-300"
									onClick={() => {
										navigator.clipboard.writeText(data.token_address);
									}}
									aria-label="Copy token address"
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
			<details className="bg-gray-900 rounded-lg p-3 sm:p-4">
				<summary className="text-xs sm:text-sm font-medium text-gray-300 cursor-pointer hover:text-blue-400">
					View Raw Data
				</summary>
				<div className="p-2 mt-2 bg-gray-800 rounded border border-gray-700 overflow-auto max-h-32 sm:max-h-40">
					<pre className="text-gray-300 whitespace-pre-wrap break-words text-xs sm:text-sm">
						{JSON.stringify(data, null, 2)}
					</pre>
				</div>
			</details>
		</div>
	);
};

// Update the hook to use the new component
export const useGetBalanceOfAddress = () => useAssistantToolUI({
	toolName: "get_balance_of_address",
	render: (input) => <BalanceDisplay input={input} />,
});