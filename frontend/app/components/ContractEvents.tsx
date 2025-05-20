"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect, useMemo } from "react";

export type ContractEvent = {
	blockNumber: number;
	transactionHash: string;
	logIndex: number;
	address: string;
	topics: string[];
	data: string;
};

export type ContractEventsData = {
	events: ContractEvent[];
	contract_address: string;
	event_name: string;
	from_block: number | string;
	to_block: number | string;
	network: string;
	network_type: string;
};

// 格式化地址或交易哈希函数
const formatHash = (hash: string, length = 8): string => {
	if (!hash) return '';
	if (hash.length <= length * 2) return hash;
	return `${hash.substring(0, length)}...${hash.substring(hash.length - length)}`;
};

// 格式化事件主题数据
const formatTopicData = (topic: string): string => {
	if (!topic) return '';
	return formatHash(topic);
};

// 格式化事件数据
const formatEventData = (data: string): string => {
	if (!data) return 'No data';
	if (data === '0x') return 'Empty data';
	return formatHash(data, 10);
};

// 创建一个 ContractEventsComponent 组件来处理渲染
const ContractEventsComponent = ({ data }: { data: ContractEventsData }) => {
	// 使用useMemo优化事件列表的处理
	const formattedEvents = useMemo(() => {
		return data.events.map((event, index) => ({
			...event,
			formattedAddress: formatHash(event.address),
			formattedTxHash: formatHash(event.transactionHash),
			formattedTopics: event.topics.map(formatTopicData),
			formattedData: formatEventData(event.data),
			key: `${event.transactionHash}-${event.logIndex}-${index}`
		}));
	}, [data.events]);

	// 统计信息
	const stats = useMemo(() => ({
		totalEvents: data.events.length,
		blockRange: typeof data.from_block === 'string' && typeof data.to_block === 'string'
			? `${data.from_block} to ${data.to_block}`
			: `${data.from_block} to ${data.to_block}`,
		network: `${data.network} (${data.network_type})`
	}), [data.events.length, data.from_block, data.to_block, data.network, data.network_type]);

	// 展示事件列表的限制数量
	const [displayLimit, setDisplayLimit] = useState(5);

	// 处理"显示更多"按钮点击
	const handleShowMore = () => {
		setDisplayLimit(prev => prev + 10);
	};

	// 获取要显示的事件
	const eventsToDisplay = useMemo(() => {
		return formattedEvents.slice(0, displayLimit);
	}, [formattedEvents, displayLimit]);

	return (
		<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto">
			<h2 className="text-xl sm:text-2xl font-bold text-center">Contract Events</h2>

			{/* 合约和事件信息 */}
			<div className="bg-gray-900 p-3 rounded-lg">
				<div className="flex flex-col sm:flex-row justify-between items-start gap-2">
					<div>
						<p className="text-xs sm:text-sm text-gray-400">Contract Address</p>
						<p className="text-sm sm:text-base text-white break-all">
							{formatHash(data.contract_address, 12)}
						</p>
					</div>
					<div>
						<p className="text-xs sm:text-sm text-gray-400">Event Name</p>
						<p className="text-sm sm:text-base text-white">
							{data.event_name}
						</p>
					</div>
					<div>
						<p className="text-xs sm:text-sm text-gray-400">Network</p>
						<p className="text-sm sm:text-base text-white">
							{stats.network}
						</p>
					</div>
				</div>
			</div>

			{/* 统计信息 */}
			<div className="grid grid-cols-3 gap-2 text-center">
				<div className="bg-gray-900 p-2 rounded-lg">
					<p className="text-xs text-gray-400">Total Events</p>
					<p className="text-lg font-semibold">{stats.totalEvents}</p>
				</div>
				<div className="bg-gray-900 p-2 rounded-lg">
					<p className="text-xs text-gray-400">Block Range</p>
					<p className="text-sm font-semibold">{stats.blockRange}</p>
				</div>
				<div className="bg-gray-900 p-2 rounded-lg">
					<p className="text-xs text-gray-400">Displayed</p>
					<p className="text-lg font-semibold">{Math.min(displayLimit, stats.totalEvents)}/{stats.totalEvents}</p>
				</div>
			</div>

			{/* 事件列表 */}
			{eventsToDisplay.length > 0 ? (
				<div className="overflow-x-auto">
					<table className="min-w-full divide-y divide-gray-700">
						<thead className="bg-gray-900">
							<tr>
								<th scope="col" className="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Block #</th>
								<th scope="col" className="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Tx Hash</th>
								<th scope="col" className="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Log Index</th>
								<th scope="col" className="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Topics</th>
								<th scope="col" className="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Data</th>
							</tr>
						</thead>
						<tbody className="bg-gray-800 divide-y divide-gray-700">
							{eventsToDisplay.map((event) => (
								<tr key={event.key} className="hover:bg-gray-700 transition-colors duration-150">
									<td className="px-3 py-2 whitespace-nowrap text-sm text-white">{event.blockNumber}</td>
									<td className="px-3 py-2 whitespace-nowrap text-sm text-blue-400 hover:text-blue-300">
										<a href={`https://etherscan.io/tx/${event.transactionHash}`} target="_blank" rel="noopener noreferrer" className="hover:underline">
											{event.formattedTxHash}
										</a>
									</td>
									<td className="px-3 py-2 whitespace-nowrap text-sm text-white">{event.logIndex}</td>
									<td className="px-3 py-2 text-sm text-gray-300">
										<div className="max-h-20 overflow-y-auto">
											{event.formattedTopics.map((topic, idx) => (
												<div key={idx} className="text-xs truncate mb-1">
													<span className="text-gray-400">{idx}:</span> {topic}
												</div>
											))}
										</div>
									</td>
									<td className="px-3 py-2 text-sm text-gray-300">
										<div className="text-xs truncate max-w-[150px]" title={event.data}>
											{event.formattedData}
										</div>
									</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
			) : (
				<div className="text-center p-4 bg-gray-900 rounded-lg">
					<p className="text-gray-400">No events found</p>
				</div>
			)}

			{/* 显示更多按钮 */}
			{displayLimit < formattedEvents.length && (
				<button
					onClick={handleShowMore}
					className="mt-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors duration-150 self-center"
				>
					Show More Events
				</button>
			)}
		</div>
	);
};

// 导出 useContractEvents Hook
export const useContractEvents = () => useAssistantToolUI({
	toolName: "get_contract_events",
	render: (input) => {
		const data: ContractEventsData = input.args.data;
		if (!data) return null;
		return <ContractEventsComponent data={data} />;
	},
});
