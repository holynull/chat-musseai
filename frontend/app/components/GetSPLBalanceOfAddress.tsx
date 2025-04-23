"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import Image from "next/image";
import { useState, useEffect } from "react";

export type Balance = {
	success: boolean,
	balance: string,
	symbol: string,
	token_mint_address: string
};

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

export const useGetSPLBalanceOfAddress = () => useAssistantToolUI({
	toolName: "get_spl_token_balance",
	render: (input) => {
		const data: Balance = input.args.data;

		if (!data) return null;

		// 获取默认的代币logo
		const defaultTokenLogo = "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v/logo.png";

		// 截断代币地址以便显示
		const shortenedTokenAddress = data.token_mint_address
			? `${data.token_mint_address.substring(0, 6)}...${data.token_mint_address.substring(data.token_mint_address.length - 4)}`
			: "";

		return (
			<div className="rounded-lg border border-gray-200 overflow-hidden bg-white shadow-sm sm:mt-6 md:mt-8">
				<div className="p-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
					<div className="flex items-center justify-between">
						<h3 className="text-lg font-medium text-gray-800">SPL Token Balance</h3>
						<div className="flex items-center">
							<span className="text-sm text-gray-700 mr-2">Solana SPL</span>
							<img
								src={defaultTokenLogo}
								alt={`${data.symbol} Logo`}
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
									<span className="text-gray-600 text-base ml-1">{data.symbol}</span>
								</p>
							</div>
						</div>

						{/* 代币信息 */}
						<div className="mt-2">
							<h4 className="text-sm font-medium text-gray-800 mb-2">Token Info</h4>
							<div className="text-xs bg-gray-50 p-2 rounded overflow-hidden text-gray-700 border border-gray-200 hover:bg-blue-50 transition-all duration-200">
								<div className="truncate" title={data.token_mint_address}>
									<span className="font-medium text-gray-800">Token Address: </span>
									{data.token_mint_address}
								</div>
							</div>
						</div>

						{/* 市场信息 */}
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
								<div className="flex justify-between p-2 border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
									<span className="text-gray-700">Status</span>
									<span className={`font-medium ${data.success ? 'text-green-600' : 'text-red-600'}`}>
										{data.success ? 'Success' : 'Failed'}
									</span>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		);
	},
});