"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import Image from "next/image";
import { useState, useEffect } from "react";

export type Allowance = {
	success: boolean,
	allowance: string,
	owner_address: string,
	spender_address: string,
	token_address: string,
	symbol: string,
	decimals: number,
	chainId: number,
};

// Format number function
const formatNumber = (value: string, decimals: string | number = 6): string => {
	const num = parseFloat(value);
	if (isNaN(num)) return value;

	const decimalPlaces = typeof decimals === 'string' ? parseInt(decimals) : decimals;
	const maxDecimals = Math.min(decimalPlaces, 8);

	return num.toLocaleString('en-US', {
		minimumFractionDigits: 2,
		maximumFractionDigits: maxDecimals
	});
};

export const useAllowanceERC20 = () => useAssistantToolUI({
	toolName: "allowance_erc20",
	render: (input) => {
		const data: Allowance = input.args.data;

		if (!data || !data.success) return null;

		// Calculate formatted allowance amount
		const allowanceAmount = data.allowance
			? parseFloat(data.allowance) / Math.pow(10, data.decimals)
			: 0;

		return (
			<div className="flex flex-col space-y-6 p-4 rounded-lg border border-gray-700 bg-gray-800 text-white max-w-3xl sm:mt-6 md:mt-8">
				<h2 className="text-2xl font-bold text-center">Token Allowance</h2>

				{/* Main allowance information */}
				<div className="bg-gray-900 rounded-lg p-4">
					<h3 className="text-xl font-semibold mb-3">Current Allowance</h3>
					<div className="flex items-center justify-center mb-4">
						<span className="text-3xl font-bold">
							{formatNumber(allowanceAmount.toString(), data.decimals)}
							<span className="text-gray-400 text-xl ml-1">{data.symbol}</span>
						</span>
					</div>
				</div>

				{/* Allowance details */}
				<div className="bg-gray-900 rounded-lg p-4">
					<h3 className="text-xl font-semibold mb-2">Allowance Details</h3>
					<div className="grid grid-cols-1 gap-2">
						<div className="flex justify-between p-2 border-b border-gray-700">
							<span>Owner</span>
							<span className="font-medium text-xs truncate max-w-[200px]" title={data.owner_address}>
								{data.owner_address}
							</span>
						</div>
						<div className="flex justify-between p-2 border-b border-gray-700">
							<span>Spender</span>
							<span className="font-medium text-xs truncate max-w-[200px]" title={data.spender_address}>
								{data.spender_address}
							</span>
						</div>
						<div className="flex justify-between p-2 border-b border-gray-700">
							<span>Chain ID</span>
							<span className="font-medium">{data.chainId}</span>
						</div>
					</div>
				</div>

				{/* Token information */}
				<div className="bg-gray-900 rounded-lg p-4">
					<h3 className="text-xl font-semibold mb-2">Token Info</h3>
					<div className="bg-gray-800 p-2 rounded overflow-hidden text-xs">
						<div className="truncate" title={data.token_address}>
							<span className="font-medium">Token Address: </span>
							{data.token_address}
						</div>
					</div>
				</div>
			</div>
		);
	},
});