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
		'receive_complete': { label: 'Completed', color: 'bg-green-100 text-green-800' },
		'pending': { label: 'Pending', color: 'bg-yellow-100 text-yellow-800' },
		'failed': { label: 'Failed', color: 'bg-red-100 text-red-800' },
		'processing': { label: 'Processing', color: 'bg-blue-100 text-blue-800' }
	};

	return statusMap[status] || { label: status, color: 'bg-gray-100 text-gray-800' };
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

		if (!data) return <div className="text-gray-500">No transaction details available</div>;

		const statusInfo = getStatusInfo(data.status);
		const fromAmount = parseFloat(data.fromTokenAmount);
		const toAmount = parseFloat(data.toTokenAmount);

		return (
			<div className="rounded-lg border border-gray-200 overflow-hidden bg-white shadow-sm">
				<div className="p-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
					<div className="flex items-center justify-between">
						<h3 className="text-lg font-medium text-gray-900">Transaction Details</h3>
						<div className="flex items-center space-x-2">
							<span className="text-sm text-gray-500">Order ID:</span>
							<div className="flex items-center space-x-1">
								<span className="text-sm text-gray-700">{truncateAddress(data.orderId)}</span>
								<button
									onClick={() => copyToClipboard(data.orderId)}
									className="p-1 hover:bg-gray-100 rounded-full transition-colors duration-200"
									title="Copy Order ID"
								>
									<svg className="w-4 h-4 text-gray-500 hover:text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
									</svg>
								</button>
							</div>
						</div>
					</div>
				</div>

				<div className="p-4">
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
						<div className="space-y-4">
							<div>
								<h4 className="text-sm font-medium text-gray-700 uppercase tracking-wider mb-2">Basic Information</h4>
								<ul className="space-y-2">
									<li className="flex justify-between">
										<span className="text-sm text-gray-500">Created:</span>
										<span className="text-sm text-gray-700">{formatDate(data.createTime)}</span>
									</li>
									{data.finishTime && (
										<li className="flex justify-between">
											<span className="text-sm text-gray-500">Completed:</span>
											<span className="text-sm text-gray-700">{formatDate(data.finishTime)}</span>
										</li>
									)}
									<li className="flex justify-between">
										<span className="text-sm text-gray-500">Status:</span>
										<span className={`px-2 py-1 text-xs leading-5 font-semibold rounded-full ${statusInfo.color}`}>
											{statusInfo.label}
										</span>
									</li>
								</ul>
							</div>

							<div>
								<h4 className="text-sm font-medium text-gray-700 uppercase tracking-wider mb-2">Transaction Details</h4>
								<ul className="space-y-2">
									<li className="flex justify-between">
										<span className="text-sm text-gray-500">From:</span>
										<span className="text-sm text-gray-700">{data.fromChain || 'BSC'}</span>
									</li>
									<li className="flex justify-between">
										<span className="text-sm text-gray-500">To:</span>
										<span className="text-sm text-gray-700">{data.toChain || 'Solana'}</span>
									</li>
									<li className="flex justify-between">
										<span className="text-sm text-gray-500">Amount:</span>
										<span className="text-sm text-gray-700">
											{formatNumber(fromAmount.toString())} {data.fromCoinCode || 'USDT'}
										</span>
									</li>
									<li className="flex justify-between">
										<span className="text-sm text-gray-500">Receive Amount:</span>
										<span className="text-sm text-gray-700">
											{formatNumber(toAmount.toString())} {data.toCoinCode || 'SOL'}
										</span>
									</li>
									<li className="flex justify-between">
										<span className="text-sm text-gray-500">Slippage:</span>
										<span className="text-sm text-gray-700">{data.slippage}%</span>
									</li>
									{data.fee && (
										<li className="flex justify-between">
											<span className="text-sm text-gray-500">Fee:</span>
											<span className="text-sm text-gray-700">{data.fee}%</span>
										</li>
									)}
								</ul>
							</div>
						</div>

						<div className="space-y-4">
							<div>
								<h4 className="text-sm font-medium text-gray-700 uppercase tracking-wider mb-2">Address Information</h4>
								<ul className="space-y-2">
									<li className="flex justify-between">
										<span className="text-sm text-gray-500">Source Address:</span>
										<span className="text-sm text-gray-700 font-mono">{truncateAddress(data.fromAddress)}</span>
									</li>
									<li className="flex justify-between">
										<span className="text-sm text-gray-500">Source Token:</span>
										<span className="text-sm text-gray-700 font-mono">{truncateAddress(data.fromTokenAddress)}</span>
									</li>
									<li className="flex justify-between">
										<span className="text-sm text-gray-500">Target Token:</span>
										<span className="text-sm text-gray-700 font-mono">{truncateAddress(data.toTokenAddress)}</span>
									</li>
								</ul>
							</div>

							<div>
								<h4 className="text-sm font-medium text-gray-700 uppercase tracking-wider mb-2">Transaction Hash</h4>
								<ul className="space-y-2">
									{data.hash && (
										<li>
											<a
												href={data.depositHashExplore || `https://solscan.io/tx/${data.hash}`}
												target="_blank"
												rel="noopener noreferrer"
												className="text-blue-600 hover:text-blue-800 hover:underline text-sm inline-flex items-center space-x-1"
											>
												<span>View Transaction</span>
												<span className="text-gray-500">({truncateAddress(data.hash)})</span>
											</a>
										</li>
									)}
									{data.refundHash && (
										<li>
											<a
												href={data.refundHashExplore || `https://solscan.io/tx/${data.refundHash}`}
												target="_blank"
												rel="noopener noreferrer"
												className="text-blue-600 hover:text-blue-800 hover:underline text-sm inline-flex items-center space-x-1"
											>
												<span>View Refund Transaction</span>
												<span className="text-gray-500">({truncateAddress(data.refundHash)})</span>
											</a>
										</li>
									)}
								</ul>
							</div>

							{data.refundReason && (
								<div>
									<h4 className="text-sm font-medium text-gray-700 uppercase tracking-wider mb-2">Refund Information</h4>
									<div className="p-3 bg-red-50 border border-red-100 rounded-md">
										<p className="text-sm text-red-700">{data.refundReason}</p>
									</div>
								</div>
							)}
						</div>
					</div>
				</div>
			</div>
		);
	},
});