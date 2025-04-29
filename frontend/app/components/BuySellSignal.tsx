"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect } from "react";

// Define data types
interface ComputeData {
	[key: string]: string;
}

interface MovingAverages {
	RECOMMENDATION: string;
	BUY: number;
	SELL: number;
	NEUTRAL: number;
	COMPUTE: ComputeData;
}

interface Oscillators {
	RECOMMENDATION: string;
	BUY: number;
	SELL: number;
	NEUTRAL: number;
	COMPUTE: ComputeData;
}

interface Summary {
	RECOMMENDATION: string;
	BUY: number;
	SELL: number;
	NEUTRAL: number;
}

interface Indicators {
	[key: string]: number;
}

interface TechnicalAnalysisData {
	summary: Summary;
	oscillators: Oscillators;
	moving_averages: MovingAverages;
	indicators: Indicators;
}

export const useBuySellSignal = () => useAssistantToolUI({
	toolName: "buy_sell_signal",
	render: (input) => {
		const responseData: TechnicalAnalysisData = input.args.data;

		return responseData && (
			<div className="flex flex-col space-y-4 sm:space-y-6 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-3xl mx-auto">
				<h2 className="text-xl sm:text-2xl font-bold text-center">Technical Analysis Signals</h2>

				{/* Summary Recommendation */}
				<RecommendationCard
					title="Summary"
					recommendation={responseData.summary.RECOMMENDATION}
					buyCount={responseData.summary.BUY}
					sellCount={responseData.summary.SELL}
					neutralCount={responseData.summary.NEUTRAL}
				/>

				<div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
					{/* Oscillators */}
					<AnalysisCard
						title="Oscillators"
						recommendation={responseData.oscillators.RECOMMENDATION}
						buyCount={responseData.oscillators.BUY}
						sellCount={responseData.oscillators.SELL}
						neutralCount={responseData.oscillators.NEUTRAL}
						computeData={responseData.oscillators.COMPUTE}
					/>

					{/* Moving Averages */}
					<AnalysisCard
						title="Moving Averages"
						recommendation={responseData.moving_averages.RECOMMENDATION}
						buyCount={responseData.moving_averages.BUY}
						sellCount={responseData.moving_averages.SELL}
						neutralCount={responseData.moving_averages.NEUTRAL}
						computeData={responseData.moving_averages.COMPUTE}
					/>
				</div>

				{/* Key Price Indicators */}
				<PriceIndicators indicators={responseData.indicators} />
			</div>
		);
	},
});

// Summary Recommendation Card Component
const RecommendationCard = ({
	title,
	recommendation,
	buyCount,
	sellCount,
	neutralCount
}: {
	title: string;
	recommendation: string;
	buyCount: number;
	sellCount: number;
	neutralCount: number;
}) => {
	// Select color based on recommendation type
	const getRecommendationColor = (rec: string) => {
		switch (rec) {
			case 'BUY': return 'text-green-500';
			case 'SELL': return 'text-red-500';
			default: return 'text-yellow-500';
		}
	};

	// Calculate percentages
	const total = buyCount + sellCount + neutralCount;
	const buyPercent = Math.round((buyCount / total) * 100);
	const sellPercent = Math.round((sellCount / total) * 100);
	const neutralPercent = Math.round((neutralCount / total) * 100);

	return (
		<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
			<h3 className="text-lg sm:text-xl font-semibold mb-2 sm:mb-3">{title}</h3>
			<div className="flex items-center justify-center mb-3 sm:mb-4">
				<span className={`text-2xl sm:text-3xl font-bold ${getRecommendationColor(recommendation)}`}>
					{recommendation}
				</span>
			</div>

			<div className="flex flex-wrap justify-between text-xs sm:text-sm mb-2">
				<span className="mb-1 sm:mb-0">Buy: {buyCount}</span>
				<span className="mb-1 sm:mb-0">Sell: {sellCount}</span>
				<span className="mb-1 sm:mb-0">Neutral: {neutralCount}</span>
			</div>

			{/* Signal Distribution Bar */}
			<div className="w-full h-2 flex rounded-full overflow-hidden">
				<div
					className="bg-green-500 h-full"
					style={{ width: `${buyPercent}%` }}
					title={`Buy: ${buyPercent}%`}
				/>
				<div
					className="bg-red-500 h-full"
					style={{ width: `${sellPercent}%` }}
					title={`Sell: ${sellPercent}%`}
				/>
				<div
					className="bg-yellow-500 h-full"
					style={{ width: `${neutralPercent}%` }}
					title={`Neutral: ${neutralPercent}%`}
				/>
			</div>

			<div className="flex justify-between text-xs mt-1 text-gray-400">
				<span>{buyPercent}%</span>
				<span>{sellPercent}%</span>
				<span>{neutralPercent}%</span>
			</div>
		</div>
	);
};

// Analysis Card Component (for Oscillators and Moving Averages)
const AnalysisCard = ({
	title,
	recommendation,
	buyCount,
	sellCount,
	neutralCount,
	computeData
}: {
	title: string;
	recommendation: string;
	buyCount: number;
	sellCount: number;
	neutralCount: number;
	computeData: ComputeData;
}) => {
	// Get signal color
	const getSignalColor = (signal: string) => {
		switch (signal) {
			case 'BUY': return 'text-green-500';
			case 'SELL': return 'text-red-500';
			default: return 'text-yellow-500';
		}
	};

	// State to toggle detailed indicators visibility on mobile
	const [showDetails, setShowDetails] = useState(true);

	return (
		<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
			<h3 className="text-lg sm:text-xl font-semibold mb-2">{title}</h3>
			<div className="flex items-center mb-2 sm:mb-3">
				<span className="text-sm mr-2">Recommendation:</span>
				<span className={`font-bold ${getSignalColor(recommendation)}`}>
					{recommendation}
				</span>
			</div>

			<div className="flex flex-wrap justify-between text-xs sm:text-sm mb-2 sm:mb-3">
				<div className="text-green-500 mr-2">Buy: {buyCount}</div>
				<div className="text-red-500 mr-2">Sell: {sellCount}</div>
				<div className="text-yellow-500">Neutral: {neutralCount}</div>
			</div>

			<div className="mt-2 sm:mt-3">
				<button
					onClick={() => setShowDetails(!showDetails)}
					className="text-xs sm:text-sm font-semibold mb-2 flex items-center text-blue-400 md:hidden"
				>
					{showDetails ? 'Hide Details' : 'Show Details'}
					<span className="ml-1">{showDetails ? '▲' : '▼'}</span>
				</button>

				<div className={`${showDetails ? 'block' : 'hidden md:block'}`}>
					<h4 className="text-xs sm:text-sm font-semibold mb-1 sm:mb-2">Detailed Indicators:</h4>
					<div className="grid grid-cols-1 xs:grid-cols-2 gap-1 sm:gap-2 text-xs">
						{Object.entries(computeData).map(([indicator, signal]) => (
							<div key={indicator} className="flex justify-between border-b border-gray-700 py-1">
								<span className="truncate mr-1">{indicator}:</span>
								<span className={getSignalColor(signal)}>{signal}</span>
							</div>
						))}
					</div>
				</div>
			</div>
		</div>
	);
};

// Price Indicators Component
const PriceIndicators = ({ indicators }: { indicators: Indicators }) => {
	// Select key indicators to display
	const keyIndicators = [
		{ name: "Close", key: "close" },
		{ name: "Open", key: "open" },
		{ name: "High", key: "high" },
		{ name: "Low", key: "low" },
		{ name: "RSI", key: "RSI" },
		{ name: "Volume", key: "volume" },
		{ name: "Change", key: "change", format: (value: number) => `${(value * 100).toFixed(2)}%` },
	];

	return (
		<div className="bg-gray-900 rounded-lg p-3 sm:p-4">
			<h3 className="text-lg sm:text-xl font-semibold mb-2 sm:mb-3">Key Price Indicators</h3>

			<div className="grid grid-cols-2 xs:grid-cols-3 sm:grid-cols-4 gap-2 sm:gap-3">
				{keyIndicators.map((indicator) => {
					if (indicators[indicator.key] === undefined) return null;

					const value = indicator.format
						? indicator.format(indicators[indicator.key])
						: indicators[indicator.key].toFixed(2);

					return (
						<div key={indicator.key} className="bg-gray-800 p-2 rounded">
							<div className="text-xs sm:text-sm text-gray-400">{indicator.name}</div>
							<div className="text-base sm:text-lg font-semibold truncate">
								{value}
							</div>
						</div>
					);
				})}
			</div>
		</div>
	);
};
