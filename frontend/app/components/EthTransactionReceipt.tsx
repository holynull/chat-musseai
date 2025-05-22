"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect } from "react";
interface NetworkExplorer {
	explorer: string;
}

interface NetworkType {
	mainnet: NetworkExplorer;
	goerli?: NetworkExplorer;
	sepolia?: NetworkExplorer;
	mumbai?: NetworkExplorer;
	testnet?: NetworkExplorer;
}

interface NetworkConfig {
	[key: string]: NetworkType;
}

// 修改 NETWORK_CONFIG 的定义
const NETWORK_CONFIG: NetworkConfig = {
	"ethereum": {
		"mainnet": {
			"explorer": "https://etherscan.io",
		},
		"goerli": {
			"explorer": "https://goerli.etherscan.io",
		},
		"sepolia": {
			"explorer": "https://sepolia.etherscan.io",
		},
	},
	"polygon": {
		"mainnet": {
			"explorer": "https://polygonscan.com",
		},
		"mumbai": {
			"explorer": "https://mumbai.polygonscan.com",
		},
	},
	"bsc": {
		"mainnet": {
			"explorer": "https://bscscan.com",
		},
		"testnet": {
			"explorer": "https://testnet.bscscan.com",
		},
	},
	"arbitrum": {
		"mainnet": {
			"explorer": "https://arbiscan.io",
		},
		"testnet": {
			"explorer": "https://testnet.arbiscan.io",
		},
	},
	"optimism": {
		"mainnet": {
			"explorer": "https://optimistic.etherscan.io",
		},
		"testnet": {
			"explorer": "https://goerli-optimism.etherscan.io",
		},
	},
	"avalanche": {
		"mainnet": {
			"explorer": "https://snowtrace.io",
		},
		"testnet": {
			"explorer": "https://testnet.snowtrace.io",
		},
	},
};

// 添加一个安全的获取explorer URL的函数
const getExplorerUrl = (network: string, networkType: string, txHash: string): string => {
	const defaultExplorer = "https://etherscan.io";

	try {
		const networkLower = network.toLowerCase();
		const networkTypeLower = networkType.toLowerCase();

		const explorerUrl = NETWORK_CONFIG[networkLower]?.[networkTypeLower as keyof NetworkType]?.explorer;
		return explorerUrl ? `${explorerUrl}/tx/${txHash}` : `${defaultExplorer}/tx/${txHash}`;
	} catch (error) {
		console.error('Error getting explorer URL:', error);
		return `${defaultExplorer}/tx/${txHash}`;
	}
};

export type TransactionReceipt = {
	blockHash: string;
	blockNumber: string;
	contractAddress: string | null;
	cumulativeGasUsed: string;
	effectiveGasPrice: string;
	from: string;
	gasUsed: string;
	logs: Array<{
		address: string;
		topics: string[];
		data: string;
		blockNumber: string;
		transactionHash: string;
		transactionIndex: string;
		blockHash: string;
		logIndex: string;
		removed: boolean;
	}>;
	logsBloom: string;
	status: string;
	to: string;
	transactionHash: string;
	transactionIndex: string;
	type: string;
	network: string;
	network_type: string;
};

// Format address function
const formatAddress = (address: string, chars: number = 6): string => {
	if (!address) return '';
	if (address.length <= chars * 2) return address;
	return `${address.substring(0, chars)}...${address.substring(address.length - chars)}`;
};

// Format hex number to decimal
const formatHexToDecimal = (hex: string): string => {
	if (!hex || !hex.startsWith('0x')) return hex;
	return parseInt(hex, 16).toString();
};

// Format gas
const formatGas = (gas: string): string => {
	const gasNumber = parseInt(gas, 16);
	return gasNumber.toLocaleString();
};

// Format status
const formatStatus = (status: string): { text: string, color: string } => {
	if (status === '0x1') {
		return { text: 'Success', color: 'text-green-500' };
	} else if (status === '0x0') {
		return { text: 'Failed', color: 'text-red-500' };
	}
	return { text: status, color: 'text-gray-500' };
};

export const useEthTransactionReceipt = () => useAssistantToolUI({
	toolName: "eth_getTransactionReceipt",
	render: (input) => {
		const data: TransactionReceipt = input.args.data?.result;

		if (!data) return null;

		const statusInfo = formatStatus(data.status);
		const explorerUrl = getExplorerUrl(data.network, data.network_type, data.transactionHash);

		// Simplified logs display
		const logsPreview = data.logs.slice(0, 3);
		const hasMoreLogs = data.logs.length > 3;

		return (
			<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto">
				<h2 className="text-xl sm:text-2xl font-bold text-center">Transaction Receipt</h2>
				<div className="flex items-center justify-center">
					<span className={`px-3 py-1 rounded-full text-sm font-medium ${statusInfo.color} bg-opacity-20 border border-current`}>
						{statusInfo.text}
					</span>
				</div>

				{/* Main transaction information */}
				<div className="grid gap-3 sm:gap-4">
					<div className="flex flex-col sm:flex-row justify-between items-center p-3 bg-gray-900 rounded-lg gap-3">
						<div className="w-full sm:w-auto text-center sm:text-left">
							<p className="text-xs sm:text-sm text-gray-400">Transaction Hash</p>
							<p className="text-sm sm:text-base font-mono break-all">
								{data.transactionHash}
							</p>
						</div>
					</div>

					{/* Transaction details */}
					<div className="mt-2 sm:mt-4">
						<h4 className="text-xs sm:text-sm font-medium text-white mb-2">Transaction Details</h4>
						<div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs sm:text-sm">
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Block</span>
								<span className="font-medium text-white">
									{formatHexToDecimal(data.blockNumber)}
								</span>
							</div>
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">From</span>
								<span className="font-medium text-white font-mono">
									<span className="hidden sm:inline">{data.from}</span>
									<span className="inline sm:hidden">{formatAddress(data.from)}</span>
								</span>
							</div>
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">To</span>
								<span className="font-medium text-white font-mono">
									<span className="hidden sm:inline">{data.to}</span>
									<span className="inline sm:hidden">{formatAddress(data.to)}</span>
								</span>
							</div>
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Gas Used</span>
								<span className="font-medium text-white">{formatGas(data.gasUsed)}</span>
							</div>
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Effective Gas Price</span>
								<span className="font-medium text-white">{formatGas(data.effectiveGasPrice)} Wei</span>
							</div>
							<div className="flex justify-between p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Network</span>
								<span className="font-medium text-white capitalize">{data.network} {data.network_type}</span>
							</div>
						</div>
					</div>

					{/* Contract info */}
					{data.contractAddress && (
						<div className="mt-1 sm:mt-2">
							<h4 className="text-xs sm:text-sm font-medium text-white mb-2">Contract Created</h4>
							<div className="text-xxs sm:text-xs bg-gray-900 p-2 rounded overflow-hidden text-gray-400 border border-gray-700 hover:bg-gray-700 transition-all duration-200">
								<div className="truncate" title={data.contractAddress}>
									<span className="font-medium text-white">Contract Address: </span>
									<span className="hidden sm:inline font-mono">{data.contractAddress}</span>
									<span className="inline sm:hidden font-mono">{formatAddress(data.contractAddress)}</span>
								</div>
							</div>
						</div>
					)}

					{/* Logs info - simplified */}
					{data.logs.length > 0 && (
						<div className="mt-1 sm:mt-2">
							<h4 className="text-xs sm:text-sm font-medium text-white mb-2">
								Event Logs <span className="text-gray-400">({data.logs.length})</span>
							</h4>
							<div className="space-y-2">
								{logsPreview.map((log, index) => (
									<div key={index} className="text-xxs sm:text-xs bg-gray-900 p-2 rounded overflow-hidden text-gray-400 border border-gray-700">
										<div className="mb-1">
											<span className="font-medium text-white">Contract: </span>
											<span className="font-mono">{formatAddress(log.address, 8)}</span>
										</div>
										{log.topics.length > 0 && (
											<div className="mb-1">
												<span className="font-medium text-white">Topic 0: </span>
												<span className="font-mono">{formatAddress(log.topics[0], 10)}</span>
											</div>
										)}
									</div>
								))}
								{hasMoreLogs && (
									<div className="text-center text-gray-400 text-xs p-1">
										{data.logs.length - 3} more logs...
									</div>
								)}
							</div>
						</div>
					)}

					{/* Explorer link - would need to be constructed based on network */}
					<div className="mt-2 text-center">
						<a
							href={explorerUrl}
							target="_blank"
							rel="noopener noreferrer"
							className="text-blue-400 hover:text-blue-300 transition-colors text-sm inline-flex items-center"
						>
							View on Block Explorer
							<svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
							</svg>
						</a>
					</div>
				</div>
			</div>
		);
	},
});