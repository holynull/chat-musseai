"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
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

const MAX_UINT256 = "115792089237316195423570985008687907853269984665640564039457584007913129639935";

const formatNumber = (value: string, decimals: string | number = 6): string => {
	// 检查是否为最大值（unlimit）
	if (value === MAX_UINT256) {
		return "Unlimited";
	}

	// 处理空值或零值
	if (!value || value === '0') return '0';

	const num = parseFloat(value);
	if (isNaN(num)) return value;

	const decimalPlaces = typeof decimals === 'string' ? parseInt(decimals) : decimals;
	const maxDecimals = Math.min(decimalPlaces, 18);

	// 处理极小值
	if (num > 0 && num < 0.000001) {
		return '<0.000001';
	}

	// 处理大数值
	if (num >= 1000000000000) { // 万亿以上
		return (num / 1000000000000).toFixed(2) + 'T';
	} else if (num >= 1000000000) { // 十亿以上
		return (num / 1000000000).toFixed(2) + 'B';
	} else if (num >= 1000000) { // 百万以上
		return (num / 1000000).toFixed(2) + 'M';
	} else if (num >= 1000) { // 千以上
		return (num / 1000).toFixed(2) + 'K';
	}

	// 常规数字格式化
	return num.toLocaleString('en-US', {
		minimumFractionDigits: 0,
		maximumFractionDigits: maxDecimals
	});
};

const CopyIcon = ({ className = "w-4 h-4" }) => (
	<svg
		xmlns="http://www.w3.org/2000/svg"
		className={className}
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		strokeWidth="2"
		strokeLinecap="round"
		strokeLinejoin="round"
	>
		<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
		<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
	</svg>
);

// 添加检查图标组件
const CheckIcon = ({ className = "w-4 h-4" }) => (
	<svg
		xmlns="http://www.w3.org/2000/svg"
		className={className}
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		strokeWidth="2"
		strokeLinecap="round"
		strokeLinejoin="round"
	>
		<polyline points="20 6 9 17 4 12"></polyline>
	</svg>
);

const AddressDisplay = ({ address, label }: { address: string, label: string }) => {
	const [copied, setCopied] = useState(false);

	const shortenedAddress = address
		? `${address.substring(0, 6)}...${address.substring(address.length - 4)}`
		: '';

	const copyToClipboard = () => {
		navigator.clipboard.writeText(address);
		setCopied(true);
		setTimeout(() => setCopied(false), 2000);
	};

	return (
		<div className="flex justify-between p-2 border-b border-gray-700 items-center flex-wrap">
			<span className="text-sm sm:text-base">{label}</span>
			<div className="flex items-center">
				<span className="font-medium text-xs sm:text-sm mr-2" title={address}>
					{shortenedAddress}
				</span>
				<button
					onClick={copyToClipboard}
					className="text-gray-400 hover:text-white p-1 rounded-md transition-colors duration-200"
					aria-label="Copy address"
				>
					{copied ? <CheckIcon /> : <CopyIcon />}
				</button>
			</div>
		</div>
	);
};
const MainAllowanceDisplay = ({ amount, symbol }: { amount: string, symbol: string }) => {
	const isUnlimited = amount === MAX_UINT256;

	return (
		<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
			<h3 className="text-lg sm:text-xl font-semibold mb-2 sm:mb-3">Current Allowance</h3>
			<div className="flex items-center justify-center mb-2 sm:mb-4">
				<span className="text-2xl sm:text-3xl font-bold">
					{formatNumber(amount)}
					{!isUnlimited && (
						<span className="text-gray-400 text-lg sm:text-xl ml-1">{symbol}</span>
					)}
				</span>
			</div>
		</div>
	);
};

export const useAllowanceERC20 = () => useAssistantToolUI({
	toolName: "allowance_erc20",
	render: (input) => {
		const [isExpanded, setIsExpanded] = useState(false);
		const data: Allowance = input.args.data;

		// 处理加载和错误状态
		// if (!data) return <div className="p-4 text-center">Loading allowance data...</div>;
		if (data && !data.success) return (
			<div className="p-4 text-center text-red-500">
				Failed to fetch allowance data. Please try again.
			</div>
		);

		// 计算格式化的授权金额
		// const allowanceAmount = data.allowance
		// 	? parseFloat(data.allowance) / Math.pow(10, data.decimals)
		// 	: 0;

		return data && (
			<div className="flex flex-col space-y-3 sm:space-y-6 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto mt-3 sm:mt-6">
				<h2 className="text-xl sm:text-2xl font-bold text-center">Token Allowance</h2>

				{/* 主要授权信息 */}
				<MainAllowanceDisplay
					amount={data.allowance}
					symbol={data.symbol}
				/>

				{/* 授权详情 */}
				<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
					<h3 className="text-lg sm:text-xl font-semibold mb-2">Allowance Details</h3>
					<div className="grid grid-cols-1 gap-2">
						<AddressDisplay address={data.owner_address} label="Owner" />
						<AddressDisplay address={data.spender_address} label="Spender" />
						<div className="flex justify-between p-2 border-b border-gray-700">
							<span className="text-sm sm:text-base">Chain ID</span>
							<span className="font-medium">{data.chainId}</span>
						</div>
					</div>
				</div>

				{/* 代币信息 */}
				<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
					<button
						className="w-full text-left text-lg sm:text-xl font-semibold mb-0 flex justify-between items-center"
						onClick={() => setIsExpanded(!isExpanded)}
					>
						<span>Token Info</span>
						<span>{isExpanded ? '▲' : '▼'}</span>
					</button>

					{isExpanded && (
						<div className="mt-2 bg-gray-800 p-2 rounded overflow-hidden">
							<AddressDisplay address={data.token_address} label="Token Address" />
							<div className="flex justify-between p-2">
								<span className="text-sm sm:text-base">Symbol</span>
								<span className="font-medium">{data.symbol}</span>
							</div>
							<div className="flex justify-between p-2">
								<span className="text-sm sm:text-base">Decimals</span>
								<span className="font-medium">{data.decimals}</span>
							</div>
						</div>
					)}
				</div>
			</div>
		);
	},
});