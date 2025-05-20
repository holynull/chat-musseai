"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect, useMemo } from "react";

export type ProofData = {
	address: string;
	accountProof: string[];
	balance: string;
	codeHash: string;
	nonce: string;
	storageHash: string;
	storageProof: {
		key: string;
		value: string;
		proof: string[];
	}[];
	network: string;
	network_type: string;
};

// 将十六进制值格式化为可读格式
const formatHexValue = (hexValue: string): string => {
	if (!hexValue || !hexValue.startsWith("0x")) return hexValue;

	// 将十六进制转换为十进制
	const decimalValue = BigInt(hexValue).toString();
	return decimalValue;
};

// 截断长字符串的辅助函数
const truncateString = (str: string, maxLength: number = 8): string => {
	if (!str) return '';
	if (str.length <= maxLength * 2) return str;
	return `${str.substring(0, maxLength)}...${str.substring(str.length - maxLength)}`;
};

// 处理展开/折叠数组的组件
const CollapsibleArray = ({
	array,
	title,
	maxInitialItems = 3
}: {
	array: string[],
	title: string,
	maxInitialItems?: number
}) => {
	const [isExpanded, setIsExpanded] = useState(false);

	if (!array || array.length === 0) {
		return <div className="text-gray-400">No {title} available</div>;
	}

	const displayItems = isExpanded ? array : array.slice(0, maxInitialItems);

	return (
		<div className="mt-2">
			<div className="flex justify-between mb-1">
				<span className="text-sm font-medium text-white">{title} ({array.length})</span>
				{array.length > maxInitialItems && (
					<button
						onClick={() => setIsExpanded(!isExpanded)}
						className="text-xs text-blue-400 hover:text-blue-300"
					>
						{isExpanded ? 'Show Less' : 'Show More'}
					</button>
				)}
			</div>
			<div className="bg-gray-800 rounded-md p-2 text-xs overflow-x-auto">
				{displayItems.map((item, index) => (
					<div key={index} className="border-b border-gray-700 py-1 last:border-0">
						<span className="text-gray-400">{index}: </span>
						<span className="text-gray-300 break-all font-mono">{item}</span>
					</div>
				))}
				{!isExpanded && array.length > maxInitialItems && (
					<div className="text-center text-gray-400 mt-1">
						{array.length - maxInitialItems} more items...
					</div>
				)}
			</div>
		</div>
	);
};

// 展示存储证明的组件
const StorageProofItem = ({ proof }: { proof: { key: string; value: string; proof: string[] } }) => {
	const [isExpanded, setIsExpanded] = useState(false);

	return (
		<div className="border border-gray-700 rounded-md p-2 mb-2 bg-gray-800">
			<div className="flex justify-between items-center mb-2">
				<div className="flex-1">
					<div className="flex items-center">
						<span className="text-xs text-gray-400 mr-2">Key:</span>
						<span className="text-xs text-white font-mono">{proof.key}</span>
					</div>
					<div className="flex items-center mt-1">
						<span className="text-xs text-gray-400 mr-2">Value:</span>
						<span className="text-xs text-white font-mono">{formatHexValue(proof.value)}</span>
					</div>
				</div>
				<button
					onClick={() => setIsExpanded(!isExpanded)}
					className="text-xs text-blue-400 hover:text-blue-300 ml-2"
				>
					{isExpanded ? 'Hide Proof' : 'Show Proof'}
				</button>
			</div>
			{isExpanded && (
				<CollapsibleArray array={proof.proof} title="Storage Proof Elements" />
			)}
		</div>
	);
};

export const useEthGetProof = () => useAssistantToolUI({
	toolName: "eth_getProof",
	render: (input) => {
		const data: ProofData = input.args.data;

		if (!data) return null;

		// Format the data for display
		const formattedBalance = formatHexValue(data.balance);
		const formattedNonce = formatHexValue(data.nonce);

		return (
			<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto">
				<h2 className="text-xl sm:text-2xl font-bold text-center border-b border-gray-700 pb-2">
					Account Merkle Proof
				</h2>

				{/* Account Information */}
				<div className="grid gap-2">
					<div className="flex flex-col sm:flex-row justify-between items-start sm:items-center p-2 bg-gray-900 rounded-lg">
						<span className="text-xs sm:text-sm text-gray-400">Address:</span>
						<span className="text-xs sm:text-sm font-medium text-white break-all font-mono">{data.address}</span>
					</div>

					<div className="flex flex-col sm:flex-row justify-between items-start sm:items-center p-2 bg-gray-900 rounded-lg">
						<span className="text-xs sm:text-sm text-gray-400">Network:</span>
						<span className="text-xs sm:text-sm font-medium text-white">
							{data.network} ({data.network_type})
						</span>
					</div>

					<div className="flex flex-col sm:flex-row justify-between items-start sm:items-center p-2 bg-gray-900 rounded-lg">
						<span className="text-xs sm:text-sm text-gray-400">Balance:</span>
						<span className="text-xs sm:text-sm font-medium text-white">{formattedBalance} wei</span>
					</div>

					<div className="flex flex-col sm:flex-row justify-between items-start sm:items-center p-2 bg-gray-900 rounded-lg">
						<span className="text-xs sm:text-sm text-gray-400">Nonce:</span>
						<span className="text-xs sm:text-sm font-medium text-white">{formattedNonce}</span>
					</div>
				</div>

				{/* Hashes Section */}
				<div className="mt-2">
					<h3 className="text-sm font-medium text-white mb-2">Hash Information</h3>
					<div className="grid gap-2">
						<div className="flex flex-col p-2 bg-gray-900 rounded-lg">
							<span className="text-xs text-gray-400">Storage Hash:</span>
							<span className="text-xs font-medium text-white break-all font-mono">{data.storageHash}</span>
						</div>

						<div className="flex flex-col p-2 bg-gray-900 rounded-lg">
							<span className="text-xs text-gray-400">Code Hash:</span>
							<span className="text-xs font-medium text-white break-all font-mono">{data.codeHash}</span>
						</div>
					</div>
				</div>

				{/* Account Proof */}
				<CollapsibleArray array={data.accountProof} title="Account Proof" />

				{/* Storage Proofs */}
				{data.storageProof && data.storageProof.length > 0 && (
					<div className="mt-2">
						<h3 className="text-sm font-medium text-white mb-2">Storage Proofs ({data.storageProof.length})</h3>
						<div className="space-y-2">
							{data.storageProof.map((proof, index) => (
								<StorageProofItem key={index} proof={proof} />
							))}
						</div>
					</div>
				)}

				<div className="text-xs text-gray-400 mt-2 text-center">
					Merkle-Patricia proof that shows the account state at the requested block
				</div>
			</div>
		);
	},
});
