"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { FC, useMemo } from "react";

export type EthBalanceData = {
	address: string;
	balance_wei: string;
	balance: number;
	symbol: string;
	network: string;
	network_type: string;
};

// Format balance for display
const formatBalance = (balance: number): string => {
	if (balance === undefined || balance === null || isNaN(balance)) {
		return "0.00";
	}

	// Different format for small and large numbers
	if (balance < 0.000001 && balance > 0) {
		return balance.toExponential(6);
	}

	return balance.toLocaleString('en-US', {
		minimumFractionDigits: 2,
		maximumFractionDigits: 6
	});
};

// Format address for display
const formatAddress = (address: string, length = 6): string => {
	if (!address) return '';
	if (address.length <= length * 2) return address;
	return `${address.substring(0, length)}...${address.substring(address.length - length)}`;
};

interface EthBalanceDisplayProps {
	data: EthBalanceData;
}

// 将render函数改为独立的React组件
const EthBalanceDisplay: FC<EthBalanceDisplayProps> = ({ data }) => {
	// 在组件开始时无条件调用所有Hooks
	const formattedNetwork = useMemo(() => {
		if (!data) return '';

		const network = data.network.charAt(0).toUpperCase() + data.network.slice(1);
		const networkType = data.network_type === "mainnet"
			? "Mainnet"
			: data.network_type.charAt(0).toUpperCase() + data.network_type.slice(1);
		return `${network} ${networkType}`;
	}, [data]);

	const formattedBalance = useMemo(() => {
		if (!data) return '0.00';

		return formatBalance(data.balance);
	}, [data]);

	// 只在渲染部分使用条件判断
	if (!data) return null;

	return (
		<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-2xl mx-auto">
			<h2 className="text-xl sm:text-2xl font-bold text-center">{data.symbol} Balance</h2>

			{/* Main balance display */}
			<div className="flex flex-col sm:flex-row justify-between items-center p-4 bg-gray-900 rounded-lg gap-4">
				<div className="w-full sm:w-auto text-center sm:text-left">
					<p className="text-xs sm:text-sm text-gray-400">Balance</p>
					<p className="text-2xl sm:text-3xl font-semibold text-white">
						{formattedBalance}
						<span className="text-gray-400 text-base sm:text-lg ml-2">{data.symbol}</span>
					</p>
				</div>
				<div className="bg-gray-700 p-2 rounded-md">
					<p className="text-xs text-gray-300">{formattedNetwork}</p>
				</div>
			</div>

			{/* Address details */}
			<div className="mt-2">
				<h4 className="text-xs sm:text-sm font-medium text-white mb-2">Address Details</h4>
				<div className="flex flex-col space-y-2">
					<div className="flex justify-between items-center p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
						<span className="text-gray-400 text-sm">Address</span>
						<div className="flex items-center">
							<span className="font-medium text-white text-sm sm:hidden">{formatAddress(data.address)}</span>
							<span className="font-medium text-white text-sm hidden sm:inline">{data.address}</span>
							<button
								className="ml-2 text-blue-400 hover:text-blue-300 text-xs"
								onClick={() => navigator.clipboard.writeText(data.address)}
							>
								Copy
							</button>
						</div>
					</div>

					<div className="flex justify-between items-center p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
						<span className="text-gray-400 text-sm">Raw Balance (Wei)</span>
						<span className="font-medium text-white text-sm overflow-hidden text-ellipsis max-w-[180px] sm:max-w-[300px]">
							{data.balance_wei}
						</span>
					</div>
				</div>
			</div>

			{/* Link to block explorer */}
			<div className="text-center mt-2">
				<a
					href={`https://${data.network_type !== 'mainnet' ? `${data.network_type}.` : ''}${data.network === 'ethereum' ? 'etherscan.io' : `${data.network}scan.com`}/address/${data.address}`}
					target="_blank"
					rel="noopener noreferrer"
					className="text-blue-400 hover:text-blue-300 text-sm"
				>
					View on Block Explorer
				</a>
			</div>
		</div>
	);
};

export const useGetEthBalance = () => useAssistantToolUI({
	toolName: "get_eth_balance",
	render: (input) => <EthBalanceDisplay data={input.args.data} />,
});
