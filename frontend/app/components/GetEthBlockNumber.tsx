"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect, useCallback } from "react";

export type EthBlockNumberData = {
	block_number: number;
	network: string;
	network_type: string;
};

// Format block number function
const formatBlockNumber = (blockNumber: number): string => {
	return blockNumber.toLocaleString('en-US');
};

export const useGetEthBlockNumber = () => useAssistantToolUI({
	toolName: "get_eth_block_number",
	render: (input) => {
		const data: EthBlockNumberData = input.args.data;

		if (!data) return null;

		return (
			<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto">
				<h2 className="text-xl sm:text-2xl font-bold text-center">Blockchain Info</h2>

				<div className="grid gap-3 sm:gap-4">
					{/* Main information */}
					<div className="flex flex-col sm:flex-row justify-between items-center p-3 bg-gray-900 rounded-lg gap-3">
						<div className="w-full sm:w-auto text-center sm:text-left">
							<p className="text-xs sm:text-sm text-gray-400">Network</p>
							<p className="text-lg sm:text-xl font-semibold text-white">
								{data.network.charAt(0).toUpperCase() + data.network.slice(1)} ({data.network_type})
							</p>
						</div>
						<div className="text-blue-500 transform rotate-90 sm:rotate-0 transition-transform duration-200 hover:scale-110">
							<svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 sm:h-6 sm:w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
							</svg>
						</div>
						<div className="w-full sm:w-auto text-center sm:text-left">
							<p className="text-xs sm:text-sm text-gray-400">Current Block Height</p>
							<p className="text-lg sm:text-xl font-semibold text-white">
								{formatBlockNumber(data.block_number)}
							</p>
						</div>
					</div>

					{/* Additional details */}
					<div className="mt-2 sm:mt-4">
						<h4 className="text-xs sm:text-sm font-medium text-white mb-2">Details</h4>
						<div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs sm:text-sm">
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Block Number (Hex)</span>
								<span className="font-medium text-white">{`0x${data.block_number.toString(16)}`}</span>
							</div>
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Network Type</span>
								<span className="font-medium text-white">{data.network_type}</span>
							</div>
						</div>
					</div>
				</div>
			</div>
		);
	},
});
