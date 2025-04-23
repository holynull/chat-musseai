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
			<div className="flex flex-col space-y-6 p-4 rounded-lg border border-gray-700 bg-gray-800 text-white max-w-3xl sm:mt-6 md:mt-8">
				<h2 className="text-2xl font-bold text-center">Technical Analysis Signals</h2>

				{/* Summary Recommendation */}
				<RecommendationCard
					title="Summary"
					recommendation={responseData.summary.RECOMMENDATION}
					buyCount={responseData.summary.BUY}
					sellCount={responseData.summary.SELL}
					neutralCount={responseData.summary.NEUTRAL}
				/>

				<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
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
		<div className="bg-gray-900 rounded-lg p-4">
			<h3 className="text-xl font-semibold mb-3">{title}</h3>
			<div className="flex items-center justify-center mb-4">
				<span className={`text-3xl font-bold ${getRecommendationColor(recommendation)}`}>
					{recommendation}
				</span>
			</div>

			<div className="flex justify-between text-sm mb-2">
				<span>Buy Signals: {buyCount}</span>
				<span>Sell Signals: {sellCount}</span>
				<span>Neutral: {neutralCount}</span>
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

	return (
		<div className="bg-gray-900 rounded-lg p-4">
			<h3 className="text-xl font-semibold mb-2">{title}</h3>
			<div className="flex items-center mb-3">
				<span className="mr-2">Recommendation:</span>
				<span className={`font-bold ${getSignalColor(recommendation)}`}>
					{recommendation}
				</span>
			</div>

			<div className="flex justify-between text-sm mb-3">
				<div className="text-green-500">Buy: {buyCount}</div>
				<div className="text-red-500">Sell: {sellCount}</div>
				<div className="text-yellow-500">Neutral: {neutralCount}</div>
			</div>

			<div className="mt-3">
				<h4 className="text-sm font-semibold mb-2">Detailed Indicators:</h4>
				<div className="grid grid-cols-2 gap-2">
					{Object.entries(computeData).map(([indicator, signal]) => (
						<div key={indicator} className="flex justify-between text-xs border-b border-gray-700 py-1">
							<span>{indicator}:</span>
							<span className={getSignalColor(signal)}>{signal}</span>
						</div>
					))}
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
		<div className="bg-gray-900 rounded-lg p-4">
			<h3 className="text-xl font-semibold mb-3">Key Price Indicators</h3>

			<div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
				{keyIndicators.map((indicator) => {
					if (indicators[indicator.key] === undefined) return null;

					const value = indicator.format
						? indicator.format(indicators[indicator.key])
						: indicators[indicator.key].toFixed(2);

					return (
						<div key={indicator.key} className="bg-gray-800 p-2 rounded">
							<div className="text-sm text-gray-400">{indicator.name}</div>
							<div className="text-lg font-semibold">
								{value}
							</div>
						</div>
					);
				})}
			</div>
		</div>
	);
};