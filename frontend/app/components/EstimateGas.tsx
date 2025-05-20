"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useMemo } from "react";

export type EstimateGasData = {
	estimated_gas: number;
	gas_price: number;
	total_cost_wei: number;
	total_cost_eth: number;
	network: string;
	network_type: string;
};

// 格式化数字显示函数
const formatNumber = (value: number | string, decimals: number = 6): string => {
	const num = typeof value === 'string' ? parseFloat(value) : value;
	if (isNaN(num)) return String(value);

	const maxDecimals = Math.min(decimals, 8);
	return num.toLocaleString('en-US', {
		minimumFractionDigits: 2,
		maximumFractionDigits: maxDecimals
	});
};

// 格式化Wei为Gwei
const weiToGwei = (wei: number): number => {
	return wei / 1e9;
};

// 将Wei转换为人类可读的格式
const formatWei = (wei: number): string => {
	if (wei >= 1e18) {
		return `${formatNumber(wei / 1e18)} ETH`;
	} else if (wei >= 1e15) {
		return `${formatNumber(wei / 1e15)} Finney`;
	} else if (wei >= 1e12) {
		return `${formatNumber(wei / 1e12)} Szabo`;
	} else if (wei >= 1e9) {
		return `${formatNumber(wei / 1e9)} Gwei`;
	} else if (wei >= 1e6) {
		return `${formatNumber(wei / 1e6)} Mwei`;
	} else if (wei >= 1e3) {
		return `${formatNumber(wei / 1e3)} Kwei`;
	} else {
		return `${formatNumber(wei)} Wei`;
	}
};

// 创建一个独立的 React 组件来处理渲染
const EstimateGasDisplay = ({ data }: { data: EstimateGasData }) => {
	// 计算当前网络的本地货币符号
	const networkSymbol = useMemo(() => {
		// 基于网络返回对应的货币符号
		const networkSymbols: Record<string, string> = {
			'ethereum': 'ETH',
			'polygon': 'MATIC',
			'arbitrum': 'ETH',
			'optimism': 'ETH',
			'bsc': 'BNB',
			'avalanche': 'AVAX',
			'base': 'ETH',
			'zksync': 'ETH',
		};
		return networkSymbols[data.network.toLowerCase()] || 'ETH';
	}, [data.network]);

	// 计算 Gas 费用信息
	const gasPriceGwei = weiToGwei(data.gas_price);
	const totalCostGwei = weiToGwei(data.total_cost_wei);

	return (
		<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto">
			<h2 className="text-xl sm:text-2xl font-bold text-center">Gas Estimate</h2>
			<div className="text-xs sm:text-sm text-gray-400 text-center">
				{data.network.charAt(0).toUpperCase() + data.network.slice(1)} {data.network_type}
			</div>

			<div className="grid gap-3 sm:gap-4">
				{/* Gas Estimate Overview */}
				<div className="flex flex-col sm:flex-row justify-between items-center p-3 bg-gray-900 rounded-lg gap-3">
					<div className="w-full sm:w-auto text-center sm:text-left">
						<p className="text-xs sm:text-sm text-gray-400">Estimated Gas</p>
						<p className="text-lg sm:text-xl font-semibold text-white">
							{formatNumber(data.estimated_gas)}
							<span className="text-gray-400 text-sm sm:text-base ml-1">units</span>
						</p>
					</div>
					<div className="text-blue-500 transform rotate-90 sm:rotate-0 transition-transform duration-200 hover:scale-110">
						<svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 sm:h-6 sm:w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
						</svg>
					</div>
					<div className="w-full sm:w-auto text-center sm:text-left">
						<p className="text-xs sm:text-sm text-gray-400">Total Cost</p>
						<p className="text-lg sm:text-xl font-semibold text-white">
							{formatNumber(data.total_cost_eth, 8)}
							<span className="text-gray-400 text-sm sm:text-base ml-1">{networkSymbol}</span>
						</p>
					</div>
				</div>

				{/* Transaction Details */}
				<div className="mt-2 sm:mt-4">
					<h4 className="text-xs sm:text-sm font-medium text-white mb-2">Gas Details</h4>
					<div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs sm:text-sm">
						<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
							<span className="text-gray-400">Gas Price</span>
							<span className="font-medium text-white">
								{formatNumber(gasPriceGwei)} Gwei
							</span>
						</div>
						<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
							<span className="text-gray-400">Gas Price (Wei)</span>
							<span className="font-medium text-white">{formatWei(data.gas_price)}</span>
						</div>
						<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
							<span className="text-gray-400">Total Gas Cost (Wei)</span>
							<span className="font-medium text-white">{formatWei(data.total_cost_wei)}</span>
						</div>
						<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
							<span className="text-gray-400">Total Gas Cost (Gwei)</span>
							<span className="font-medium text-white">{formatNumber(totalCostGwei)} Gwei</span>
						</div>
					</div>
				</div>

				{/* Network Information */}
				<div className="mt-1 sm:mt-2">
					<h4 className="text-xs sm:text-sm font-medium text-white mb-2">Network Info</h4>
					<div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs sm:text-sm">
						<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
							<span className="text-gray-400">Network</span>
							<span className="font-medium text-white">
								{data.network.charAt(0).toUpperCase() + data.network.slice(1)}
							</span>
						</div>
						<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
							<span className="text-gray-400">Network Type</span>
							<span className="font-medium text-white">
								{data.network_type.charAt(0).toUpperCase() + data.network_type.slice(1)}
							</span>
						</div>
						<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
							<span className="text-gray-400">Native Currency</span>
							<span className="font-medium text-white">{networkSymbol}</span>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};

export const useEstimateGas = () => useAssistantToolUI({
	toolName: "estimate_gas",
	render: (input) => {
		const data: EstimateGasData = input.args.data;
		if (!data) return null;
		return <EstimateGasDisplay data={data} />;
	},
});
