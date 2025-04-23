"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect } from "react";

export type TransactionRecord = {
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
	depositHashExplore: string  // Deposit explorer URL
	dexName: string             // DEX name
	status: string              // Order status
	createTime: string          // Order creation time
	finishTime: string          // Order finish time
	source: string              // Source platform
	fee: string                 // Fee percentage
	fromCoinCode: string        // Source token symbol
	toCoinCode: string          // Target token symbol
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

export const useTransactionRecords = () => useAssistantToolUI({
	toolName: "get_transaction_records",
	render: (input) => {
		const data: TransactionRecord[] = input.args.data;

		return data && data.length > 0 && (
			<div className="rounded-lg border border-gray-200 overflow-hidden bg-white shadow-sm sm:mt-6 md:mt-8">
				<div className="p-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
					<div className="flex items-center justify-between">
						<h3 className="text-lg font-medium text-gray-800">Transaction Records</h3>
						<span className="text-sm text-gray-600">{data.length} transactions</span>
					</div>
				</div>

				<div className="overflow-x-auto">
					<table className="min-w-full divide-y divide-gray-200">
						<thead className="bg-gray-50">
							<tr>
								<th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
									Transaction
								</th>
								<th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
									From → To
								</th>
								<th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
									Amount
								</th>
								<th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
									Status
								</th>
								<th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
									Time
								</th>
							</tr>
						</thead>
						<tbody className="bg-white divide-y divide-gray-200">
							{data.map((record, index) => {
								// 直接使用已格式化的金额
								const fromAmount = parseFloat(record.fromTokenAmount);
								const toAmount = parseFloat(record.toTokenAmount);
								const statusInfo = getStatusInfo(record.status);

								return (
									<tr key={index} className="hover:bg-gray-50 transition-colors duration-150">
										<td className="px-4 py-3 whitespace-nowrap">
											<div className="flex items-center">
												<div className="text-sm font-medium text-gray-900">
													{truncateAddress(record.orderId)}
												</div>
											</div>
											<div className="text-xs text-gray-500">
												{record.hash && (
													<a
														href={record.depositHashExplore || `https://solscan.io/tx/${record.hash}`}
														target="_blank"
														rel="noopener noreferrer"
														className="text-blue-600 hover:text-blue-800 hover:underline"
													>
														View on Explorer
													</a>
												)}
											</div>
										</td>
										<td className="px-4 py-3 whitespace-nowrap">
											<div className="text-sm text-gray-900">
												{record.fromChain || 'BSC'} → {record.toChain || 'Solana'}
											</div>
											<div className="text-xs text-gray-500">
												{truncateAddress(record.fromAddress)}
											</div>
										</td>
										<td className="px-4 py-3 whitespace-nowrap">
											<div className="text-sm text-gray-900">
												{formatNumber(fromAmount.toString())} {record.fromCoinCode || 'USDT'}
											</div>
											<div className="text-xs text-gray-500">
												≈ {formatNumber(toAmount.toString())} {record.toCoinCode || 'SOL'}
											</div>
										</td>
										<td className="px-4 py-3 whitespace-nowrap">
											<span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${statusInfo.color}`}>
												{statusInfo.label}
											</span>
										</td>
										<td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
											<div>{formatDate(record.createTime)}</div>
											{record.finishTime && record.status === 'receive_complete' && (
												<div className="text-xs text-gray-400">
													Completed: {formatDate(record.finishTime)}
												</div>
											)}
										</td>
									</tr>
								);
							})}
						</tbody>
					</table>
				</div>
			</div>
		);
	},
});