"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect, useCallback } from "react";

export type EthMethodCallResult = {
	result: any;
	method: string;
	network: string;
	network_type: string;
};

export const useCallEthMethod = () => useAssistantToolUI({
	toolName: "call_eth_method",
	render: (input) => {
		const data: EthMethodCallResult = input.args.data;

		if (!data) return null;

		// 格式化 JSON 数据
		const formatJson = (jsonData: any) => {
			try {
				if (typeof jsonData === 'string') {
					// 尝试解析 JSON 字符串
					return JSON.stringify(JSON.parse(jsonData), null, 2);
				}
				return JSON.stringify(jsonData, null, 2);
			} catch (e) {
				// 如果不是有效的 JSON，则原样返回
				return typeof jsonData === 'object' ? JSON.stringify(jsonData, null, 2) : jsonData;
			}
		};

		// 格式化十六进制数值
		const formatHexValue = (value: string) => {
			if (typeof value !== 'string' || !value.startsWith('0x')) {
				return value;
			}

			try {
				const decimal = parseInt(value, 16);
				return `${value} (${decimal.toLocaleString()})`;
			} catch (e) {
				return value;
			}
		};

		// 自定义渲染不同类型的结果
		const renderResult = (result: any) => {
			if (result === null || result === undefined) {
				return <span className="text-gray-400">null</span>;
			}

			if (typeof result === 'string') {
				if (result.startsWith('0x')) {
					return <span>{formatHexValue(result)}</span>;
				}
				return <span>{result}</span>;
			}

			if (typeof result === 'object') {
				return (
					<pre className="bg-gray-900 p-2 rounded-md overflow-x-auto text-xs sm:text-sm whitespace-pre-wrap">
						{formatJson(result)}
					</pre>
				);
			}

			return <span>{String(result)}</span>;
		};

		return (
			<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto">
				<h2 className="text-xl sm:text-2xl font-bold text-center">Ethereum RPC Call Result</h2>

				<div className="grid gap-3 sm:gap-4">
					<div className="bg-gray-900 p-3 rounded-lg">
						<div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 mb-2">
							<div className="flex items-center gap-2">
								<span className="text-blue-400 font-medium">Method:</span>
								<span className="font-mono bg-gray-700 px-2 py-1 rounded text-sm">{data.method}</span>
							</div>
							<div className="flex items-center gap-2">
								<span className="text-blue-400 font-medium">Network:</span>
								<span className="font-medium">{data.network} ({data.network_type})</span>
							</div>
						</div>

						<div className="mt-4">
							<h3 className="text-md font-medium text-blue-400 mb-2">Result:</h3>
							<div className="bg-gray-800 p-3 rounded-lg">
								{renderResult(data.result)}
							</div>
						</div>
					</div>
				</div>
			</div>
		);
	},
});
