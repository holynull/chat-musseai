"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect, useMemo } from "react";

export type TransactionReceipt = {
	blockHash: string;
	blockNumber: string;
	contractAddress: string | null;
	cumulativeGasUsed: string;
	effectiveGasPrice: string;
	from: string;
	gasUsed: string;
	logs: any[];
	logsBloom: string;
	status: string;
	to: string;
	transactionHash: string;
	transactionIndex: string;
	type: string;
};

export type BlockReceipts = {
	result: TransactionReceipt[];
	method: string;
	network: string;
	network_type: string;
};

// Format address function
const formatAddress = (address: string): string => {
	if (!address) return "";
	return `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
};

// Format hash function
const formatHash = (hash: string): string => {
	if (!hash) return "";
	return `${hash.substring(0, 10)}...${hash.substring(hash.length - 8)}`;
};

// Converts hexadecimal string to decimal
const hexToDecimal = (hex: string): string => {
	if (!hex || !hex.startsWith("0x")) return hex;
	return parseInt(hex, 16).toString();
};

// Maximum number of transactions to display initially
const MAX_INITIAL_TRANSACTIONS = 5;

// React component for displaying block receipts
const BlockReceiptsDisplay = ({ data }: { data: BlockReceipts }) => {
	const [showAllTransactions, setShowAllTransactions] = useState(false);

	// Memoize the transaction list to avoid unnecessary re-renders
	const displayTransactions = useMemo(() => {
		return showAllTransactions
			? data.result
			: data.result.slice(0, MAX_INITIAL_TRANSACTIONS);
	}, [data.result, showAllTransactions]);

	// Calculate gas usage statistics
	const gasStats = useMemo(() => {
		if (!data.result.length) return { total: 0, average: 0, max: 0, min: 0 };

		const gasValues = data.result.map(tx => parseInt(tx.gasUsed, 16));
		return {
			total: gasValues.reduce((a, b) => a + b, 0),
			average: Math.round(gasValues.reduce((a, b) => a + b, 0) / gasValues.length),
			max: Math.max(...gasValues),
			min: Math.min(...gasValues)
		};
	}, [data.result]);

	return (
		<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full overflow-x-auto">
			<h2 className="text-xl sm:text-2xl font-bold text-center">Block Transaction Receipts</h2>

			<div className="text-sm sm:text-base">
				<div className="flex flex-wrap gap-2 sm:gap-4 justify-between mb-4 bg-gray-900 p-3 rounded-lg">
					<div>
						<span className="text-gray-400">Network: </span>
						<span className="font-medium">{data.network} ({data.network_type})</span>
					</div>
					<div>
						<span className="text-gray-400">Transactions: </span>
						<span className="font-medium">{data.result.length}</span>
					</div>
					<div>
						<span className="text-gray-400">Block Number: </span>
						<span className="font-medium">
							{hexToDecimal(data.result[0]?.blockNumber || "0x0")}
						</span>
					</div>
				</div>

				{/* Gas usage statistics */}
				<div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
					<div className="bg-gray-900 p-2 rounded-lg">
						<div className="text-xs text-gray-400">Total Gas Used</div>
						<div className="font-medium">{gasStats.total.toLocaleString()}</div>
					</div>
					<div className="bg-gray-900 p-2 rounded-lg">
						<div className="text-xs text-gray-400">Avg Gas / Tx</div>
						<div className="font-medium">{gasStats.average.toLocaleString()}</div>
					</div>
					<div className="bg-gray-900 p-2 rounded-lg">
						<div className="text-xs text-gray-400">Max Gas Used</div>
						<div className="font-medium">{gasStats.max.toLocaleString()}</div>
					</div>
					<div className="bg-gray-900 p-2 rounded-lg">
						<div className="text-xs text-gray-400">Min Gas Used</div>
						<div className="font-medium">{gasStats.min.toLocaleString()}</div>
					</div>
				</div>

				{/* Transaction list */}
				<div className="overflow-x-auto">
					<table className="min-w-full divide-y divide-gray-700">
						<thead>
							<tr>
								<th className="px-2 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Tx Hash</th>
								<th className="px-2 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">From</th>
								<th className="px-2 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">To</th>
								<th className="px-2 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Gas Used</th>
								<th className="px-2 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Status</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-gray-700">
							{displayTransactions.map((tx, index) => (
								<tr key={tx.transactionHash} className={index % 2 === 0 ? 'bg-gray-900' : 'bg-gray-800'}>
									<td className="px-2 py-2 whitespace-nowrap text-sm font-medium text-blue-400">
										{formatHash(tx.transactionHash)}
									</td>
									<td className="px-2 py-2 whitespace-nowrap text-sm text-gray-300">
										{formatAddress(tx.from)}
									</td>
									<td className="px-2 py-2 whitespace-nowrap text-sm text-gray-300">
										{formatAddress(tx.to)}
									</td>
									<td className="px-2 py-2 whitespace-nowrap text-sm text-gray-300">
										{parseInt(tx.gasUsed, 16).toLocaleString()}
									</td>
									<td className="px-2 py-2 whitespace-nowrap text-sm">
										<span className={`px-2 py-1 rounded-full text-xs font-medium ${tx.status === "0x1" ? "bg-green-900 text-green-300" : "bg-red-900 text-red-300"
											}`}>
											{tx.status === "0x1" ? "Success" : "Failed"}
										</span>
									</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>

				{/* Show more/less button */}
				{data.result.length > MAX_INITIAL_TRANSACTIONS && (
					<div className="mt-4 text-center">
						<button
							onClick={() => setShowAllTransactions(!showAllTransactions)}
							className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-md text-sm font-medium transition-colors"
						>
							{showAllTransactions
								? `Show Less (${MAX_INITIAL_TRANSACTIONS} of ${data.result.length})`
								: `Show All (${data.result.length} Transactions)`}
						</button>
					</div>
				)}
			</div>
		</div>
	);
};

export const useEthBlockReceipts = () => useAssistantToolUI({
	toolName: "eth_getBlockReceipts",
	render: (input) => {
		const data: BlockReceipts = input.args.data;

		// Early return if no data or empty result
		if (!data || !data.result || data.result.length === 0) {
			return (
				<div className="p-4 rounded-lg border border-gray-700 bg-gray-800 text-white">
					<p>No transaction receipts found for this block.</p>
				</div>
			);
		}

		return <BlockReceiptsDisplay data={data} />;
	},
});
