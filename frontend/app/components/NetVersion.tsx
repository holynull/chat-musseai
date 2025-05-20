"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect } from "react";

export type NetworkVersionInfo = {
	result: string;
	method: string;
	network: string;
	network_type: string;
};

// 创建网络名称转换和美化的辅助函数
const formatNetworkName = (network: string, networkType: string): string => {
	const networkName = network.charAt(0).toUpperCase() + network.slice(1);
	const typeName = networkType === "mainnet" ? "Mainnet" : networkType.charAt(0).toUpperCase() + networkType.slice(1);
	return `${networkName} ${typeName}`;
};

// 获取网络图标URL的辅助函数
const getNetworkIconUrl = (network: string): string => {
	const networkIcons: Record<string, string> = {
		ethereum: "https://cryptologos.cc/logos/ethereum-eth-logo.png",
		polygon: "https://cryptologos.cc/logos/polygon-matic-logo.png",
		arbitrum: "https://cryptologos.cc/logos/arbitrum-arb-logo.png",
		optimism: "https://cryptologos.cc/logos/optimism-op-logo.png",
		avalanche: "https://cryptologos.cc/logos/avalanche-avax-logo.png",
		bsc: "https://cryptologos.cc/logos/bnb-bnb-logo.png",
		base: "https://cryptologos.cc/logos/base-logo.png",
		zksync: "https://cryptologos.cc/logos/zksync-logo.png",
		// 可以添加更多网络的图标
	};

	return networkIcons[network.toLowerCase()] ||
		"https://cryptologos.cc/logos/ethereum-eth-logo.png"; // 默认使用以太坊图标
};

export const useNetVersion = () => useAssistantToolUI({
	toolName: "net_version",
	render: (input) => {
		const data: NetworkVersionInfo = input.args.data;

		if (!data || !data.result) return null;

		// 获取网络ID
		const networkId = data.result;
		const networkName = formatNetworkName(data.network, data.network_type);
		const networkIcon = getNetworkIconUrl(data.network);

		return (
			<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto">
				<h2 className="text-xl sm:text-2xl font-bold text-center">Network Information</h2>

				<div className="flex items-center justify-center mt-1 sm:mt-2">
					<img
						src={networkIcon}
						alt={`${data.network} logo`}
						width={24}
						height={24}
						className="rounded-full w-6 h-6 sm:w-8 sm:h-8 mr-2"
					/>
					<span className="text-sm sm:text-base text-white">{networkName}</span>
				</div>

				<div className="grid gap-3 sm:gap-4">
					{/* 网络详细信息 */}
					<div className="flex flex-col sm:flex-row justify-between items-center p-3 bg-gray-900 rounded-lg gap-3">
						<div className="w-full sm:w-auto text-center sm:text-left">
							<p className="text-xs sm:text-sm text-gray-400">Network ID</p>
							<p className="text-lg sm:text-xl font-semibold text-white">
								{networkId}
							</p>
						</div>
					</div>

					{/* 其他网络信息 */}
					<div className="mt-2 sm:mt-4">
						<h4 className="text-xs sm:text-sm font-medium text-white mb-2">Network Details</h4>
						<div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs sm:text-sm">
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Network</span>
								<span className="font-medium text-white">{data.network}</span>
							</div>
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Type</span>
								<span className="font-medium text-white">{data.network_type}</span>
							</div>
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Method</span>
								<span className="font-medium text-white">{data.method}</span>
							</div>
						</div>
					</div>
				</div>
			</div>
		);
	},
});
