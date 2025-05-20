"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect } from "react";

export type MaxPriorityFeePerGasData = {
	result: string;
	method: string;
	network: string;
	network_type: string;
};

// Format the gas fee in Gwei
const formatGasInGwei = (value: string): string => {
	if (!value || !value.startsWith("0x")) return "N/A";

	try {
		// Convert hex to decimal
		const weiValue = parseInt(value, 16);
		// Convert wei to gwei (divide by 10^9)
		const gweiValue = weiValue / 1000000000;

		// Format to 2 decimal places
		return gweiValue.toFixed(2);
	} catch (e) {
		console.error("Error formatting gas value:", e);
		return "Error";
	}
};

export const useEthMaxPriorityFeePerGas = () => useAssistantToolUI({
	toolName: "eth_maxPriorityFeePerGas",
	render: (input) => {
		const data: MaxPriorityFeePerGasData = input.args.data;

		if (!data || !data.result) return null;

		// Format the priority fee into a more readable format
		const priorityFeeGwei = formatGasInGwei(data.result);

		// Get network name with proper capitalization
		const networkName = data.network.charAt(0).toUpperCase() + data.network.slice(1);
		const networkType = data.network_type.charAt(0).toUpperCase() + data.network_type.slice(1);

		return (
			<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-md mx-auto">
				<h2 className="text-xl sm:text-2xl font-bold text-center">Max Priority Fee</h2>

				<div className="flex flex-col space-y-3">
					<div className="flex justify-between items-center p-3 bg-gray-900 rounded-lg">
						<span className="text-gray-400">Network</span>
						<span className="font-medium text-white">{networkName} {networkType}</span>
					</div>

					<div className="flex justify-between items-center p-3 bg-gray-900 rounded-lg">
						<span className="text-gray-400">Max Priority Fee</span>
						<div className="flex flex-col items-end">
							<span className="font-medium text-white">{priorityFeeGwei} Gwei</span>
							<span className="text-xs text-gray-400">({data.result} Wei)</span>
						</div>
					</div>
				</div>

				<div className="text-xs text-gray-400 text-center mt-2">
					The Max Priority Fee represents the maximum amount of gas fee that users are willing to pay to miners/validators above the base fee.
				</div>
			</div>
		);
	},
});
