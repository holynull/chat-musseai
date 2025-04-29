"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useEffect, useState } from "react";
import Image from "next/image";

// 定义TokenMetadata接口
interface TokenMetadata {
	status: {
		timestamp: string;
		error_code: number;
		error_message: string | null;
		elapsed: number;
		credit_count: number;
		notice: string | null;
	};
	data: {
		[symbol: string]: Array<{
			id: number;
			name: string;
			symbol: string;
			category: string;
			description: string;
			slug: string;
			logo: string;
			subreddit: string;
			notice: string;
			tags: string[] | null;
			"tag-names": string[] | null;
			"tag-groups": string[] | null;
			urls: {
				website: string[];
				twitter: string[];
				message_board: string[];
				chat: string[];
				facebook: string[];
				explorer: string[];
				reddit: string[];
				technical_doc: string[];
				source_code: string[];
				announcement: string[];
			};
			platform: {
				id: string;
				name: string;
				slug: string;
				symbol: string;
				token_address: string;
			};
			date_added: string;
			twitter_username: string;
			is_hidden: number;
			date_launched: string | null;
			contract_address: Array<{
				contract_address: string;
				platform: {
					name: string;
					coin: {
						id: string;
						name: string;
						symbol: string;
						slug: string;
					};
				};
			}>;
			self_reported_circulating_supply: number | null;
			self_reported_tags: string[] | null;
			self_reported_market_cap: number | null;
			infinite_supply: boolean;
		}>;
	};
}

// 链接组件
const LinkItem = ({ href, label, className = "" }: { href: string; label: string; className?: string }) => (
	<a
		href={href}
		target="_blank"
		rel="noopener noreferrer"
		className={`inline-flex items-center px-3 py-1.5 rounded-md text-xs font-medium bg-blue-900/30 text-blue-300 hover:bg-blue-800/50 transition-colors ${className}`}
	>
		{label}
	</a>
);

export const useGetTokenMetadata = () => useAssistantToolUI({
	toolName: "getTokenMetadata",
	render: (input) => <TokenMetadataDisplay input={input} />,
});
const useWindowSize = () => {
	const [windowSize, setWindowSize] = useState({
		width: typeof window !== 'undefined' ? window.innerWidth : 0,
		height: typeof window !== 'undefined' ? window.innerHeight : 0,
	});

	useEffect(() => {
		if (typeof window === 'undefined') return;

		const handleResize = () => {
			setWindowSize({
				width: window.innerWidth,
				height: window.innerHeight,
			});
		};

		window.addEventListener('resize', handleResize);
		return () => window.removeEventListener('resize', handleResize);
	}, []);

	return windowSize;
};
const TokenMetadataDisplay = ({ input }: { input: any }) => {
	const [activeTab, setActiveTab] = useState("overview");
	const responseData: TokenMetadata = input.args.data;
	const { width } = useWindowSize();
	const getMaxLength = () => width < 640 ? 200 : 400;

	// 获取第一个代币符号（键）
	const tokenSymbol = Object.keys(responseData ? responseData.data : {})[0];

	// 获取代币信息
	const token = responseData?.data[tokenSymbol][0];
	const tokensInCategory = responseData?.data[tokenSymbol].length;

	// 格式化日期函数
	const formatDate = (dateString: string | null) => {
		if (!dateString) return 'Unknown';
		try {
			return new Date(dateString).toLocaleDateString(undefined, {
				year: 'numeric',
				month: 'short',
				day: 'numeric'
			});
		} catch (e) {
			return 'Invalid date';
		}
	};

	// 格式化数字函数
	const formatNumber = (num: number | null) => {
		if (num === null || num === undefined) return 'Unknown';

		if (num >= 1_000_000_000) {
			return `${(num / 1_000_000_000).toFixed(2)}B`;
		} else if (num >= 1_000_000) {
			return `${(num / 1_000_000).toFixed(2)}M`;
		} else if (num >= 1_000) {
			return `${(num / 1_000).toFixed(2)}K`;
		}

		return num.toLocaleString();
	};

	// 截断长文本函数
	const truncateText = (text: string, maxLength: number = 300) => {
		if (!text || text.length <= maxLength) return text;
		return text.substring(0, maxLength) + '...';
	};

	// 创建Tab组件
	const Tab = ({ id, label, active }: { id: string; label: string; active: boolean }) => (
		<button
			onClick={() => setActiveTab(id)}
			className={`px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${active
				? 'border-blue-500 text-blue-300'
				: 'border-transparent text-gray-400 hover:text-gray-300'
				}`}
		>
			{label}
		</button>
	);

	return responseData && tokenSymbol && (
		// <div className="flex flex-col space-y-6 p-4 rounded-lg border border-gray-700 bg-gray-800 text-white max-w-3xl sm:mt-6 md:mt-8">
		<div className="flex flex-col space-y-4 sm:space-y-6 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-3xl mx-auto sm:mt-6 md:mt-8 overflow-hidden">
			{/* Token Header Section */}
			<div className="flex items-center p-5 border-b border-gray-700 bg-gray-900">
				{token.logo && (
					<div className="mr-3 sm:mr-4 relative h-12 w-12 sm:h-16 sm:w-16 flex-shrink-0">
						<Image
							src={token.logo}
							alt={`${token.name} logo`}
							className="rounded-full shadow-sm border border-gray-700"
							width={64}
							height={64}
						/>
					</div>
				)}
				<div className="flex-1 min-w-0"> {/* 防止子元素溢出 */}
					<div className="flex flex-wrap items-center gap-2">
						<h2 className="text-xl sm:text-2xl font-bold text-white truncate max-w-[200px] sm:max-w-none">
							{token.name}
						</h2>
						<span className="px-2 py-0.5 rounded-full text-xs sm:text-sm font-medium bg-gray-700 text-gray-300">
							{token.symbol}
						</span>
						{tokensInCategory > 1 && (
							<span className="text-xs text-gray-400">
								+{tokensInCategory - 1} more
							</span>
						)}
					</div>
					<div className="flex items-center mt-1">
						<span className="text-sm text-gray-400 mr-3">{token.category}</span>
						{token.platform && (
							<span className="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-300">
								{token.platform.name}
							</span>
						)}
					</div>
				</div>
			</div>

			{/* Navigation Tabs */}
			<div className="border-b border-gray-700 overflow-x-auto">
				<nav className="flex min-w-max">
					<Tab id="overview" label="Overview" active={activeTab === "overview"} />
					<Tab id="details" label="Details" active={activeTab === "details"} />
					<Tab id="links" label="Links" active={activeTab === "links"} />
				</nav>
			</div>

			{/* Content Sections */}
			<div className="p-5">
				{/* Overview Tab */}
				{activeTab === "overview" && (
					<div className="space-y-5">
						{/* Description */}
						<div>
							<h3 className="text-sm font-medium text-gray-400 mb-2">Description</h3>
							<p className="text-xs sm:text-sm text-gray-300 leading-relaxed break-words">
								{truncateText(token.description, getMaxLength())}
							</p>
						</div>

						{/* Quick Stats */}
						{/* <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mt-4"> */}
						<div className="grid grid-cols-1 xs:grid-cols-2 md:grid-cols-3 gap-2 sm:gap-4 mt-3 sm:mt-4">
							<div className="bg-gray-900 p-3 rounded-lg">
								<div className="text-xs text-gray-400">Launch Date</div>
								<div className="text-sm font-medium text-gray-200 mt-1">
									{formatDate(token.date_launched || token.date_added)}
								</div>
							</div>

							<div className="bg-gray-900 p-3 rounded-lg">
								<div className="text-xs text-gray-400">Circulating Supply</div>
								<div className="text-sm font-medium text-gray-200 mt-1">
									{formatNumber(token.self_reported_circulating_supply)}
								</div>
							</div>

							<div className="bg-gray-900 p-3 rounded-lg">
								<div className="text-xs text-gray-400">Market Cap</div>
								<div className="text-sm font-medium text-gray-200 mt-1">
									{token.self_reported_market_cap ? `$${formatNumber(token.self_reported_market_cap)}` : 'Unknown'}
								</div>
							</div>
						</div>

						{/* Tags */}
						{token["tag-names"] && token["tag-names"].length > 0 && (
							<div>
								<h3 className="text-sm font-medium text-gray-400 mb-2">Tags</h3>
								<div className="flex flex-wrap gap-2">
									{token["tag-names"].map((tag, index) => (
										<span
											key={index}
											className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-900/30 text-blue-300"
										>
											{tag}
										</span>
									))}
								</div>
							</div>
						)}

						{/* Quick Links */}
						<div>
							<h3 className="text-sm font-medium text-gray-400 mb-2">Quick Links</h3>
							<div className="flex flex-wrap gap-2">
								{token.urls.website && token.urls.website.length > 0 && (
									<LinkItem href={token.urls.website[0]} label="Website" />
								)}
								{token.urls.explorer && token.urls.explorer.length > 0 && (
									<LinkItem href={token.urls.explorer[0]} label="Explorer" />
								)}
								{token.urls.twitter && token.urls.twitter.length > 0 && (
									<LinkItem href={token.urls.twitter[0]} label="Twitter" />
								)}
							</div>
						</div>
					</div>
				)}

				{/* Details Tab */}
				{activeTab === "details" && (
					<div className="space-y-5">
						{/* Contract Addresses */}
						{token.contract_address && token.contract_address.length > 0 && (
							<div>
								<h3 className="text-sm font-medium text-gray-400 mb-2">Contract Addresses</h3>
								<div className="space-y-2 bg-gray-900 rounded-lg p-3">
									{token.contract_address.map((contract, index) => (
										<div key={index} className="flex flex-col md:flex-row md:items-center py-2 border-b border-gray-800 last:border-0">
											<span className="text-xs bg-gray-700 text-gray-300 px-2 py-1 rounded mr-2 mb-1 md:mb-0 inline-block flex-shrink-0">
												{contract.platform.name}
											</span>
											<span className="text-xs text-gray-400 font-mono break-all overflow-hidden text-ellipsis">
												{contract.contract_address}
											</span>
										</div>
									))}
								</div>
							</div>
						)}

						{/* Token Economics */}
						<div>
							<h3 className="text-sm font-medium text-gray-400 mb-2">Token Economics</h3>
							<div className="grid grid-cols-2 gap-4 bg-gray-900 rounded-lg p-3">
								<div className="border-r border-gray-700 pr-3">
									<div className="text-xs text-gray-400">Circulating Supply</div>
									<div className="text-sm font-medium text-gray-200 mt-1">
										{formatNumber(token.self_reported_circulating_supply)}
									</div>
								</div>

								<div>
									<div className="text-xs text-gray-400">Market Cap</div>
									<div className="text-sm font-medium text-gray-200 mt-1">
										{token.self_reported_market_cap ? `$${formatNumber(token.self_reported_market_cap)}` : 'Unknown'}
									</div>
								</div>

								<div className="border-r border-gray-700 pr-3">
									<div className="text-xs text-gray-400">Infinite Supply</div>
									<div className="text-sm font-medium text-gray-200 mt-1">
										{token.infinite_supply ? 'Yes' : 'No'}
									</div>
								</div>

								<div>
									<div className="text-xs text-gray-400">Launch Date</div>
									<div className="text-sm font-medium text-gray-200 mt-1">
										{formatDate(token.date_launched || token.date_added)}
									</div>
								</div>
							</div>
						</div>

						{/* Additional Information */}
						{token.notice && (
							<div className="bg-yellow-900/20 border border-yellow-900/50 rounded-lg p-3">
								<h3 className="text-sm font-medium text-yellow-500 mb-1">Notice</h3>
								<p className="text-xs text-yellow-400">{token.notice}</p>
							</div>
						)}
					</div>
				)}

				{/* Links Tab */}
				{activeTab === "links" && (
					<div className="space-y-5">
						{/* Official Links */}
						<div>
							<h3 className="text-sm font-medium text-gray-400 mb-2">Official Links</h3>
							{/* <div className="grid grid-cols-2 md:grid-cols-3 gap-3"> */}
							<div className="grid grid-cols-1 xs:grid-cols-2 md:grid-cols-3 gap-2 sm:gap-3">
								{token.urls.website && token.urls.website.length > 0 && (
									<LinkItem href={token.urls.website[0]} label="Website" className="w-full justify-center" />
								)}
								{token.urls.technical_doc && token.urls.technical_doc.length > 0 && (
									<LinkItem href={token.urls.technical_doc[0]} label="Whitepaper" className="w-full justify-center" />
								)}
								{token.urls.source_code && token.urls.source_code.length > 0 && (
									<LinkItem href={token.urls.source_code[0]} label="Source Code" className="w-full justify-center" />
								)}
							</div>
						</div>

						{/* Social Links */}
						<div>
							<h3 className="text-sm font-medium text-gray-400 mb-2">Social Media</h3>
							{/* <div className="grid grid-cols-2 md:grid-cols-3 gap-3"> */}
							<div className="grid grid-cols-1 xs:grid-cols-2 md:grid-cols-3 gap-2 sm:gap-3">
								{token.urls.twitter && token.urls.twitter.length > 0 && (
									<LinkItem href={token.urls.twitter[0]} label="Twitter" className="w-full justify-center" />
								)}
								{token.urls.message_board && token.urls.message_board.length > 0 && (
									<LinkItem href={token.urls.message_board[0]} label="Blog" className="w-full justify-center" />
								)}
								{token.urls.chat && token.urls.chat.length > 0 && (
									<LinkItem href={token.urls.chat[0]} label="Chat" className="w-full justify-center" />
								)}
							</div>
						</div>

						{/* Explorers */}
						{token.urls.explorer && token.urls.explorer.length > 0 && (
							<div>
								<h3 className="text-sm font-medium text-gray-400 mb-2">Block Explorers</h3>
								<div className="space-y-2">
									{token.urls.explorer.map((explorer, index) => (
										<a
											key={index}
											href={explorer}
											target="_blank"
											rel="noopener noreferrer"
											className="block text-sm text-blue-300 hover:text-blue-200 underline-offset-2 hover:underline"
										>
											{new URL(explorer).hostname}
										</a>
									))}
								</div>
							</div>
						)}
					</div>
				)}
			</div>
		</div>
	);
};