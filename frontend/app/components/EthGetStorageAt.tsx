// EthGetStorageAt.tsx
"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect } from "react";

export type EthStorageData = {
	result: string;
	method: string;
	network: string;
	network_type: string;
	address?: string;
	position?: string;
	block_parameter?: string;
};

// 格式化地址函数
const formatAddress = (address: string, length = 8) => {
	if (!address) return '';
	if (address.length <= length * 2) return address;
	return `${address.substring(0, length)}...${address.substring(address.length - length)}`;
};

// 十六进制转换函数
const formatHexValue = (hexValue: string): string => {
	if (!hexValue || hexValue === "0x0") return "0x0 (Empty Storage)";

	// 移除前导0x进行处理，然后再添加回来
	const cleanHex = hexValue.startsWith("0x") ? hexValue.slice(2) : hexValue;
	const paddedHex = cleanHex.padStart(64, "0");

	// 添加间隔以提高可读性
	const chunks = [];
	for (let i = 0; i < paddedHex.length; i += 8) {
		chunks.push(paddedHex.substring(i, i + 8));
	}

	return `0x${chunks.join(" ")}`;
};

export const useEthGetStorageAt = () => useAssistantToolUI({
	toolName: "eth_getStorageAt",
	render: (input) => {
		const data: EthStorageData = input.args.data;

		if (!data || !data.result) return null;

		return (
			<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto">
				<h2 className="text-xl sm:text-2xl font-bold text-center">Storage Value</h2>

				{/* Contract & Storage Information */}
				{data.address && (
					<div className="bg-gray-900 rounded-lg p-3 mb-2">
						<h3 className="text-sm font-medium text-gray-300 mb-2">Contract Information</h3>
						<div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs sm:text-sm">
							<div className="flex flex-col">
								<span className="text-gray-400">Contract Address</span>
								<span className="font-medium text-white overflow-x-auto">
									<span className="hidden sm:inline">{data.address}</span>
									<span className="inline sm:hidden">{formatAddress(data.address)}</span>
								</span>
							</div>
							<div className="flex flex-col">
								<span className="text-gray-400">Storage Position</span>
								<span className="font-medium text-white">{data.position || "0x0"}</span>
							</div>
							<div className="flex flex-col">
								<span className="text-gray-400">Block Parameter</span>
								<span className="font-medium text-white">{data.block_parameter || "latest"}</span>
							</div>
						</div>
					</div>
				)}

				{/* Network Information */}
				<div className="bg-gray-900 rounded-lg p-3 mb-2">
					<h3 className="text-sm font-medium text-gray-300 mb-2">Network Information</h3>
					<div className="grid grid-cols-2 gap-2 text-xs sm:text-sm">
						<div className="flex flex-col">
							<span className="text-gray-400">Network</span>
							<span className="font-medium text-white capitalize">
								{data.network || "ethereum"}
							</span>
						</div>
						<div className="flex flex-col">
							<span className="text-gray-400">Network Type</span>
							<span className="font-medium text-white capitalize">
								{data.network_type || "mainnet"}
							</span>
						</div>
					</div>
				</div>

				{/* Storage Value */}
				<div className="bg-gray-900 rounded-lg p-3">
					<h3 className="text-sm font-medium text-gray-300 mb-2">Storage Value</h3>
					<div className="overflow-x-auto">
						<div className="bg-gray-700 p-3 rounded-md font-mono text-xs sm:text-sm break-all">
							{formatHexValue(data.result)}
						</div>
					</div>

					{/* Additional display for different interpretations */}
					<div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
						<div className="flex flex-col">
							<span className="text-gray-400 text-xs">As Decimal</span>
							<span className="font-medium text-white overflow-x-auto">
								{data.result && data.result !== "0x0"
									? BigInt(data.result).toString()
									: "0"}
							</span>
						</div>
						<div className="flex flex-col">
							<span className="text-gray-400 text-xs">Method</span>
							<span className="font-medium text-white">
								{data.method || "eth_getStorageAt"}
							</span>
						</div>
					</div>
				</div>

				<div className="text-xs text-gray-400 text-center mt-2 italic">
					Storage values are shown in hexadecimal format. Values may represent various data types depending on the contract&apos;s storage layout.
				</div>
			</div>
		);
	},
});
