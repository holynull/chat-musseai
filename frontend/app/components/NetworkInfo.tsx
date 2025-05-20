"use client";
import { useAssistantToolUI } from "@assistant-ui/react";

export type NetworkInfo = {
	chain_id: number;
	name: string;
	native_currency: string;
	network_version: string;
	latest_block: number;
	gas_price: string;
	is_listening: boolean;
	peer_count: number;
	network: string;
	network_type: string;
};

// 格式化gas价格为可读形式
const formatGasPrice = (gasPriceWei: string): string => {
	const gasPrice = parseInt(gasPriceWei);
	if (isNaN(gasPrice)) return gasPriceWei;

	// 转换为Gwei
	const gasPriceGwei = gasPrice / 1e9;
	return `${gasPriceGwei.toLocaleString('en-US', { maximumFractionDigits: 2 })} Gwei`;
};

// 将渲染逻辑抽取为一个独立的React组件
const NetworkInfoDisplay = ({ data }: { data: NetworkInfo }) => {
	if (!data) return null;

	const formattedGasPrice = formatGasPrice(data.gas_price.toString());

	return (
		<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto">
			<h2 className="text-xl sm:text-2xl font-bold text-center">{data.name} Network Info</h2>

			<div className="grid gap-3 sm:gap-4">
				{/* 网络基本信息 */}
				<div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs sm:text-sm">
					<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
						<span className="text-gray-400">Network</span>
						<span className="font-medium text-white">{data.network}</span>
					</div>
					<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
						<span className="text-gray-400">Network Type</span>
						<span className="font-medium text-white">{data.network_type}</span>
					</div>
					<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
						<span className="text-gray-400">Chain ID</span>
						<span className="font-medium text-white">{data.chain_id}</span>
					</div>
					<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
						<span className="text-gray-400">Native Currency</span>
						<span className="font-medium text-white">{data.native_currency}</span>
					</div>
				</div>

				{/* 网络状态信息 */}
				<div className="mt-2 sm:mt-4">
					<h4 className="text-xs sm:text-sm font-medium text-white mb-2">Network Status</h4>
					<div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs sm:text-sm">
						<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
							<span className="text-gray-400">Latest Block</span>
							<span className="font-medium text-white">{data.latest_block.toLocaleString()}</span>
						</div>
						<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
							<span className="text-gray-400">Gas Price</span>
							<span className="font-medium text-white">{formattedGasPrice}</span>
						</div>
						<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
							<span className="text-gray-400">Network Version</span>
							<span className="font-medium text-white">{data.network_version}</span>
						</div>
						<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
							<span className="text-gray-400">Connection Status</span>
							<span className={`font-medium ${data.is_listening ? "text-green-400" : "text-red-400"}`}>
								{data.is_listening ? "Connected" : "Disconnected"}
							</span>
						</div>
						<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
							<span className="text-gray-400">Peer Count</span>
							<span className="font-medium text-white">{data.peer_count}</span>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};

export const useNetworkInfo = () => useAssistantToolUI({
	toolName: "get_network_info",
	render: (input) => <NetworkInfoDisplay data={input.args.data} />,
});
