"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect } from "react";

export type TransactionCountData = {
	address: string;
	transaction_count: number;
	transaction_count_hex: string;
	network: string;
	network_type: string;
	block_parameter?: string;
};

// Format address to display format
const formatAddress = (address: string, length = 6): string => {
	if (!address) return '';
	if (address.length <= length * 2) return address;
	return `${address.substring(0, length)}...${address.substring(address.length - length)}`;
};

export const useEthGetTransactionCount = () => useAssistantToolUI({
	toolName: "eth_getTransactionCount",
	render: (input) => {
		const data: TransactionCountData = input.args.data;

		if (!data) return null;

		return (
			<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto">
				<h2 className="text-xl sm:text-2xl font-bold text-center">Transaction Count</h2>

				<div className="grid gap-3 sm:gap-4">
					{/* Main information */}
					<div className="flex flex-col sm:flex-row justify-between items-center p-3 bg-gray-900 rounded-lg gap-3">
						<div className="w-full sm:w-auto text-center sm:text-left">
							<p className="text-xs sm:text-sm text-gray-400">Address</p>
							<p className="text-sm sm:text-base font-semibold text-white">
								<span className="hidden sm:inline">{data.address}</span>
								<span className="inline sm:hidden">{formatAddress(data.address)}</span>
							</p>
						</div>
						<div className="w-full sm:w-auto text-center sm:text-left">
							<p className="text-xs sm:text-sm text-gray-400">Transaction Count</p>
							<p className="text-lg sm:text-xl font-semibold text-white">
								{data.transaction_count}
							</p>
						</div>
					</div>

					{/* Transaction details */}
					<div className="mt-2 sm:mt-4">
						<h4 className="text-xs sm:text-sm font-medium text-white mb-2">Network Details</h4>
						<div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs sm:text-sm">
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Network</span>
								<span className="font-medium text-white">{data.network}</span>
							</div>
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Network Type</span>
								<span className="font-medium text-white">{data.network_type}</span>
							</div>
							{data.block_parameter && (
								<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
									<span className="text-gray-400">Block Parameter</span>
									<span className="font-medium text-white">{data.block_parameter}</span>
								</div>
							)}
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Hex Value</span>
								<span className="font-medium text-white">{data.transaction_count_hex}</span>
							</div>
						</div>
					</div>

					{/* Description */}
					<div className="mt-1 sm:mt-2 text-xs text-gray-400 bg-gray-900 p-2 rounded">
						<p>The transaction count (nonce) represents the number of transactions sent from this address.</p>
					</div>
				</div>
			</div>
		);
	},
});
