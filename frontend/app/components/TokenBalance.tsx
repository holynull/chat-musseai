"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { FC, useMemo } from "react";

export type TokenBalanceData = {
	token_address: string;
	wallet_address: string;
	balance_wei: string;
	balance: number;
	decimals: number;
	symbol: string;
	name: string;
	network: string;
	network_type: string;
};

// Format number function
const formatNumber = (value: number, decimals: number = 6): string => {
	if (isNaN(value)) return value.toString();

	const maxDecimals = Math.min(decimals, 8);

	return value.toLocaleString('en-US', {
		minimumFractionDigits: 2,
		maximumFractionDigits: maxDecimals
	});
};

// Truncate address for display
const truncateAddress = (address: string, length = 8) => {
	if (!address) return '';
	if (address.length <= length * 2) return address;
	return `${address.substring(0, length)}...${address.substring(address.length - length)}`;
};

interface TokenBalanceDisplayProps {
	data: TokenBalanceData;
}

const TokenBalanceDisplay: FC<TokenBalanceDisplayProps> = ({ data }) => {
	// 使用useMemo优化网络名称的格式化
	const networkDisplay = useMemo(() => {
		return `${data.network.charAt(0).toUpperCase() + data.network.slice(1)} ${data.network_type !== 'mainnet' ? data.network_type : ''
			}`.trim();
	}, [data.network, data.network_type]);

	return (
		<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto">
			<h2 className="text-xl sm:text-2xl font-bold text-center">Token Balance</h2>

			{/* Main Balance Info */}
			<div className="flex flex-col sm:flex-row justify-between items-center p-3 bg-gray-900 rounded-lg gap-3">
				<div className="w-full sm:w-auto text-center sm:text-left">
					<p className="text-xs sm:text-sm text-gray-400">Token</p>
					<p className="text-lg sm:text-xl font-semibold text-white">
						{data.name}
						<span className="text-gray-400 text-sm sm:text-base ml-1">({data.symbol})</span>
					</p>
				</div>
				<div className="bg-blue-500/20 text-blue-400 py-1 px-3 rounded-full text-xs">
					{networkDisplay}
				</div>
				<div className="w-full sm:w-auto text-center sm:text-left">
					<p className="text-xs sm:text-sm text-gray-400">Balance</p>
					<p className="text-lg sm:text-xl font-semibold text-white">
						{formatNumber(data.balance, data.decimals)}
						<span className="text-gray-400 text-sm sm:text-base ml-1">{data.symbol}</span>
					</p>
				</div>
			</div>

			{/* Additional Details */}
			<div className="mt-2 sm:mt-4">
				<h4 className="text-xs sm:text-sm font-medium text-white mb-2">Token Details</h4>
				<div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs sm:text-sm">
					<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
						<span className="text-gray-400">Wallet Address</span>
						<span className="font-medium text-white truncate max-w-[150px] sm:max-w-none">
							<span className="hidden sm:inline">{data.wallet_address}</span>
							<span className="inline sm:hidden">{truncateAddress(data.wallet_address)}</span>
						</span>
					</div>
					<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
						<span className="text-gray-400">Token Address</span>
						<span className="font-medium text-white truncate max-w-[150px] sm:max-w-none">
							<span className="hidden sm:inline">{data.token_address}</span>
							<span className="inline sm:hidden">{truncateAddress(data.token_address)}</span>
						</span>
					</div>
					<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
						<span className="text-gray-400">Decimals</span>
						<span className="font-medium text-white">{data.decimals}</span>
					</div>
					<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
						<span className="text-gray-400">Raw Balance (Wei)</span>
						<span className="font-medium text-white truncate max-w-[150px] sm:max-w-none">
							{data.balance_wei}
						</span>
					</div>
				</div>
			</div>

			{/* Network Information */}
			<div className="mt-1 sm:mt-2">
				<h4 className="text-xs sm:text-sm font-medium text-white mb-2">Network Info</h4>
				<div className="grid grid-cols-1 gap-2 text-xs sm:text-sm">
					<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
						<span className="text-gray-400">Network</span>
						<span className="font-medium text-white">{data.network}</span>
					</div>
					<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
						<span className="text-gray-400">Network Type</span>
						<span className="font-medium text-white">{data.network_type}</span>
					</div>
				</div>
			</div>
		</div>
	);
};

export const useTokenBalance = () => useAssistantToolUI({
	toolName: "get_token_balance",
	render: (input) => {
		const data: TokenBalanceData = input.args.data;
		if (!data || typeof data === 'string') return null;
		return <TokenBalanceDisplay data={data} />;
	},
});
