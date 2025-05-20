"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect, useMemo } from "react";

// 定义日志项目的类型接口
interface EventLog {
	blockNumber: number;
	transactionHash: string;
	logIndex: number;
	address: string;
	topics: string[];
	data: string;
}

// 定义工具结果的类型接口
interface EthGetLogsResult {
	events: EventLog[];
	contract_address: string;
	event_name: string;
	from_block: string | number;
	to_block: string | number;
	network: string;
	network_type: string;
}

interface EthGetLogsProps {
	data: EthGetLogsResult;
}

// 格式化地址函数 - 截断长地址以便于显示
const formatAddress = (address: string, length = 6): string => {
	if (!address) return '';
	if (address.length <= length * 2) return address;
	return `${address.substring(0, length)}...${address.substring(address.length - length)}`;
};

// 格式化十六进制为数字
const formatHexToNumber = (hex: string | number): number => {
	if (typeof hex === 'number') return hex;
	return parseInt(hex, 16);
};

// 创建独立的React组件
const EthGetLogsComponent: React.FC<EthGetLogsProps> = ({ data }) => {
	// 将所有Hooks移到组件顶部
	const [visibleEvents, setVisibleEvents] = useState<EventLog[]>([]);
	const [showAll, setShowAll] = useState(false);

	// 计算事件总数
	const totalEvents = useMemo(() => (data?.events?.length || 0), [data]);

	// 当showAll状态或数据改变时更新可见事件
	useEffect(() => {
		if (data?.events) {
			setVisibleEvents(showAll ? data.events : data.events.slice(0, 5));
		}
	}, [showAll, data]);

	// 如果没有数据，返回空
	if (!data || !data.events) {
		return null;
	}

	// 提取网络信息并格式化
	const networkInfo = `${data.network_type === 'mainnet' ? '' : `${data.network_type} `}${data.network}`;

	// 计算区块范围
	const fromBlock = typeof data.from_block === 'string' && data.from_block === 'earliest'
		? 'earliest'
		: formatHexToNumber(data.from_block);

	const toBlock = typeof data.to_block === 'string' && data.to_block === 'latest'
		? 'latest'
		: formatHexToNumber(data.to_block);

	return (
		<div className="flex flex-col space-y-4 p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto">
			<h2 className="text-xl sm:text-2xl font-bold text-center">Contract Events</h2>

			{/* 查询信息摘要 */}
			<div className="bg-gray-900 p-3 rounded-lg">
				<div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
					<div className="flex justify-between">
						<span className="text-gray-400">Contract:</span>
						<a
							href={`https://${data.network_type === 'mainnet' ? '' : `${data.network_type}.`}${data.network}scan.io/address/${data.contract_address}`}
							target="_blank"
							rel="noopener noreferrer"
							className="font-medium text-blue-400 hover:underline"
						>
							<span className="hidden sm:inline">{data.contract_address}</span>
							<span className="inline sm:hidden">{formatAddress(data.contract_address)}</span>
						</a>
					</div>
					<div className="flex justify-between">
						<span className="text-gray-400">Event:</span>
						<span className="font-medium text-white">{data.event_name}</span>
					</div>
					<div className="flex justify-between">
						<span className="text-gray-400">Network:</span>
						<span className="font-medium text-white capitalize">{networkInfo}</span>
					</div>
					<div className="flex justify-between">
						<span className="text-gray-400">Block Range:</span>
						<span className="font-medium text-white">
							{fromBlock} to {toBlock}
						</span>
					</div>
					<div className="flex justify-between">
						<span className="text-gray-400">Events Found:</span>
						<span className="font-medium text-white">{totalEvents}</span>
					</div>
				</div>
			</div>

			{/* 事件列表 */}
			{totalEvents > 0 ? (
				<div className="mt-2">
					<h3 className="text-md font-medium mb-2">Event Logs</h3>
					<div className="space-y-3">
						{visibleEvents.map((event, index) => (
							<div key={`${event.blockNumber}-${event.logIndex}`} className="bg-gray-900 p-3 rounded border border-gray-700 hover:border-gray-500 transition-colors">
								<div className="grid grid-cols-1 sm:grid-cols-2 gap-1 text-xs">
									<div className="flex justify-between">
										<span className="text-gray-400">Block:</span>
										<span className="font-medium text-white">{event.blockNumber}</span>
									</div>
									<div className="flex justify-between">
										<span className="text-gray-400">Log Index:</span>
										<span className="font-medium text-white">{event.logIndex}</span>
									</div>
									<div className="flex justify-between col-span-1 sm:col-span-2">
										<span className="text-gray-400">Transaction:</span>
										<a
											href={`https://${data.network_type === 'mainnet' ? '' : `${data.network_type}.`}${data.network}scan.io/tx/${event.transactionHash}`}
											target="_blank"
											rel="noopener noreferrer"
											className="font-medium text-blue-400 hover:underline"
										>
											<span className="hidden sm:inline">{event.transactionHash}</span>
											<span className="inline sm:hidden">{formatAddress(event.transactionHash, 10)}</span>
										</a>
									</div>

									{/* 主题 (topics) */}
									<div className="col-span-1 sm:col-span-2 mt-1">
										<div className="text-gray-400 mb-1">Topics:</div>
										<div className="pl-2 space-y-1">
											{event.topics.map((topic, i) => (
												<div key={i} className="text-white font-mono text-xs overflow-hidden text-ellipsis">
													{i}: {topic}
												</div>
											))}
										</div>
									</div>

									{/* 数据段 */}
									{event.data && event.data !== '0x' && (
										<div className="col-span-1 sm:col-span-2 mt-1">
											<div className="text-gray-400 mb-1">Data:</div>
											<div className="pl-2 text-white font-mono text-xs break-all">
												{event.data}
											</div>
										</div>
									)}
								</div>
							</div>
						))}
					</div>

					{/* 显示更多/收起按钮 */}
					{totalEvents > 5 && (
						<button
							className="mt-3 w-full py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm font-medium transition-colors"
							onClick={() => setShowAll(!showAll)}
						>
							{showAll ? 'Show Less' : `Show All (${totalEvents})`}
						</button>
					)}
				</div>
			) : (
				<div className="text-center py-4 text-gray-400">No events found for the specified criteria</div>
			)}
		</div>
	);
};

// 导出hook
export const useEthGetLogs = () => useAssistantToolUI({
	toolName: "eth_getLogs",
	render: (input) => <EthGetLogsComponent data={input.args.data} />,
});
