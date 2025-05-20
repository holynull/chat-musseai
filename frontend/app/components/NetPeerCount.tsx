"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useMemo } from "react";

export type NetPeerCountData = {
	result: string;
	method: string;
	network: string;
	network_type: string;
};

// 创建独立的展示组件
const NetPeerCountDisplay = ({ data }: { data: NetPeerCountData }) => {
	// 将十六进制结果转换为十进制
	const peerCount = useMemo(() => {
		if (!data.result) return 0;
		return parseInt(data.result, 16);
	}, [data.result]);

	// 准备网络显示信息
	const networkInfo = useMemo(() => {
		return {
			network: data.network.charAt(0).toUpperCase() + data.network.slice(1),
			networkType: data.network_type.charAt(0).toUpperCase() + data.network_type.slice(1)
		};
	}, [data.network, data.network_type]);

	// 基于连接数量确定连接状态
	const connectionStatus = useMemo(() => {
		if (peerCount === 0) return "No peers connected";
		if (peerCount < 3) return "Low peer count";
		if (peerCount < 10) return "Moderate peer count";
		return "Healthy peer count";
	}, [peerCount]);

	// 基于连接状态确定颜色
	const statusColor = useMemo(() => {
		if (peerCount === 0) return "text-red-500";
		if (peerCount < 3) return "text-yellow-500";
		if (peerCount < 10) return "text-blue-500";
		return "text-green-500";
	}, [peerCount]);

	return (
		<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-xl mx-auto">
			<h2 className="text-xl sm:text-2xl font-bold text-center">Network Peer Count</h2>

			<div className="grid gap-3 sm:gap-4">
				{/* Network Information */}
				<div className="flex justify-between p-2 bg-gray-900 rounded-lg">
					<span className="text-gray-400">Network</span>
					<span className="font-medium text-white">
						{networkInfo.network} {networkInfo.networkType}
					</span>
				</div>

				{/* Peer Count */}
				<div className="flex flex-col items-center p-4 bg-gray-900 rounded-lg">
					<span className="text-gray-400 text-sm">Connected Peers</span>
					<span className="text-3xl font-bold mt-2">{peerCount}</span>
					<span className={`mt-1 ${statusColor} text-sm font-medium`}>
						{connectionStatus}
					</span>
				</div>

				{/* Additional Information */}
				<div className="text-xs sm:text-sm bg-gray-900 p-3 rounded-lg text-gray-300">
					<p>
						Peer count represents the number of nodes connected to the {networkInfo.network} {networkInfo.networkType} network.
						A higher peer count generally indicates better network connectivity and health.
					</p>
				</div>
			</div>
		</div>
	);
};

export const useNetPeerCount = () => useAssistantToolUI({
	toolName: "net_peerCount",
	render: (input) => {
		const data: NetPeerCountData = input.args.data;
		if (!data) return null;
		return <NetPeerCountDisplay data={data} />;
	},
});
