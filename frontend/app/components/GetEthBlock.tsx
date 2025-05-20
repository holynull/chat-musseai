"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useMemo } from "react";

export type EthBlockData = {
	basic_info: {
		number: number;
		timestamp: number;
		tx_count: number;
	};
	gas_info: {
		used_percentage: number;
		base_fee_gwei: number | null;
		gas_used: number;
		gas_limit: number;
	};
	miner: string | null;
	network_info: {
		network: string;
		network_type: string;
		explorer_url: string;
	};
	transactions: {
		preview: string[];
		total: number;
	};
	consensus_info?: {
		extra_data_length: number;
		is_poa: boolean;
	};
};

// Helper functions
const formatTimestamp = (timestamp: number): string => {
	return new Date(timestamp * 1000).toLocaleString();
};

const truncateHash = (hash: string, length = 6): string => {
	if (!hash) return '';
	return `${hash.substring(0, length)}...${hash.substring(hash.length - length)}`;
};

const formatNumber = (num: number): string => {
	return new Intl.NumberFormat().format(num);
};

// 错误显示组件
const ErrorDisplay = ({ message }: { message: string }) => (
	<div className="p-4 bg-red-900/50 border border-red-700 rounded-lg text-white">
		<h3 className="text-lg font-semibold mb-2">Error</h3>
		<p className="text-sm">{message}</p>
	</div>
);

// 主显示组件
const EthBlockDisplay = ({ data }: { data: EthBlockData }) => {
	const transactionPreviews = useMemo(() => {
		return data.transactions.preview.map((hash, index) => (
			<div key={index} className="p-2 hover:bg-gray-700 transition-colors duration-150">
				<a
					href={`${data.network_info.explorer_url.split('/block')[0]}/tx/${hash}`}
					target="_blank"
					rel="noopener noreferrer"
					className="text-blue-400 hover:text-blue-300 text-xs"
				>
					{truncateHash(hash)}
				</a>
			</div>
		));
	}, [data.transactions.preview, data.network_info.explorer_url]);

	return (
		<div className="flex flex-col space-y-3 p-3 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-xl mx-auto">
			{/* Header */}
			<div className="text-center">
				<h2 className="text-xl font-bold">Block #{data.basic_info.number}</h2>
				<div className="text-xs text-gray-400">
					{data.network_info.network_type} {data.network_info.network}
					{data.consensus_info?.is_poa && " (PoA)"}
				</div>
			</div>

			{/* Stats Grid */}
			<div className="grid grid-cols-2 gap-2 text-sm">
				<div className="bg-gray-900 p-2 rounded">
					<div className="text-gray-400 text-xs">Transactions</div>
					<div className="font-medium">{data.basic_info.tx_count}</div>
				</div>
				<div className="bg-gray-900 p-2 rounded">
					<div className="text-gray-400 text-xs">Gas Used</div>
					<div className="font-medium">
						{data.gas_info.used_percentage}%
						<span className="text-xs text-gray-400 ml-1">
							({formatNumber(data.gas_info.gas_used)})
						</span>
					</div>
				</div>
				<div className="bg-gray-900 p-2 rounded">
					<div className="text-gray-400 text-xs">Base Fee</div>
					<div className="font-medium">
						{data.gas_info.base_fee_gwei ? `${data.gas_info.base_fee_gwei} Gwei` : 'N/A'}
					</div>
				</div>
				<div className="bg-gray-900 p-2 rounded">
					<div className="text-gray-400 text-xs">Time</div>
					<div className="font-medium">{formatTimestamp(data.basic_info.timestamp)}</div>
				</div>
			</div>

			{/* Miner */}
			{data.miner && (
				<div className="bg-gray-900 p-2 rounded text-sm">
					<div className="text-gray-400 text-xs">Miner</div>
					<div className="font-mono text-xs truncate" title={data.miner}>
						{data.miner}
					</div>
				</div>
			)}

			{/* Consensus Info */}
			{data.consensus_info && (
				<div className="bg-gray-900 p-2 rounded text-xs">
					<div className="text-gray-400">Consensus</div>
					<div className="mt-1">
						<span className="text-gray-300">Type:</span> PoA
						<span className="ml-2 text-gray-300">Extra Data Size:</span> {data.consensus_info.extra_data_length} bytes
					</div>
				</div>
			)}

			{/* Transaction Preview */}
			{data.transactions.preview.length > 0 && (
				<div className="bg-gray-900 rounded">
					<div className="text-xs font-medium p-2 border-b border-gray-700">
						Recent Transactions
					</div>
					<div className="divide-y divide-gray-700">
						{transactionPreviews}
					</div>
					{data.transactions.total > data.transactions.preview.length && (
						<div className="p-2 text-center border-t border-gray-700">
							<a
								href={data.network_info.explorer_url}
								target="_blank"
								rel="noopener noreferrer"
								className="text-blue-400 hover:text-blue-300 text-xs"
							>
								View all {data.transactions.total} transactions
							</a>
						</div>
					)}
				</div>
			)}

			{/* Explorer Link */}
			<a
				href={data.network_info.explorer_url}
				target="_blank"
				rel="noopener noreferrer"
				className="text-center text-blue-400 hover:text-blue-300 text-xs"
			>
				View full block details
			</a>
		</div>
	);
};

// 主Hook
export const useGetEthBlock = () => useAssistantToolUI({
	toolName: "get_eth_block",
	render: (input) => {
		// 检查是否是错误消息
		if (typeof input.args.data === 'string') {
			return <ErrorDisplay message={input.args.data} />;
		}

		const data: EthBlockData = input.args.data;
		if (!data || !data.basic_info) return null;

		return <EthBlockDisplay data={data} />;
	},
});
