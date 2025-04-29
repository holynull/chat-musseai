"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect } from "react";

// 类型定义
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

// 格式化日期，支持移动端紧凑模式
const formatDate = (dateString: string, isCompact = false): string => {
	if (!dateString) return "";
	const date = new Date(dateString);

	// 移动端使用紧凑格式
	if (isCompact) {
		return date.toLocaleString('en-US', {
			month: 'short',
			day: 'numeric',
			hour: 'numeric',
			minute: 'numeric',
			hour12: true
		});
	}

	// PC端格式，匹配截图样式
	const month = date.toLocaleString('en-US', { month: 'short' });
	const day = date.getDate();
	const year = date.getFullYear();
	const hours = date.getHours();
	const minutes = date.getMinutes();
	const ampm = hours >= 12 ? 'PM' : 'AM';

	// 补零函数
	const padZero = (num: number): string => num < 10 ? `0${num}` : num.toString();

	return `${month} ${day}, ${year}\n${padZero(hours % 12 || 12)}:${padZero(minutes)} ${ampm}`;
};

// 格式化数字，限制小数位数
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

// 获取状态信息和对应的样式
const getStatusInfo = (status: string) => {
	const statusMap: Record<string, { label: string, color: string }> = {
		'receive_complete': { label: 'Completed', color: 'bg-green-900 text-green-300' },
		'pending': { label: 'Pending', color: 'bg-yellow-900 text-yellow-300' },
		'failed': { label: 'Failed', color: 'bg-red-900 text-red-300' },
		'processing': { label: 'Processing', color: 'bg-blue-900 text-blue-300' }
	};

	return statusMap[status] || { label: status, color: 'bg-gray-700 text-gray-300' };
};

// 截断地址，支持移动端更短的显示方式
const truncateAddress = (address: string, isMobile = false): string => {
	if (!address) return '';
	const length = isMobile ? 4 : 6;
	return `${address.substring(0, length)}...${address.substring(address.length - 4)}`;
};

// 分页按钮组件
const PaginationButton = ({
	onClick,
	disabled,
	children
}: {
	onClick: () => void,
	disabled: boolean,
	children: React.ReactNode
}) => (
	<button
		onClick={onClick}
		disabled={disabled}
		className={`px-3 py-1 rounded-md text-sm ${disabled
			? 'bg-gray-700 text-gray-500 cursor-not-allowed'
			: 'bg-gray-700 text-white hover:bg-gray-600 transition-colors'
			}`}
	>
		{children}
	</button>
);

// Create a proper React component for transaction records display
const TransactionRecordsDisplay: React.FC<{ input: { args: { data: TransactionRecord[] } } }> = ({ input }: { input: { args: { data: TransactionRecord[] } } }) => {
	const data: TransactionRecord[] = input.args.data;
	const [isMobile, setIsMobile] = useState(false);
	const [currentPage, setCurrentPage] = useState(1);
	const itemsPerPage = isMobile ? 5 : 10; // 移动端每页显示5条，桌面端显示10条

	// 计算总页数
	const totalPages = Math.ceil(data?.length / itemsPerPage);

	// 获取当前页的数据
	const getCurrentPageData = () => {
		const startIndex = (currentPage - 1) * itemsPerPage;
		const endIndex = startIndex + itemsPerPage;
		return data?.slice(startIndex, endIndex);
	};

	// 响应式处理
	useEffect(() => {
		const checkIfMobile = () => {
			const isMobileView = window.innerWidth < 768;
			setIsMobile(isMobileView);
			// 如果从桌面端切换到移动端，可能需要调整当前页码
			if (isMobileView && currentPage > Math.ceil(data?.length / 5)) {
				setCurrentPage(1);
			}
		};

		checkIfMobile();
		window.addEventListener('resize', checkIfMobile);
		return () => window.removeEventListener('resize', checkIfMobile);
	}, [data?.length, currentPage]);

	// 分页控制组件
	const Pagination = () => (
		<div className="flex items-center justify-between px-4 py-3 bg-gray-900 sm:px-6">
			<div className="flex justify-between flex-1 sm:hidden">
				<PaginationButton
					onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
					disabled={currentPage === 1}
				>
					Previous
				</PaginationButton>
				<PaginationButton
					onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
					disabled={currentPage === totalPages}
				>
					Next
				</PaginationButton>
			</div>
			<div className="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
				<div>
					<p className="text-sm text-gray-400">
						Showing{' '}
						<span className="font-medium">{((currentPage - 1) * itemsPerPage) + 1}</span>
						{' '}-{' '}
						<span className="font-medium">
							{Math.min(currentPage * itemsPerPage, data?.length)}
						</span>
						{' '}of{' '}
						<span className="font-medium">{data?.length}</span>
						{' '}results
					</p>
				</div>
				<div className="flex space-x-2">
					<PaginationButton
						onClick={() => setCurrentPage(1)}
						disabled={currentPage === 1}
					>
						First
					</PaginationButton>
					<PaginationButton
						onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
						disabled={currentPage === 1}
					>
						Previous
					</PaginationButton>
					<span className="px-3 py-1 text-sm text-white bg-gray-700 rounded-md">
						Page {currentPage} of {totalPages}
					</span>
					<PaginationButton
						onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
						disabled={currentPage === totalPages}
					>
						Next
					</PaginationButton>
					<PaginationButton
						onClick={() => setCurrentPage(totalPages)}
						disabled={currentPage === totalPages}
					>
						Last
					</PaginationButton>
				</div>
			</div>
		</div>
	);

	// 渲染单个记录卡片（移动端）
	const renderTransactionCard = (record: TransactionRecord, index: number) => {
		const fromAmount = parseFloat(record.fromTokenAmount);
		const toAmount = parseFloat(record.toTokenAmount);
		const statusInfo = getStatusInfo(record.status);

		return (
			<div key={index} className="bg-gray-800 rounded-lg p-4 space-y-3">
				{/* 头部：ID和状态 */}
				<div className="flex items-center justify-between">
					<div className="text-sm font-medium text-white">
						{truncateAddress(record.orderId, true)}
					</div>
					<span className={`px-2 py-1 text-xs font-semibold rounded-full ${statusInfo.color}`}>
						{statusInfo.label}
					</span>
				</div>

				{/* 链信息 */}
				<div className="space-y-1">
					<div className="text-xs text-gray-400">Chain</div>
					<div className="text-sm text-white flex items-center space-x-2">
						<span>{record.fromChain || 'BSC'}</span>
						<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
						</svg>
						<span>{record.toChain || 'Solana'}</span>
					</div>
					<div className="text-xs text-gray-400">{truncateAddress(record.fromAddress, true)}</div>
				</div>

				{/* 金额信息 */}
				<div className="space-y-1">
					<div className="text-xs text-gray-400">Amount</div>
					<div className="text-sm text-white">
						{formatNumber(fromAmount.toString())} {record.fromCoinCode || 'USDT'}
					</div>
					<div className="text-xs text-gray-400">
						≈ {formatNumber(toAmount.toString())} {record.toCoinCode || 'SOL'}
					</div>
				</div>

				{/* 时间信息 */}
				<div className="space-y-1">
					<div className="text-xs text-gray-400">Time</div>
					<div className="text-sm text-white">{formatDate(record.createTime, true)}</div>
					{record.finishTime && record.status === 'receive_complete' && (
						<div className="text-xs text-gray-400">
							Completed: {formatDate(record.finishTime, true)}
						</div>
					)}
				</div>

				{/* 区块浏览器链接 */}
				{record.hash && (
					<div className="pt-2 border-t border-gray-700">
						<a
							href={record.depositHashExplore || `https://solscan.io/tx/${record.hash}`}
							target="_blank"
							rel="noopener noreferrer"
							className="text-blue-400 hover:text-blue-300 text-sm flex items-center"
						>
							<span>View on Explorer</span>
							<svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
							</svg>
						</a>
					</div>
				)}
			</div>
		);
	};

	// 渲染表格行（桌面端）
	const renderTableRow = (record: TransactionRecord, index: number) => {
		const fromAmount = parseFloat(record.fromTokenAmount);
		const toAmount = parseFloat(record.toTokenAmount);
		const statusInfo = getStatusInfo(record.status);

		return (
			<tr key={index} className="hover:bg-gray-800 transition-colors duration-150">
				<td className="px-4 py-3">
					<div className="flex items-center">
						<div className="text-sm font-medium text-white">
							{truncateAddress(record.orderId)}
						</div>
					</div>
					{record.hash && (
						<div className="text-xs text-gray-400 mt-1">
							<a
								href={record.depositHashExplore || `https://solscan.io/tx/${record.hash}`}
								target="_blank"
								rel="noopener noreferrer"
								className="text-blue-400 hover:text-blue-300 hover:underline inline-flex items-center"
							>
								View on Explorer
								<svg className="w-3 h-3 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
								</svg>
							</a>
						</div>
					)}
				</td>
				<td className="px-4 py-3">
					<div className="text-sm text-white flex items-center space-x-2">
						<span>{record.fromChain || 'BSC'}</span>
						<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
						</svg>
						<span>{record.toChain || 'Solana'}</span>
					</div>
					<div className="text-xs text-gray-400 mt-1">
						{truncateAddress(record.fromAddress)}
					</div>
				</td>
				<td className="px-4 py-3">
					<div className="text-sm text-white">
						{formatNumber(fromAmount.toString())} {record.fromCoinCode || 'USDT'}
					</div>
					<div className="text-xs text-gray-400 mt-1">
						≈ {formatNumber(toAmount.toString())} {record.toCoinCode || 'SOL'}
					</div>
				</td>
				<td className="px-4 py-3">
					<span className={`px-2 py-1 text-xs font-semibold rounded-full ${statusInfo.color}`}>
						{statusInfo.label}
					</span>
				</td>
				<td className="px-4 py-3">
					<div className="text-sm text-white whitespace-pre-line">
						{formatDate(record.createTime)}
					</div>
					{record.finishTime && record.status === 'receive_complete' && (
						<div className="text-xs text-gray-400 mt-1">
							Completed: {formatDate(record.finishTime)}
						</div>
					)}
				</td>
			</tr>
		);
	};

	// 主渲染
	return data && (
		<div className="w-full mx-auto max-w-7xl">
			<div className="flex flex-col rounded-lg border border-gray-700 bg-gray-800 text-white overflow-hidden">
				{/* 头部 */}
				<div className="bg-gray-900 p-4 sm:p-6">
					<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between">
						<h3 className="text-xl font-semibold">Transaction Records</h3>
						<span className="text-sm text-gray-400 mt-2 sm:mt-0">
							{data?.length} transaction{data?.length !== 1 ? 's' : ''}
						</span>
					</div>
				</div>

				{/* 内容区域 */}
				<div className="p-4 sm:p-6">
					{/* 桌面端表格视图 */}
					<div className="hidden md:block overflow-x-auto">
						<table className="min-w-full divide-y divide-gray-700">
							<thead>
								<tr>
									<th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
										Transaction
									</th>
									<th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
										Chain
									</th>
									<th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
										Amount
									</th>
									<th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
										Status
									</th>
									<th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
										Time
									</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-700">
								{getCurrentPageData().map((record, index) => renderTableRow(record, index))}
							</tbody>
						</table>
					</div>

					{/* 移动端卡片视图 */}
					<div className="md:hidden space-y-4">
						{getCurrentPageData().map((record, index) => renderTransactionCard(record, index))}
					</div>
				</div>

				{/* 分页控件 */}
				{totalPages > 1 && <Pagination />}
			</div>
		</div>
	);
};

// Update the hook to use the new component
export const useTransactionRecords = () => useAssistantToolUI({
	toolName: "get_transaction_records",
	render: (input) => <TransactionRecordsDisplay input={input} />,
});