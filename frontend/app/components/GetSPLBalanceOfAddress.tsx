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
		const [isMobile, setIsMobile] = useState(false);

		useEffect(() => {
			// 检测窗口宽度并设置移动设备状态
			const checkMobile = () => setIsMobile(window.innerWidth < 640);
			checkMobile();
			window.addEventListener('resize', checkMobile);
			return () => window.removeEventListener('resize', checkMobile);
		}, []);

		if (!data) return null;

		// 获取默认的代币logo
		const defaultTokenLogo = "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v/logo.png";

		// 截断代币地址以便显示
		const shortenedTokenAddress = data.token_mint_address
			? `${data.token_mint_address.substring(0, 6)}...${data.token_mint_address.substring(data.token_mint_address.length - 4)}`
			: "";

		return (
			<div className="flex flex-col space-y-4 sm:space-y-6 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-3xl sm:mt-6 md:mt-8">
				<h2 className="text-xl sm:text-2xl font-bold text-center">SPL Token Balance</h2>

				{/* 主要余额信息 */}
				<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
					<h3 className="text-lg sm:text-xl font-semibold mb-2 sm:mb-3">Balance Information</h3>
					<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-3 gap-3">
						<div>
							<p className="text-sm text-gray-400">Current Balance</p>
							<p className="text-2xl sm:text-3xl font-bold text-white">
								{formatNumber(data.balance)}
								<span className="text-gray-300 text-base sm:text-lg ml-1">{data.symbol}</span>
							</p>
						</div>
						<div className="flex items-center mt-2 sm:mt-0">
							<Image
								src={defaultTokenLogo}
								alt={`${data.symbol} Logo`}
								width={32}
								height={32}
								className="rounded-full sm:w-9 sm:h-9"
							/>
						</div>
					</div>
				</div>

				{/* 代币信息 */}
				<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
					<h3 className="text-lg sm:text-xl font-semibold mb-2 sm:mb-3">Token Information</h3>
					<div className="mt-2">
						<div className="bg-gray-800 p-2 sm:p-3 rounded-lg border border-gray-700 hover:bg-gray-700 transition-all duration-200">
							<div className="text-sm" title={data.token_mint_address}>
								<span className="font-medium text-gray-300 block sm:inline">Token Address: </span>
								<span className="text-white block sm:inline text-xs sm:text-sm break-all">
									{isMobile ? shortenedTokenAddress : data.token_mint_address}
								</span>
							</div>
						</div>
					</div>
				</div>

				{/* 市场信息 */}
				<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
					<h3 className="text-lg sm:text-xl font-semibold mb-2 sm:mb-3">Network Information</h3>
					<div className="grid grid-cols-1 xs:grid-cols-2 gap-2 sm:gap-3">
						<div className="bg-gray-800 p-2 rounded">
							<div className="text-xs sm:text-sm text-gray-400">Network</div>
							<div className="text-base sm:text-lg font-semibold">Solana Mainnet</div>
						</div>
						<div className="bg-gray-800 p-2 rounded">
							<div className="text-xs sm:text-sm text-gray-400">Last Updated</div>
							<div className="text-base sm:text-lg font-semibold">{new Date().toLocaleTimeString()}</div>
						</div>
						<div className="bg-gray-800 p-2 rounded">
							<div className="text-xs sm:text-sm text-gray-400">Status</div>
							<div className={`text-base sm:text-lg font-semibold ${data.success ? 'text-green-500' : 'text-red-500'}`}>
								{data.success ? 'Success' : 'Failed'}
							</div>
						</div>
						<div className="bg-gray-800 p-2 rounded">
							<div className="text-xs sm:text-sm text-gray-400">Token Symbol</div>
							<div className="text-base sm:text-lg font-semibold">{data.symbol}</div>
						</div>
					</div>
				</div>
			</div>
		);
	},
});
