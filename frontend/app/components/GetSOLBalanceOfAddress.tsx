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
			<div className="rounded-lg border border-gray-200 overflow-hidden bg-white shadow-sm">
				<div className="p-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
					<div className="flex items-center justify-between">
						<h3 className="text-lg font-medium text-gray-800">SOL Balance</h3>
						<div className="flex items-center">
							<span className="text-sm text-gray-700 mr-2">Solana</span>
							<Image
								src={data.solLogo || "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/So11111111111111111111111111111111111111112/logo.png"}
								alt="Solana Logo"
								width={24}
								height={24}
								className="rounded-full"
							/>
						</div>
					</div>
				</div>

				<div className="p-4">
					<div className="grid gap-4">
						{/* 主要余额信息 */}
						<div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg border border-gray-200">
							<div>
								<p className="text-sm text-gray-700">Current Balance</p>
								<p className="text-xl font-semibold text-gray-800">
									{formatNumber(data.balance)}
									<span className="text-gray-600 text-base ml-1">SOL</span>
								</p>
							</div>
							{/* <div className="text-blue-500">
								<svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
									<circle cx="12" cy="12" r="10"></circle>
									<line x1="12" y1="8" x2="12" y2="16"></line>
									<line x1="8" y1="12" x2="16" y2="12"></line>
								</svg>
							</div> */}
						</div>

						{/* 钱包信息 */}
						<div className="mt-2">
							<h4 className="text-sm font-medium text-gray-800 mb-2">Wallet Info</h4>
							<div className="text-xs bg-gray-50 p-2 rounded overflow-hidden text-gray-700 border border-gray-200 hover:bg-blue-50 transition-all duration-200">
								<div className="truncate" title={data.address}>
									<span className="font-medium text-gray-800">Address: </span>
									{data.address}
								</div>
							</div>
						</div>

						{/* 其他相关信息 */}
						<div className="mt-2">
							<h4 className="text-sm font-medium text-gray-800 mb-2">Market Info</h4>
							<div className="grid grid-cols-2 gap-2 text-sm">
								<div className="flex justify-between p-2 border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
									<span className="text-gray-700">Network</span>
									<span className="font-medium text-gray-800">Solana Mainnet</span>
								</div>
								<div className="flex justify-between p-2 border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
									<span className="text-gray-700">Last Updated</span>
									<span className="font-medium text-gray-800">{new Date().toLocaleTimeString()}</span>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		);
	},
});