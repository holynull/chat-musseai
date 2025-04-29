"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import Image from "next/image";
import { useState, useEffect } from "react";

export type SwapQuote = {
	amountOutMin: string
	chainFee: string
	contractAddress: string
	depositMin: string
	depositMax: string
	dex: string
	fee: string
	feeToken: string
	fromTokenAmount: string
	fromTokenDecimal: string
	toTokenAmount: string
	toTokenDecimal: string
	path: string
	logoUrl: string
	estimatedTime?: string
	instantRate?: string
	tx_detail: { to_token_symbol: any, from_token_symbol: any }
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

export const useSwapQuote = () => useAssistantToolUI({
	toolName: "swap_quote",
	render: (input) => {
		const data: SwapQuote = input.args.data;
		const from_token_symbol = data?.tx_detail?.from_token_symbol
		const to_token_symbol = data?.tx_detail?.to_token_symbol

		if (!data) return null;

		// Calculate exchange rate
		const fromAmount = parseFloat(data.fromTokenAmount) / Math.pow(10, parseInt(data.fromTokenDecimal));
		const toAmount = parseFloat(data.toTokenAmount);//parseFloat(data.toTokenAmount) / Math.pow(10, parseInt(data.toTokenDecimal));
		const exchangeRate = toAmount / fromAmount;

		// Calculate fee percentage
		const feePercent = parseFloat(data.fee) * 100;

		// Function to truncate long text
		const truncateAddress = (address: string, length = 8) => {
			if (!address) return '';
			if (address.length <= length * 2) return address;
			return `${address.substring(0, length)}...${address.substring(address.length - length)}`;
		};

		return (
			<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto">
				<h2 className="text-xl sm:text-2xl font-bold text-center">Swap Quote</h2>
				{data.logoUrl && (
					<div className="flex items-center justify-center mt-1 sm:mt-2">
						<span className="text-xs sm:text-sm text-white mr-2">{data.dex}</span>
						<Image
							src={data.logoUrl}
							alt={data.dex || "DEX Logo"}
							width={20}
							height={20}
							className="rounded-full w-5 h-5 sm:w-6 sm:h-6"
						/>
					</div>
				)}

				<div className="grid gap-3 sm:gap-4">
					{/* Main trading information */}
					<div className="flex flex-col sm:flex-row justify-between items-center p-3 bg-gray-900 rounded-lg gap-3">
						<div className="w-full sm:w-auto text-center sm:text-left">
							<p className="text-xs sm:text-sm text-gray-400">Pay</p>
							<p className="text-lg sm:text-xl font-semibold text-white">
								{formatNumber(
									(parseFloat(data.fromTokenAmount) / Math.pow(10, parseInt(data.fromTokenDecimal))).toString()
								)}
								<span className="text-gray-400 text-sm sm:text-base ml-1">{from_token_symbol}</span>
							</p>
						</div>
						<div className="text-blue-500 transform rotate-90 sm:rotate-0 transition-transform duration-200 hover:scale-110">
							<svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 sm:h-6 sm:w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
							</svg>
						</div>
						<div className="w-full sm:w-auto text-center sm:text-left">
							<p className="text-xs sm:text-sm text-gray-400">Receive</p>
							<p className="text-lg sm:text-xl font-semibold text-white">
								{toAmount}
								<span className="text-gray-400 text-sm sm:text-base ml-1">{to_token_symbol}</span>
							</p>
						</div>
					</div>

					{/* Transaction details */}
					<div className="mt-2 sm:mt-4">
						<h4 className="text-xs sm:text-sm font-medium text-white mb-2">Transaction Details</h4>
						<div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs sm:text-sm">
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Exchange Rate</span>
								<span className="font-medium text-white truncate max-w-[150px] sm:max-w-none">
									1 {from_token_symbol} ≈ {exchangeRate.toFixed(6)} {to_token_symbol}
								</span>
							</div>
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Fee</span>
								<span className="font-medium text-white">{feePercent.toFixed(2)}%</span>
							</div>
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Min Deposit</span>
								<span className="font-medium text-white">{formatNumber(data.depositMin)} {from_token_symbol}</span>
							</div>
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Max Deposit</span>
								<span className="font-medium text-white">{formatNumber(data.depositMax)} {from_token_symbol}</span>
							</div>
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Chain Fee</span>
								<span className="font-medium text-white">{data.chainFee} {to_token_symbol}</span>
							</div>
							{data.estimatedTime && (
								<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
									<span className="text-gray-400">Estimated Time</span>
									<span className="font-medium text-white">{data.estimatedTime} sec</span>
								</div>
							)}
						</div>
					</div>

					{/* Contract information */}
					<div className="mt-1 sm:mt-2">
						<h4 className="text-xs sm:text-sm font-medium text-white mb-2">Contract Info</h4>
						<div className="text-xxs sm:text-xs bg-gray-900 p-2 rounded overflow-hidden text-gray-400 border border-gray-700 hover:bg-gray-700 transition-all duration-200">
							<div className="truncate" title={data.contractAddress}>
								<span className="font-medium text-white">Contract Address: </span>
								<span className="hidden sm:inline">{data.contractAddress}</span>
								<span className="inline sm:hidden">{truncateAddress(data.contractAddress)}</span>
							</div>
						</div>
					</div>
				</div>
			</div>
		);
	},
});