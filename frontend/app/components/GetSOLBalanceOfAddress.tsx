"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import Image from "next/image";
import { useState, useEffect } from "react";

// 格式化数字的辅助函数
const formatNumber = (value: string | number, decimals: string | number = 6): string => {
	const num = typeof value === 'string' ? parseFloat(value) : value;
	if (isNaN(num)) return value.toString();

	const decimalPlaces = typeof decimals === 'string' ? parseInt(decimals) : decimals;
	const maxDecimals = Math.min(decimalPlaces, 8);

	return num.toLocaleString('en-US', {
		minimumFractionDigits: 2,
		maximumFractionDigits: maxDecimals
	});
};

export type SolBalanceData = {
	address: string;
	balance: string;
	solLogo?: string;
};

export const useGetSOLBalanceOfAddress = () => useAssistantToolUI({
	toolName: "get_sol_balance",
	render: (input) => {
		const data: SolBalanceData = input.args.data;

		if (!data) return null;

		// 截断钱包地址以便显示
		const shortenedAddress = data.address
			? `${data.address.substring(0, 6)}...${data.address.substring(data.address.length - 4)}`
			: "";

		return (
			<div className="flex flex-col space-y-4 sm:space-y-6 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-3xl sm:mt-6 md:mt-8">
				<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
					<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-3">
						<h3 className="text-lg sm:text-xl font-semibold">SOL Balance</h3>
						<div className="flex items-center">
							<span className="text-xs sm:text-sm text-gray-400 mr-2">Solana</span>
							<Image
								src={data.solLogo || "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/So11111111111111111111111111111111111111112/logo.png"}
								alt="Solana Logo"
								width={20}
								height={20}
								className="rounded-full"
							/>
						</div>
					</div>

					{/* 主要余额信息 */}
					<div className="flex justify-between items-center p-2 sm:p-3 bg-gray-800 rounded-lg border border-gray-700 mb-3 sm:mb-4">
						<div>
							<p className="text-xs sm:text-sm text-gray-400">Current Balance</p>
							<p className="text-base sm:text-xl font-semibold text-white">
								{formatNumber(data.balance)}
								<span className="text-gray-400 text-sm sm:text-base ml-1">SOL</span>
							</p>
						</div>
					</div>

					{/* 钱包信息 */}
					<div className="mt-2 sm:mt-3">
						<h4 className="text-xs sm:text-sm font-semibold mb-1 sm:mb-2">Wallet Info</h4>
						<div className="text-2xs sm:text-xs bg-gray-800 p-1.5 sm:p-2 rounded overflow-hidden text-gray-300 border border-gray-700 hover:bg-gray-700 transition-all duration-200">
							<div className="flex flex-col sm:flex-row sm:items-center gap-1">
								<span className="font-medium text-white whitespace-nowrap">Address:</span>
								<span className="truncate" title={data.address}>
									{shortenedAddress}
								</span>
								<button
									onClick={() => navigator.clipboard.writeText(data.address)}
									className="text-2xs sm:text-xs text-blue-400 hover:text-blue-300 ml-auto mt-1 sm:mt-0"
								>
									Copy
								</button>
							</div>
						</div>
					</div>

					{/* 其他相关信息 */}
					<div className="mt-2 sm:mt-3">
						<h4 className="text-xs sm:text-sm font-semibold mb-1 sm:mb-2">Market Info</h4>
						<div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs sm:text-sm">
							<div className="flex justify-between p-1.5 sm:p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Network</span>
								<span className="font-medium text-white">Solana Mainnet</span>
							</div>
							<div className="flex justify-between p-1.5 sm:p-2 border-b border-gray-700 hover:bg-gray-700 transition-colors duration-150">
								<span className="text-gray-400">Last Updated</span>
								<span className="font-medium text-white">{new Date().toLocaleTimeString()}</span>
							</div>
						</div>
					</div>
				</div>
			</div>
		);
	},
});
