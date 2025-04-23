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

		return (
			<div className="rounded-lg border border-gray-200 overflow-hidden bg-white shadow-sm sm:mt-6 md:mt-8">
				<div className="p-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
					<div className="flex items-center justify-between">
						<h3 className="text-lg font-medium text-gray-800">Swap Quote</h3>
						{data.logoUrl && (
							<div className="flex items-center">
								<span className="text-sm text-gray-700 mr-2">{data.dex}</span>
								<Image
									src={data.logoUrl}
									alt={data.dex || "DEX Logo"}
									width={24}
									height={24}
									className="rounded-full"
								/>
							</div>
						)}
					</div>
				</div>

				<div className="p-4">
					<div className="grid gap-4">
						{/* Main trading information */}
						<div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg border border-gray-200">
							<div>
								<p className="text-sm text-gray-700">Pay</p>
								<p className="text-xl font-semibold text-gray-800">
									{formatNumber(
										(parseFloat(data.fromTokenAmount) / Math.pow(10, parseInt(data.fromTokenDecimal))).toString()
									)}
									<span className="text-gray-600 text-base ml-1">{from_token_symbol}</span>
								</p>
							</div>
							<div className="text-blue-500 transform transition-transform duration-200 hover:scale-110">
								<svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
								</svg>
							</div>
							<div>
								<p className="text-sm text-gray-700">Receive</p>
								<p className="text-xl font-semibold text-gray-800">
									{toAmount}
									<span className="text-gray-600 text-base ml-1">{to_token_symbol}</span>
								</p>
							</div>
						</div>

						{/* Transaction details */}
						<div className="mt-4">
							<h4 className="text-sm font-medium text-gray-800 mb-2">Transaction Details</h4>
							<div className="grid grid-cols-2 gap-2 text-sm">
								<div className="flex justify-between p-2 border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
									<span className="text-gray-700">Exchange Rate</span>
									<span className="font-medium text-gray-800">1 {from_token_symbol} ≈ {exchangeRate.toFixed(6)} {to_token_symbol}</span>
								</div>
								<div className="flex justify-between p-2 border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
									<span className="text-gray-700">Fee</span>
									<span className="font-medium text-gray-800">{feePercent.toFixed(2)}%</span>
								</div>
								<div className="flex justify-between p-2 border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
									<span className="text-gray-700">Min Deposit</span>
									<span className="font-medium text-gray-800">{formatNumber(data.depositMin)} {from_token_symbol}</span>
								</div>
								<div className="flex justify-between p-2 border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
									<span className="text-gray-700">Max Deposit</span>
									<span className="font-medium text-gray-800">{formatNumber(data.depositMax)} {from_token_symbol}</span>
								</div>
								<div className="flex justify-between p-2 border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
									<span className="text-gray-700">Chain Fee</span>
									<span className="font-medium text-gray-800">{data.chainFee} {to_token_symbol}</span>
								</div>
								{data.estimatedTime && (
									<div className="flex justify-between p-2 border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
										<span className="text-gray-700">Estimated Time</span>
										<span className="font-medium text-gray-800">{data.estimatedTime} sec</span>
									</div>
								)}
							</div>
						</div>

						{/* Contract information */}
						<div className="mt-2">
							<h4 className="text-sm font-medium text-gray-800 mb-2">Contract Info</h4>
							<div className="text-xs bg-gray-50 p-2 rounded overflow-hidden text-gray-700 border border-gray-200 hover:bg-blue-50 transition-all duration-200">
								<div className="truncate" title={data.contractAddress}>
									<span className="font-medium text-gray-800">Contract Address: </span>
									{data.contractAddress}
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		);
	},
});