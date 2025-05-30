"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect, useRef } from "react";

// Type definitions
interface CryptoQuote {
	price: number;
	volume_24h: number;
	volume_change_24h: number;
	percent_change_1h: number;
	percent_change_24h: number;
	percent_change_7d: number;
	percent_change_30d: number;
	percent_change_60d: number;
	percent_change_90d: number;
	market_cap: number;
	market_cap_dominance: number;
	fully_diluted_market_cap: number;
	tvl: number | null;
	last_updated: string;
}

interface Platform {
	id: number;
	name: string;
	symbol: string;
	slug: string;
	token_address: string;
}

interface Tag {
	slug: string;
	name: string;
	category: string;
}

interface QuoteData {
	id: number;
	name: string;
	symbol: string;
	slug: string;
	num_market_pairs: number;
	date_added: string;
	tags: Tag[];
	max_supply: number | null;
	circulating_supply: number;
	total_supply: number;
	platform: Platform;
	is_active: number;
	infinite_supply: boolean;
	cmc_rank: number;
	is_fiat: number;
	self_reported_circulating_supply: number;
	self_reported_market_cap: number;
	tvl_ratio: number | null;
	last_updated: string;
	quote: {
		USD: CryptoQuote;
	};
}

interface ResponseStatus {
	timestamp: string;
	error_code: number;
	error_message: null | string;
	elapsed: number;
	credit_count: number;
	notice: null | string;
}

interface QuoteResponse {
	status: ResponseStatus;
	data: Record<string, QuoteData[]>;
}

// TradingView Symbol Search API Response Types
interface TradingViewSymbol {
	symbol: string;
	description: string;
	type: string;
	exchange: string;
	currency_code: string;
	"currency-logoid"?: string;
	"base-currency-logoid"?: string;
	provider_id?: string;
	source2?: {
		id: string;
		name: string;
		description: string;
	};
	source_id?: string;
	typespecs?: string[];
	prefix?: string;
}

interface TradingViewResponse {
	symbols_remaining: number;
	symbols: TradingViewSymbol[];
}

interface TradingViewSymbolResult {
	symbol: string;
	full_name: string;
	description: string;
	exchange: string;
	ticker?: string;
	type: 'stock' | 'futures' | 'bitcoin' | 'forex' | 'index';
}

// 添加TradingView类型定义
declare global {
	interface Window {
		TradingView: {
			widget: any
		}
	}
}

const TradingViewChart = ({ symbol }: { symbol: string }) => {
	const container = useRef<HTMLDivElement>(null);
	const scriptLoaded = useRef<boolean>(false);
	const [chartHeight, setChartHeight] = useState<string>("400px");

	// 响应式调整图表高度
	useEffect(() => {
		const handleResize = () => {
			if (window.innerWidth < 640) { // sm断点
				setChartHeight("300px");
			} else if (window.innerWidth < 768) { // md断点
				setChartHeight("350px");
			} else {
				setChartHeight("400px");
			}
		};

		handleResize(); // 初始化时调用一次
		window.addEventListener("resize", handleResize);

		return () => {
			window.removeEventListener("resize", handleResize);
		};
	}, []);

	useEffect(() => {
		// 在effect开始时捕获当前的ref值
		const currentContainer = container.current;
		// 加载TradingView Widget脚本
		if (!scriptLoaded.current) {
			const script = document.createElement('script');
			script.src = 'https://s3.tradingview.com/tv.js';
			script.async = true;
			script.onload = () => {
				scriptLoaded.current = true;
				if (container.current && window.TradingView) {
					renderChart();
				}
			};
			document.head.appendChild(script);
		} else if (container.current && window.TradingView) {
			renderChart();
		}

		function renderChart() {
			// 清空容器以防止重复渲染
			if (currentContainer) {
				currentContainer.innerHTML = '';

				// 实现获取symbols数据的功能
				fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/tradingview/symbol_search?text=${symbol}`, { headers: { Authorization: `Bearer ${localStorage.getItem("auth_token")}` } })
					.then(response => {
						if (!response.ok) {
							throw new Error(`HTTP error! Status: ${response.status}`);
						}
						return response.json();
					})
					.then((symbolData: any) => {
						// 从symbolData中提取有效的TradingView符号
						let tvSymbol = "";

						// 处理symbolData.symbols，从中找到匹配的交易对
						if (symbolData && symbolData.symbols && symbolData.symbols.length > 0) {
							// 去除symbol名称中的HTML标签，确保匹配纯文本
							const cleanSymbol = symbol.replace(/[^A-Za-z0-9]/g, '').toUpperCase();

							// 筛选出匹配的交易对
							const matchingSymbols = symbolData.symbols.filter((s: TradingViewSymbol) => {
								// 清理<em>标签
								const cleanedSymbolName = s.symbol.replace(/<\/?em>/g, '');
								return cleanedSymbolName.includes(cleanSymbol);
							});

							if (matchingSymbols.length > 0) {
								// 定义交易所优先级
								const exchangePriority = ['BINANCE', 'COINBASE', 'OKX', 'POLONIEX', 'KRAKEN', 'KUCOIN'];
								// 定义计价货币优先级
								const currencyPriority = ['USDT', 'USD', 'USDC', 'BTC', 'ETH'];

								// 按交易所和计价货币优先级排序
								const sortedSymbols = [...matchingSymbols].sort((a, b) => {
									// 首先按类型排序 - 优先选择spot类型的交易对
									if (a.type === 'spot' && b.type !== 'spot') return -1;
									if (a.type !== 'spot' && b.type === 'spot') return 1;

									// 然后按交易所优先级排序
									const aExchangePriority = exchangePriority.indexOf(a.exchange);
									const bExchangePriority = exchangePriority.indexOf(b.exchange);

									if (aExchangePriority !== -1 && bExchangePriority !== -1) {
										if (aExchangePriority !== bExchangePriority) {
											return aExchangePriority - bExchangePriority;
										}
									} else if (aExchangePriority !== -1) {
										return -1;
									} else if (bExchangePriority !== -1) {
										return 1;
									}

									// 最后按计价货币优先级排序
									const aCurrencyMatch = currencyPriority.findIndex(c =>
										a.symbol.replace(/<\/?em>/g, '').endsWith(c));
									const bCurrencyMatch = currencyPriority.findIndex(c =>
										b.symbol.replace(/<\/?em>/g, '').endsWith(c));

									if (aCurrencyMatch !== -1 && bCurrencyMatch !== -1) {
										return aCurrencyMatch - bCurrencyMatch;
									} else if (aCurrencyMatch !== -1) {
										return -1;
									} else if (bCurrencyMatch !== -1) {
										return 1;
									}

									return 0;
								});

								// 选择排序后的第一个交易对
								if (sortedSymbols.length > 0) {
									const bestMatch = sortedSymbols[0];
									// 构造TradingView所需的符号格式
									const cleanSymbolName = bestMatch.symbol.replace(/<\/?em>/g, '');

									// 如果有前缀，则使用前缀构造完整符号
									if (bestMatch.prefix) {
										tvSymbol = `${bestMatch.prefix}:${cleanSymbolName}`;
									}
									// 否则使用交易所名称构造
									else if (bestMatch.exchange) {
										tvSymbol = `${bestMatch.exchange}:${cleanSymbolName}`;
									}
									// 如果都没有，直接使用符号
									else {
										tvSymbol = cleanSymbolName;
									}
								}
							}
						}

						// 如果没有找到匹配的交易对，使用默认格式
						if (!tvSymbol) {
							tvSymbol = `BINANCE:${symbol}USDT`;
						}
						if (container && container.current) {
							// 创建TradingView小部件
							new window.TradingView.widget({
								autosize: true,
								symbol: tvSymbol,
								interval: 'D',
								timezone: 'Etc/UTC',
								theme: 'dark', // 修改为深色主题以匹配BuySellSignal
								style: '1',
								locale: 'en',
								toolbar_bg: '#2D3748', // 修改为深色工具栏背景
								enable_publishing: false,
								allow_symbol_change: true,
								container_id: container.current?.id || '',
								// 适配移动端的配置
								hide_side_toolbar: window.innerWidth < 768, // 在移动设备上隐藏侧边工具栏
								hide_top_toolbar: window.innerWidth < 640, // 在小屏设备上隐藏顶部工具栏
								// 以下设置简化移动端UI
								hide_legend: window.innerWidth < 480,
								studies: []
							});
						}
					})
					.catch(error => {
						console.error('Error fetching symbol data:', error);
						if (container && container.current) {
							new window.TradingView.widget({
								autosize: true,
								symbol: `BINANCE:${symbol}USD`,
								interval: 'D',
								timezone: 'Etc/UTC',
								theme: 'dark', // 修改为深色主题
								style: '1',
								locale: 'en',
								toolbar_bg: '#2D3748', // 修改为深色工具栏背景
								enable_publishing: false,
								allow_symbol_change: true,
								container_id: container.current?.id || '',
								// 适配移动端的配置
								hide_side_toolbar: window.innerWidth < 768,
								hide_top_toolbar: window.innerWidth < 640,
								hide_legend: window.innerWidth < 480,
								studies: []
							});
						}
					});
			}
		}

		// 清理函数
		return () => {
			if (currentContainer) {
				currentContainer.innerHTML = '';
			}
		};
	}, [symbol]);

	return <div id={`tradingview_${symbol}`} ref={container} style={{ height: chartHeight, width: '100%' }} />;
};

// Create a proper React component for the quote display
const QuoteDisplay: React.FC<{ input: { args: { data: QuoteResponse } } }> = ({ input }) => {
	const [isLoading, setIsLoading] = useState(true);
	const responseData = input.args.data as QuoteResponse;

	useEffect(() => {
		// 模拟数据加载
		const timer = setTimeout(() => {
			setIsLoading(false);
		}, 500);
		return () => clearTimeout(timer);
	}, []);

	// Extract the first cryptocurrency data from the response
	// The data is in format: data.SYMBOL[0]
	const symbol = Object.keys(responseData ? responseData.data : {})[0];
	const cryptoData = responseData?.data[symbol ? symbol : ''][0];

	// Number formatting function
	const formatNumber = (num: number, decimals = 2) => {
		return new Intl.NumberFormat('en-US', {
			minimumFractionDigits: decimals,
			maximumFractionDigits: decimals
		}).format(num);
	};

	// Format large numbers (market cap, volume, etc.)
	const formatLargeNumber = (num: number) => {
		if (num >= 1_000_000_000) {
			return formatNumber(num / 1_000_000_000) + 'B';
		} else if (num >= 1_000_000) {
			return formatNumber(num / 1_000_000) + 'M';
		} else if (num >= 1_000) {
			return formatNumber(num / 1_000) + 'K';
		}
		return formatNumber(num);
	};

	// Format date
	const formatDate = (dateString: string) => {
		try {
			const date = new Date(dateString);
			return date.toLocaleString('en-US');
		} catch (e) {
			return dateString;
		}
	};

	// Get CSS class based on price change
	const getPercentChangeClass = (value: number) => {
		return value >= 0 ? 'text-green-500' : 'text-red-500';
	};

	if (isLoading) {
		return (
			<div className="flex flex-col space-y-6 p-4 rounded-lg border border-gray-700 bg-gray-800 text-white max-w-3xl 
          animate-pulse min-h-[500px] flex justify-center items-center">
				<div className="w-8 h-8 border-4 border-gray-600 border-t-gray-400 rounded-full animate-spin"></div>
				<p className="text-gray-400">Loading market data...</p>
			</div>
		);
	}

	return cryptoData && (
		<div className="flex flex-col space-y-4 sm:space-y-6 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white 
        w-full max-w-3xl sm:mt-6 md:mt-8 overflow-hidden">
			<h2 className="text-xl sm:text-2xl font-bold text-center">{cryptoData.name} ({cryptoData.symbol}) Market Data</h2>

			{/* Price Information */}
			<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
				<div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-2">
					<div>
						<div className="text-2xlsm:text-3xl font-bold">
							{formatNumber(cryptoData.quote.USD.price, 6)}
						</div>
						<div className={`text-sm font-medium flex items-center gap-1 ${getPercentChangeClass(cryptoData.quote.USD.percent_change_24h)}`}>
							{cryptoData.quote.USD.percent_change_24h > 0 ? '↑' : '↓'} {Math.abs(cryptoData.quote.USD.percent_change_24h).toFixed(2)}% (24h)
						</div>
					</div>
					<div className="flex flex-row sm:flex-col justify-between sm:items-end text-xs sm:text-sm gap-2 sm:gap-0">
						<div>Market Cap:{formatLargeNumber(cryptoData.quote.USD.market_cap)}</div>
						<div>24hVol:{formatLargeNumber(cryptoData.quote.USD.market_cap)}</div>
						<div>24hVol:{formatLargeNumber(cryptoData.quote.USD.volume_24h)}</div>
					</div>
				</div>
			</div>
			{/* TradingView Chart */}
			<div className="bg-gray-900 rounded-lg p-2 sm:p-4">
				<TradingViewChart symbol={cryptoData.symbol} />
			</div>

			{/* Price Changes */}
			<div className="bg-gray-900 rounded-lg p-3 sm:p-4 grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3 text-xs sm:text-sm">
				<div>
					<div className="text-gray-400">1h Change</div>
					<div className={getPercentChangeClass(cryptoData.quote.USD.percent_change_1h)}>
						{cryptoData.quote.USD.percent_change_1h > 0 ? '+' : ''}
						{formatNumber(cryptoData.quote.USD.percent_change_1h)}%
					</div>
				</div>
				<div>
					<div className="text-gray-400">24h Change</div>
					<div className={getPercentChangeClass(cryptoData.quote.USD.percent_change_24h)}>
						{cryptoData.quote.USD.percent_change_24h > 0 ? '+' : ''}
						{formatNumber(cryptoData.quote.USD.percent_change_24h)}%
					</div>
				</div>
				<div className="col-span-2 sm:col-span-1">
					<div className="text-gray-400">7d Change</div>
					<div className={getPercentChangeClass(cryptoData.quote.USD.percent_change_7d)}>
						{cryptoData.quote.USD.percent_change_7d > 0 ? '+' : ''}
						{formatNumber(cryptoData.quote.USD.percent_change_7d)}%
					</div>
				</div>
			</div>

			{/* Last Updated */}
			<div className="bg-gray-900 rounded-lg p-2 sm:p-3 text-[10px] sm:text-xs text-gray-400 text-right">
				Last Updated: {formatDate(cryptoData.last_updated)}
			</div>
		</div>
	);
};

// Update the hook to use the new component
export const useLatestQuote = () => useAssistantToolUI({
	toolName: "getLatestQuote",
	render: (input) => <QuoteDisplay input={input} />,
});
