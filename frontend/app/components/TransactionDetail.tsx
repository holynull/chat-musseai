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

	// 在移动设备上使用更短的地址显示
	const displayLength = window.innerWidth < 640 ? 4 : length;
	return `${address.substring(0, displayLength)}...${address.substring(address.length - 4)}`;
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

// 新增: 显示地址的组件，包含复制功能
type AddressDisplayProps = {
	label: string;
	address: string;
	showCopy?: boolean;
};

const AddressDisplay = ({ label, address, showCopy = true }: AddressDisplayProps) => {
	if (!address) return null;

	return (
		<li className="flex flex-col sm:flex-row sm:justify-between gap-1 sm:items-center py-1">
			<span className="text-sm text-gray-400">{label}:</span>
			<div className="flex items-center space-x-1 break-all">
				<span className="text-sm text-white font-mono">{truncateAddress(address)}</span>
				{showCopy && (
					<button
						onClick={() => copyToClipboard(address)}
						className="p-1.5 hover:bg-gray-700 rounded-full transition-colors duration-200 flex-shrink-0"
						title={`Copy ${label}`}
						aria-label={`Copy ${label}`}
					>
						<svg className="w-4 h-4 text-gray-400 hover:text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
						</svg>
					</button>
				)}
			</div>
		</li>
	);
};

// 新增: 交易信息项组件
const InfoItem = ({ label, value }: { label: string; value: string | number }) => {
	if (!value && value !== 0) return null;

	return (
		<li className="flex flex-col sm:flex-row sm:justify-between gap-1 py-1">
			<span className="text-sm text-gray-400">{label}:</span>
			<span className="text-sm text-white break-words">{value}</span>
		</li>
	);
};

export const useTransactionDetail = () => useAssistantToolUI({
	toolName: "get_transaction_details",
	render: (input) => {
		const data: TransactionDetail = input.args.data;
		const [isMobile, setIsMobile] = useState(false);

		// 响应式检测是否为移动设备
		useEffect(() => {
			const checkMobile = () => {
				setIsMobile(window.innerWidth < 640);
			};

			checkMobile();
			window.addEventListener('resize', checkMobile);
			return () => window.removeEventListener('resize', checkMobile);
		}, []);

		// if (!data) return <div className="text-gray-400">No transaction details available</div>;
		if (!data) return <></>
		const statusInfo = getStatusInfo(data.status);
		const fromAmount = parseFloat(data.fromTokenAmount);
		const toAmount = parseFloat(data.toTokenAmount);

		return data && (
			<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-3xl mx-auto sm:mt-6 md:mt-8 overflow-hidden">
				<h2 className="text-xl sm:text-2xl font-bold text-center">Transaction Details</h2>

				{/* 头部信息 - 订单ID和状态 */}
				<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
					<AddressDisplay
						label="Order ID"
						address={data.orderId}
					/>
					<span className={`text-base sm:text-lg font-bold ${statusInfo.color} mt-1 sm:mt-0`}>
						{statusInfo.label}
					</span>
				</div>

				{/* 主要内容区域 */}
				<div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-6">
					{/* 基本信息 */}
					<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
						<h3 className="text-lg sm:text-xl font-semibold mb-2 sm:mb-3">Basic Information</h3>
						<ul className="space-y-1">
							<InfoItem
								label="Created"
								value={formatDate(data.createTime)}
							/>
							{data.finishTime && (
								<InfoItem
									label="Completed"
									value={formatDate(data.finishTime)}
								/>
							)}
						</ul>

						<h3 className="text-lg sm:text-xl font-semibold mb-2 sm:mb-3 mt-4">Transaction Details</h3>
						<ul className="space-y-1">
							<InfoItem
								label="From"
								value={data.fromChain || 'BSC'}
							/>
							<InfoItem
								label="To"
								value={data.toChain || 'Solana'}
							/>
							<InfoItem
								label="Amount"
								value={`${formatNumber(fromAmount.toString())} ${data.fromCoinCode || 'USDT'}`}
							/>
							<InfoItem
								label="Receive Amount"
								value={`${formatNumber(toAmount.toString())} ${data.toCoinCode || 'SOL'}`}
							/>
							<InfoItem
								label="Slippage"
								value={`${data.slippage}%`}
							/>
							{data.fee && (
								<InfoItem
									label="Fee"
									value={`${data.fee}%`}
								/>
							)}
						</ul>
					</div>

					{/* 地址信息 */}
					<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
						<h3 className="text-lg sm:text-xl font-semibold mb-2 sm:mb-3">Address Information</h3>
						<ul className="space-y-1">
							<AddressDisplay
								label="Source Address"
								address={data.fromAddress}
							/>
							<AddressDisplay
								label="Source Token"
								address={data.fromTokenAddress}
							/>
							<AddressDisplay
								label="Target Token"
								address={data.toTokenAddress}
							/>
						</ul>

						<h3 className="text-lg sm:text-xl font-semibold mb-2 sm:mb-3 mt-4">Transaction Hash</h3>
						<ul className="space-y-2">
							{data.hash && (
								<li className="py-1">
									<a
										href={data.depositHashExplore || `https://solscan.io/tx/${data.hash}`}
										target="_blank"
										rel="noopener noreferrer"
										className="text-blue-400 hover:text-blue-300 hover:underline text-sm inline-flex items-center flex-wrap gap-1"
									>
										<span>View Transaction</span>
										<span className="text-gray-400">({truncateAddress(data.hash)})</span>
										<svg className="w-3.5 h-3.5 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
										</svg>
									</a>
								</li>
							)}
							{data.refundHash && (
								<li className="py-1">
									<a
										href={data.refundHashExplore || `https://solscan.io/tx/${data.refundHash}`}
										target="_blank"
										rel="noopener noreferrer"
										className="text-blue-400 hover:text-blue-300 hover:underline text-sm inline-flex items-center flex-wrap gap-1"
									>
										<span>View Refund Transaction</span>
										<span className="text-gray-400">({truncateAddress(data.refundHash)})</span>
										<svg className="w-3.5 h-3.5 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
										</svg>
									</a>
								</li>
							)}
						</ul>

						{data.refundReason && (
							<div className="mt-4">
								<h3 className="text-lg sm:text-xl font-semibold mb-2 sm:mb-3">Refund Information</h3>
								<div className="p-2 sm:p-3 bg-red-900 border border-red-700 rounded-md">
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
