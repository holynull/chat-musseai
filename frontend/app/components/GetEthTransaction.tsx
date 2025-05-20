"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect } from "react";

export type TransactionDetails = {
	hash: string;
	blockNumber: number;
	from: string;
	to: string;
	value: string;
	gas: number;
	gasPrice: string;
	nonce: number;
	transactionIndex: number;
	network: string;
	network_type: string;
	explorer_url: string;
};

// Format Ethereum address function
const formatAddress = (address: string): string => {
	if (!address) return '';
	return `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
};

// Format wei to ETH
const formatWei = (wei: string): string => {
	const web3Value = parseInt(wei) / 1e18;
	return web3Value.toFixed(6);
};

// Format gas price (wei) to Gwei
const formatGasPrice = (gasPrice: string): string => {
	const gweiValue = parseInt(gasPrice) / 1e9;
	return gweiValue.toFixed(2);
};

export const useGetEthTransaction = () => useAssistantToolUI({
	toolName: "get_eth_transaction",
	render: (input) => {
		const data: TransactionDetails = input.args.data;

		if (!data) return null;

		return (
			<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto">
				<h2 className="text-xl sm:text-2xl font-bold text-center">Transaction Details</h2>

				<div className="grid gap-3 sm:gap-4">
					{/* Transaction header */}
					<div className="flex flex-col sm:flex-row justify-between items-center p-3 bg-gray-900 rounded-lg gap-3">
						<div className="w-full sm:w-auto text-center sm:text-left">
							<p className="text-xs sm:text-sm text-gray-400">Network</p>
							<p className="text-lg sm:text-xl font-semibold text-white">
								{data.network} ({data.network_type})
							</p>
						</div>
						<div className="text-blue-500">
							<svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 sm:h-6 sm:w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
							</svg>
						</div>
						<div className="w-full sm:w-auto text-center sm:text-left">
							<p className="text-xs sm:text-sm text-gray-400">Block Number</p>
							<p className="text-lg sm:text-xl font-semibold text-white">
								{data.blockNumber}
							</p>
						</div>
					</div>

					{/* Transaction details */}
					<div className="mt-2 sm:mt-4">
						<h4 className="text-xs sm:text-sm font-medium text-white mb-2">Transaction Information</h4>
						<div className="grid grid-cols-1 gap-2 text-xs sm:text-sm">
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Transaction Hash</span>
								<span className="font-medium text-white break-all">{data.hash}</span>
							</div>

							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">From</span>
								<span className="font-medium text-white">
									<span className="hidden sm:inline break-all">{data.from}</span>
									<span className="inline sm:hidden">{formatAddress(data.from)}</span>
								</span>
							</div>

							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">To</span>
								<span className="font-medium text-white">
									<span className="hidden sm:inline break-all">{data.to}</span>
									<span className="inline sm:hidden">{formatAddress(data.to)}</span>
								</span>
							</div>

							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Value</span>
								<span className="font-medium text-white">{formatWei(data.value)} ETH</span>
							</div>

							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Gas Limit</span>
								<span className="font-medium text-white">{data.gas}</span>
							</div>

							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Gas Price</span>
								<span className="font-medium text-white">{formatGasPrice(data.gasPrice)} Gwei</span>
							</div>

							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Nonce</span>
								<span className="font-medium text-white">{data.nonce}</span>
							</div>

							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Transaction Index</span>
								<span className="font-medium text-white">{data.transactionIndex}</span>
							</div>
						</div>
					</div>

					{/* Explorer link */}
					<div className="mt-1 sm:mt-2">
						<h4 className="text-xs sm:text-sm font-medium text-white mb-2">Explorer</h4>
						<a
							href={data.explorer_url}
							target="_blank"
							rel="noopener noreferrer"
							className="flex items-center justify-center p-2 bg-gray-700 hover:bg-gray-600 rounded text-center text-blue-400 hover:text-blue-300 transition-colors duration-150"
						>
							View on Blockchain Explorer
							<svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 ml-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
							</svg>
						</a>
					</div>
				</div>
			</div>
		);
	},
});
