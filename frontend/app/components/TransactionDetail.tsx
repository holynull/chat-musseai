"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect } from "react";
import { toast } from "react-toastify"; // 如果您使用 react-toastify

export type TransactionDetail = {
	id: string                  // Record ID
	orderId: string             // Order number
	fromTokenAddress: string    // Source token contract address
	toTokenAddress: string      // Target token contract address
	fromTokenAmount: string     // Source token amount
	toTokenAmount: string       // Target token expected amount
	fromAmount: string          // Formatted source amount
	toAmount: string            // Formatted target amount
	fromDecimals: string        // Source token decimals
	toDecimals: string          // Target token decimals
	fromAddress: string         // User's source address
	slippage: string            // Slippage
	fromChain: string           // Source chain
	toChain: string             // Target chain
	hash: string                // Deposit hash
	depositHashExplore: string  // Deposit block explorer URL
	dexName: string             // DEX name
	status: string              // Order status
	createTime: string          // Order creation time
	finishTime: string          // Order finish time
	source: string              // Source platform
	fromCoinCode: string        // Source token symbol
	toCoinCode: string          // Target token symbol
	equipmentNo: string         // Equipment number
	refundCoinAmt: string       // Refund amount
	refundHash: string          // Refund hash
	refundHashExplore: string   // Refund explorer URL
	refundReason: string        // Refund reason
	platformSource: string      // Platform source
	fee: string                 // Fee
	confirms: string            // Confirmations
};

// Format date function
const formatDate = (dateString: string): string => {
	if (!dateString) return "";
	const date = new Date(dateString);
	return date.toLocaleString('en-US', {
		year: 'numeric',
		month: 'short',
		day: 'numeric',
		hour: 'numeric',
		minute: 'numeric',
		second: 'numeric',
		hour12: true
	});
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

// Function to format status with color
const getStatusInfo = (status: string) => {
	const statusMap: Record<string, { label: string, color: string }> = {
		'receive_complete': { label: 'Completed', color: 'text-green-500' },
		'pending': { label: 'Pending', color: 'text-yellow-500' },
		'failed': { label: 'Failed', color: 'text-red-500' },
		'processing': { label: 'Processing', color: 'text-blue-500' }
	};

	return statusMap[status] || { label: status, color: 'text-gray-400' };
};

// Truncate address for display
const truncateAddress = (address: string, length = 6) => {
	if (!address) return '';
	return `${address.substring(0, length)}...${address.substring(address.length - 4)}`;
};

// Copy to clipboard function
const copyToClipboard = async (text: string) => {
	try {
		await navigator.clipboard.writeText(text);
		toast?.success('Copied successfully');
	} catch (err) {
		console.error('Failed to copy:', err);
		toast?.error('Failed to copy');
	}
};

export const useTransactionDetail = () => useAssistantToolUI({
	toolName: "get_transaction_details",
	render: (input) => {
		const data: TransactionDetail = input.args.data;

		// if (!data) return <div className="text-gray-400">No transaction details available</div>;
		if (!data) return <></>
		const statusInfo = getStatusInfo(data.status);
		const fromAmount = parseFloat(data.fromTokenAmount);
		const toAmount = parseFloat(data.toTokenAmount);

		return data && (
			<div className="flex flex-col space-y-6 p-4 rounded-lg border border-gray-700 bg-gray-800 text-white max-w-3xl sm:mt-6 md:mt-8">
				<h2 className="text-2xl font-bold text-center">Transaction Details</h2>

				<div className="flex items-center justify-between">
					<div className="flex items-center space-x-2">
						<span className="text-sm text-gray-400">Order ID:</span>
						<div className="flex items-center space-x-1">
							<span className="text-sm text-white">{truncateAddress(data.orderId)}</span>
							<button
								onClick={() => copyToClipboard(data.orderId)}
								className="p-1 hover:bg-gray-700 rounded-full transition-colors duration-200"
								title="Copy Order ID"
							>
								<svg className="w-4 h-4 text-gray-400 hover:text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
								</svg>
							</button>
						</div>
					</div>
					<span className={`text-lg font-bold ${statusInfo.color}`}>
						{statusInfo.label}
					</span>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
					<div className="bg-gray-900 rounded-lg p-4">
						<h3 className="text-xl font-semibold mb-3">Basic Information</h3>
						<ul className="space-y-2">
							<li className="flex justify-between">
								<span className="text-sm text-gray-400">Created:</span>
								<span className="text-sm text-white">{formatDate(data.createTime)}</span>
							</li>
							{data.finishTime && (
								<li className="flex justify-between">
									<span className="text-sm text-gray-400">Completed:</span>
									<span className="text-sm text-white">{formatDate(data.finishTime)}</span>
								</li>
							)}
						</ul>

						<h3 className="text-xl font-semibold mb-3 mt-4">Transaction Details</h3>
						<ul className="space-y-2">
							<li className="flex justify-between">
								<span className="text-sm text-gray-400">From:</span>
								<span className="text-sm text-white">{data.fromChain || 'BSC'}</span>
							</li>
							<li className="flex justify-between">
								<span className="text-sm text-gray-400">To:</span>
								<span className="text-sm text-white">{data.toChain || 'Solana'}</span>
							</li>
							<li className="flex justify-between">
								<span className="text-sm text-gray-400">Amount:</span>
								<span className="text-sm text-white">
									{formatNumber(fromAmount.toString())} {data.fromCoinCode || 'USDT'}
								</span>
							</li>
							<li className="flex justify-between">
								<span className="text-sm text-gray-400">Receive Amount:</span>
								<span className="text-sm text-white">
									{formatNumber(toAmount.toString())} {data.toCoinCode || 'SOL'}
								</span>
							</li>
							<li className="flex justify-between">
								<span className="text-sm text-gray-400">Slippage:</span>
								<span className="text-sm text-white">{data.slippage}%</span>
							</li>
							{data.fee && (
								<li className="flex justify-between">
									<span className="text-sm text-gray-400">Fee:</span>
									<span className="text-sm text-white">{data.fee}%</span>
								</li>
							)}
						</ul>
					</div>

					<div className="bg-gray-900 rounded-lg p-4">
						<h3 className="text-xl font-semibold mb-3">Address Information</h3>
						<ul className="space-y-2">
							<li className="flex justify-between">
								<span className="text-sm text-gray-400">Source Address:</span>
								<span className="text-sm text-white font-mono">{truncateAddress(data.fromAddress)}</span>
							</li>
							<li className="flex justify-between">
								<span className="text-sm text-gray-400">Source Token:</span>
								<span className="text-sm text-white font-mono">{truncateAddress(data.fromTokenAddress)}</span>
							</li>
							<li className="flex justify-between">
								<span className="text-sm text-gray-400">Target Token:</span>
								<span className="text-sm text-white font-mono">{truncateAddress(data.toTokenAddress)}</span>
							</li>
						</ul>

						<h3 className="text-xl font-semibold mb-3 mt-4">Transaction Hash</h3>
						<ul className="space-y-2">
							{data.hash && (
								<li>
									<a
										href={data.depositHashExplore || `https://solscan.io/tx/${data.hash}`}
										target="_blank"
										rel="noopener noreferrer"
										className="text-blue-400 hover:text-blue-300 hover:underline text-sm inline-flex items-center space-x-1"
									>
										<span>View Transaction</span>
										<span className="text-gray-400">({truncateAddress(data.hash)})</span>
									</a>
								</li>
							)}
							{data.refundHash && (
								<li>
									<a
										href={data.refundHashExplore || `https://solscan.io/tx/${data.refundHash}`}
										target="_blank"
										rel="noopener noreferrer"
										className="text-blue-400 hover:text-blue-300 hover:underline text-sm inline-flex items-center space-x-1"
									>
										<span>View Refund Transaction</span>
										<span className="text-gray-400">({truncateAddress(data.refundHash)})</span>
									</a>
								</li>
							)}
						</ul>

						{data.refundReason && (
							<div className="mt-4">
								<h3 className="text-xl font-semibold mb-3">Refund Information</h3>
								<div className="p-3 bg-red-900 border border-red-700 rounded-md">
									<p className="text-sm text-red-300">{data.refundReason}</p>
								</div>
							</div>
						)}
					</div>
				</div>
			</div>
		);
	},
});