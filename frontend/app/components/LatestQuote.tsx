"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect, useRef } from "react";

// Type definitions for CryptoCompare API response
interface PriceData {
	price: string;
	price_raw: number;
	market_cap: string;
	market_cap_raw: number;
}

interface MarketData {
	circulating_supply: number;
	total_supply: number;
	last_update: number;
	high_24h: number;
	low_24h: number;
	open_24h: number;
}

interface ChangeData {
	change_24h: string;
	change_24h_pct: string;
	change_24h_raw: number;
	change_24h_pct_raw: number;
}

interface VolumeData {
	volume_24h: string;
	volume_24h_to: string;
	volume_24h_raw: number;
	volume_24h_to_raw: number;
}

interface CryptoCurrencyData {
	symbol: string;
	prices: {
		USD: PriceData;
		EUR: PriceData;
		BTC: PriceData;
	};
	market_data: MarketData;
	changes: {
		USD: ChangeData;
		EUR: ChangeData;
		BTC: ChangeData;
	};
	volume: {
		USD: VolumeData;
		EUR: VolumeData;
		BTC: VolumeData;
	};
	supply: Record<string, any>;
}

interface CryptoCompareResponse {
	source: string;
	timestamp: string;
	symbols_requested: string[];
	data: Record<string, CryptoCurrencyData>;
}

// TradingView Symbol Search API Response Types (keeping existing)
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

// Add TradingView type definitions
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

	// Responsive chart height adjustment
	useEffect(() => {
		const handleResize = () => {
			if (window.innerWidth < 640) { // sm breakpoint
				setChartHeight("300px");
			} else if (window.innerWidth < 768) { // md breakpoint
				setChartHeight("350px");
			} else {
				setChartHeight("400px");
			}
		};

		handleResize(); // Call once on initialization
		window.addEventListener("resize", handleResize);

		return () => {
			window.removeEventListener("resize", handleResize);
		};
	}, []);

	useEffect(() => {
		// Capture current ref value at the beginning of effect
		const currentContainer = container.current;
		// Load TradingView Widget script
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
			// Clear container to prevent duplicate rendering
			if (currentContainer) {
				currentContainer.innerHTML = '';

				// Implement symbol data fetching functionality
				fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/tradingview/symbol_search?text=${symbol}`, { headers: { Authorization: `Bearer ${localStorage.getItem("auth_token")}` } })
					.then(response => {
						if (!response.ok) {
							throw new Error(`HTTP error! Status: ${response.status}`);
						}
						return response.json();
					})
					.then((symbolData: any) => {
						// Extract valid TradingView symbol from symbolData
						let tvSymbol = "";

						// Process symbolData.symbols to find matching trading pairs
						if (symbolData && symbolData.symbols && symbolData.symbols.length > 0) {
							// Remove HTML tags from symbol name to ensure pure text matching
							const cleanSymbol = symbol.replace(/[^A-Za-z0-9]/g, '').toUpperCase();

							// Filter matching trading pairs
							const matchingSymbols = symbolData.symbols.filter((s: TradingViewSymbol) => {
								// Clean <em> tags
								const cleanedSymbolName = s.symbol.replace(/<\/?em>/g, '');
								return cleanedSymbolName.includes(cleanSymbol);
							});

							if (matchingSymbols.length > 0) {
								// Define exchange priority
								const exchangePriority = ['BINANCE', 'COINBASE', 'OKX', 'POLONIEX', 'KRAKEN', 'KUCOIN'];
								// Define base currency priority
								const currencyPriority = ['USDT', 'USD', 'USDC', 'BTC', 'ETH'];

								// Sort by exchange and base currency priority
								const sortedSymbols = [...matchingSymbols].sort((a, b) => {
									// First sort by type - prioritize spot type trading pairs
									if (a.type === 'spot' && b.type !== 'spot') return -1;
									if (a.type !== 'spot' && b.type === 'spot') return 1;

									// Then sort by exchange priority
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

									// Finally sort by base currency priority
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

								// Select the first trading pair after sorting
								if (sortedSymbols.length > 0) {
									const bestMatch = sortedSymbols[0];
									// Construct TradingView required symbol format
									const cleanSymbolName = bestMatch.symbol.replace(/<\/?em>/g, '');

									// If has prefix, use prefix to construct full symbol
									if (bestMatch.prefix) {
										tvSymbol = `${bestMatch.prefix}:${cleanSymbolName}`;
									}
									// Otherwise use exchange name to construct
									else if (bestMatch.exchange) {
										tvSymbol = `${bestMatch.exchange}:${cleanSymbolName}`;
									}
									// If neither, use symbol directly
									else {
										tvSymbol = cleanSymbolName;
									}
								}
							}
						}

						// If no matching trading pair found, use default format
						if (!tvSymbol) {
							tvSymbol = `BINANCE:${symbol}USDT`;
						}
						if (container && container.current) {
							// Create TradingView widget
							new window.TradingView.widget({
								autosize: true,
								symbol: tvSymbol,
								interval: 'D',
								timezone: 'Etc/UTC',
								theme: 'dark', // Change to dark theme to match BuySellSignal
								style: '1',
								locale: 'en',
								toolbar_bg: '#2D3748', // Change to dark toolbar background
								enable_publishing: false,
								allow_symbol_change: true,
								container_id: container.current?.id || '',
								// Mobile adaptation configuration
								hide_side_toolbar: window.innerWidth < 768, // Hide side toolbar on mobile devices
								hide_top_toolbar: window.innerWidth < 640, // Hide top toolbar on small screen devices
								// Following settings simplify mobile UI
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
								theme: 'dark', // Change to dark theme
								style: '1',
								locale: 'en',
								toolbar_bg: '#2D3748', // Change to dark toolbar background
								enable_publishing: false,
								allow_symbol_change: true,
								container_id: container.current?.id || '',
								// Mobile adaptation configuration
								hide_side_toolbar: window.innerWidth < 768,
								hide_top_toolbar: window.innerWidth < 640,
								hide_legend: window.innerWidth < 480,
								studies: []
							});
						}
					});
			}
		}

		// Cleanup function
		return () => {
			if (currentContainer) {
				currentContainer.innerHTML = '';
			}
		};
	}, [symbol]);

	return <div id={`tradingview_${symbol}`} ref={container} style={{ height: chartHeight, width: '100%' }} />;
};

// Create a proper React component for the quote display
const QuoteDisplay: React.FC<{ input: { args: { data: CryptoCompareResponse } } }> = ({ input }) => {
	const [isLoading, setIsLoading] = useState(true);
	const responseData = input.args.data as CryptoCompareResponse;

	useEffect(() => {
		// Simulate data loading
		const timer = setTimeout(() => {
			setIsLoading(false);
		}, 500);
		return () => clearTimeout(timer);
	}, []);

	// Extract the first cryptocurrency data from the response
	// The data is in format: data[SYMBOL]
	const symbol = Object.keys(responseData ? responseData.data : {})[0];
	const cryptoData = responseData?.data[symbol];

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

	// Format date from timestamp
	const formatDate = (timestamp: number) => {
		try {
			const date = new Date(timestamp * 1000); // Convert Unix timestamp to milliseconds
			return date.toLocaleString('en-US');
		} catch (e) {
			return 'N/A';
		}
	};

	// Get CSS class based on price change
	const getPercentChangeClass = (value: number) => {
		return value >= 0 ? 'text-green-500' : 'text-red-500';
	};

	// Parse percentage from string format
	const parsePercentage = (percentStr: string) => {
		return parseFloat(percentStr) || 0;
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
			<h2 className="text-xl sm:text-2xl font-bold text-center">{cryptoData.symbol} Market Data</h2>

			{/* Price Information */}
			<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
				<div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-2">
					<div>
						<div className="text-2xl sm:text-3xl font-bold">
							${formatNumber(cryptoData.prices.USD.price_raw, 6)}
						</div>
						<div className={`text-sm font-medium flex items-center gap-1 ${getPercentChangeClass(parsePercentage(cryptoData.changes.USD.change_24h_pct))}`}>
							{parsePercentage(cryptoData.changes.USD.change_24h_pct) > 0 ? '↑' : '↓'} 
							{Math.abs(parsePercentage(cryptoData.changes.USD.change_24h_pct)).toFixed(2)}% (24h)
						</div>
					</div>
					<div className="flex flex-row sm:flex-col justify-between sm:items-end text-xs sm:text-sm gap-2 sm:gap-0">
						<div>Market Cap: {formatLargeNumber(cryptoData.prices.USD.market_cap_raw)}</div>
						<div>24h Vol: {formatLargeNumber(cryptoData.volume.USD.volume_24h_to_raw)}</div>
						<div>Circulating: {formatLargeNumber(cryptoData.market_data.circulating_supply)}</div>
					</div>
				</div>
			</div>

			{/* TradingView Chart */}
			<div className="bg-gray-900 rounded-lg p-2 sm:p-4">
				<TradingViewChart symbol={cryptoData.symbol} />
			</div>

			{/* Price Changes and Market Data */}
			<div className="bg-gray-900 rounded-lg p-3 sm:p-4 grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3 text-xs sm:text-sm">
				<div>
					<div className="text-gray-400">24h Change</div>
					<div className={getPercentChangeClass(parsePercentage(cryptoData.changes.USD.change_24h_pct))}>
						{parsePercentage(cryptoData.changes.USD.change_24h_pct) > 0 ? '+' : ''}
						{formatNumber(parsePercentage(cryptoData.changes.USD.change_24h_pct))}%
					</div>
					<div className="text-xs text-gray-500">
						${formatNumber(cryptoData.changes.USD.change_24h_raw)}
					</div>
				</div>
				<div>
					<div className="text-gray-400">24h High</div>
					<div className="text-green-400">
						${formatNumber(cryptoData.market_data.high_24h)}
					</div>
				</div>
				<div className="col-span-2 sm:col-span-1">
					<div className="text-gray-400">24h Low</div>
					<div className="text-red-400">
						${formatNumber(cryptoData.market_data.low_24h)}
					</div>
				</div>
			</div>

			{/* Supply Information */}
			<div className="bg-gray-900 rounded-lg p-3 sm:p-4 grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3 text-xs sm:text-sm">
				<div>
					<div className="text-gray-400">Circulating Supply</div>
					<div>{formatLargeNumber(cryptoData.market_data.circulating_supply)} {cryptoData.symbol}</div>
				</div>
				<div>
					<div className="text-gray-400">Total Supply</div>
					<div>{formatLargeNumber(cryptoData.market_data.total_supply)} {cryptoData.symbol}</div>
				</div>
			</div>

			{/* Volume Information */}
			<div className="bg-gray-900 rounded-lg p-3 sm:p-4 grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3 text-xs sm:text-sm">
				<div>
					<div className="text-gray-400">24h Volume (USD)</div>
					<div>${formatLargeNumber(cryptoData.volume.USD.volume_24h_to_raw)}</div>
				</div>
				<div>
					<div className="text-gray-400">24h Volume ({cryptoData.symbol})</div>
					<div>{formatLargeNumber(cryptoData.volume.USD.volume_24h_raw)} {cryptoData.symbol}</div>
				</div>
			</div>

			{/* Multi-Currency Price Display */}
			<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
				<h3 className="text-sm font-semibold mb-2 text-gray-300">Multi-Currency Prices</h3>
				<div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs sm:text-sm">
					<div className="flex justify-between items-center">
						<span className="text-gray-400">USD:</span>
						<span className="font-medium">{cryptoData.prices.USD.price}</span>
					</div>
					<div className="flex justify-between items-center">
						<span className="text-gray-400">EUR:</span>
						<span className="font-medium">{cryptoData.prices.EUR.price}</span>
					</div>
					<div className="flex justify-between items-center">
						<span className="text-gray-400">BTC:</span>
						<span className="font-medium">{cryptoData.prices.BTC.price}</span>
					</div>
				</div>
			</div>

			{/* Market Statistics */}
			<div className="bg-gray-900 rounded-lg p-3 sm:p-4 grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3 text-xs sm:text-sm">
				<div>
					<div className="text-gray-400">Open (24h)</div>
					<div>${formatNumber(cryptoData.market_data.open_24h)}</div>
				</div>
				<div>
					<div className="text-gray-400">Market Cap (USD)</div>
					<div>{cryptoData.prices.USD.market_cap}</div>
				</div>
				<div className="col-span-2 sm:col-span-1">
					<div className="text-gray-400">Market Cap (EUR)</div>
					<div>{cryptoData.prices.EUR.market_cap}</div>
				</div>
			</div>

			{/* Data Source and Last Updated */}
			<div className="bg-gray-900 rounded-lg p-2 sm:p-3 text-[10px] sm:text-xs text-gray-400 flex justify-between items-center">
				<div>Data Source: {responseData.source}</div>
				<div>Last Updated: {formatDate(cryptoData.market_data.last_update)}</div>
			</div>
		</div>
	);
};

// Update the hook to use the new component
export const useLatestQuote = () => useAssistantToolUI({
	toolName: "getLatestQuote",
	render: (input) => <QuoteDisplay input={input} />,
});