"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { FC, useMemo } from "react";

export type FeeHistoryData = {
	oldestBlock: string;
	baseFeePerGas: string[];
	gasUsedRatio: number[];
	reward?: string[][];
	network: string;
	network_type: string;
};

interface FeeHistoryDisplayProps {
	data: FeeHistoryData;
	networkInfo: {
		network: string;
		network_type: string;
	};
}

const formatGasPrice = (value: string): string => {
	// 将十六进制转换为十进制，并从Wei转换为Gwei
	const weiValue = parseInt(value, 16);
	const gweiValue = weiValue / 1e9;
	return gweiValue.toFixed(2);
};

const formatBlockNumber = (value: string): string => {
	// 将十六进制转换为十进制
	return parseInt(value, 16).toString();
};

const FeeHistoryDisplay: FC<FeeHistoryDisplayProps> = ({ data, networkInfo }) => {
	// 记录当前区块的十进制表示
	const oldestBlockNumber = useMemo(() => formatBlockNumber(data.oldestBlock), [data.oldestBlock]);

	// 计算区块序列
	const blockNumbers = useMemo(() => {
		const oldest = parseInt(data.oldestBlock, 16);
		return Array.from({ length: data.baseFeePerGas.length }, (_, i) => oldest + i);
	}, [data.oldestBlock, data.baseFeePerGas.length]);

	// 格式化基本费用数据
	const formattedBaseFees = useMemo(() =>
		data.baseFeePerGas.map(fee => formatGasPrice(fee)),
		[data.baseFeePerGas]
	);

	// 格式化奖励数据（如果存在）
	const formattedRewards = useMemo(() => {
		if (!data.reward || data.reward.length === 0) return [];

		return data.reward.map(rewardTiers =>
			rewardTiers.map(reward => formatGasPrice(reward))
		);
	}, [data.reward]);

	return (
		<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto">
			<h2 className="text-xl sm:text-2xl font-bold text-center">
				Gas Fee History - {networkInfo.network.charAt(0).toUpperCase() + networkInfo.network.slice(1)} {networkInfo.network_type}
			</h2>

			<div className="text-sm text-gray-400 text-center">
				Starting from block #{oldestBlockNumber}
			</div>

			<div className="mt-4 overflow-x-auto">
				<table className="min-w-full divide-y divide-gray-700">
					<thead className="bg-gray-700">
						<tr>
							<th className="px-4 py-2 text-left text-xs font-medium text-gray-300 tracking-wider">Block #</th>
							<th className="px-4 py-2 text-left text-xs font-medium text-gray-300 tracking-wider">Base Fee (Gwei)</th>
							<th className="px-4 py-2 text-left text-xs font-medium text-gray-300 tracking-wider">Gas Used Ratio</th>
							{data.reward && data.reward.length > 0 && (
								<th className="px-4 py-2 text-left text-xs font-medium text-gray-300 tracking-wider">Priority Fee (Gwei)</th>
							)}
						</tr>
					</thead>
					<tbody className="bg-gray-800 divide-y divide-gray-700">
						{blockNumbers.map((blockNum, index) => (
							<tr key={blockNum} className={index % 2 === 0 ? "bg-gray-900" : ""}>
								<td className="px-4 py-2 whitespace-nowrap text-sm text-gray-200">{blockNum}</td>
								<td className="px-4 py-2 whitespace-nowrap text-sm text-blue-400">{formattedBaseFees[index]}</td>
								<td className="px-4 py-2 whitespace-nowrap text-sm text-gray-200">
									{data.gasUsedRatio[index] ? (data.gasUsedRatio[index] * 100).toFixed(2) + '%' : 'N/A'}
								</td>
								{data.reward && data.reward.length > 0 && (
									<td className="px-4 py-2 whitespace-nowrap text-sm text-green-400">
										{index < formattedRewards.length && formattedRewards[index].length > 0
											? formattedRewards[index].join(' / ')
											: 'N/A'}
									</td>
								)}
							</tr>
						))}
					</tbody>
				</table>
			</div>

			<div className="text-xs mt-2 text-gray-400">
				<div><span className="font-semibold">Base Fee:</span> Minimum gas price required for inclusion in a block</div>
				<div><span className="font-semibold">Gas Used Ratio:</span> Percentage of gas used relative to the gas limit</div>
				{data.reward && data.reward.length > 0 && (
					<div><span className="font-semibold">Priority Fee:</span> Additional fee paid to miners/validators (shown as percentiles if multiple)</div>
				)}
			</div>
		</div>
	);
};

export const useEthFeeHistory = () => useAssistantToolUI({
	toolName: "eth_feeHistory",
	render: (input) => {
		const data: FeeHistoryData = input.args.data?.result;
		const networkInfo = {
			network: input.args.data?.network,
			network_type: input.args.data?.network_type
		};

		if (!data) return null;

		return <FeeHistoryDisplay data={data} networkInfo={networkInfo} />;
	},
});
