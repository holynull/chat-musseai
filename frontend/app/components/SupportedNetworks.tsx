"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useState, useEffect, useMemo } from "react";

export type Network = {
	network: string;
	network_type: string;
	chain_id: number;
	name: string;
	symbol: string;
	explorer: string;
};

const NetworkCard = ({ network }: { network: Network }) => {
	return (
		<div className="flex flex-col p-3 bg-gray-900 rounded-lg hover:bg-gray-800 transition-colors duration-200">
			<div className="flex justify-between items-center mb-2">
				<h3 className="text-md font-semibold text-white">{network.name}</h3>
				<span className="text-xs bg-blue-500 text-white px-2 py-1 rounded-full">
					{network.network_type}
				</span>
			</div>
			<div className="text-xs text-gray-400 grid grid-cols-1 gap-1">
				<div className="flex justify-between">
					<span>Network:</span>
					<span className="text-white">{network.network}</span>
				</div>
				<div className="flex justify-between">
					<span>Chain ID:</span>
					<span className="text-white">{network.chain_id}</span>
				</div>
				<div className="flex justify-between">
					<span>Token:</span>
					<span className="text-white">{network.symbol}</span>
				</div>
				<div className="flex items-center justify-between truncate">
					<span>Explorer:</span>
					<a
						href={network.explorer}
						target="_blank"
						rel="noopener noreferrer"
						className="text-blue-400 hover:text-blue-300 transition-colors truncate ml-1 max-w-[150px]"
					>
						{network.explorer.replace(/^https:\/\//, '')}
					</a>
				</div>
			</div>
		</div>
	);
};

const NetworksDisplay = ({ data }: { data: Network[] }) => {
	// 使用useMemo优化网络数据初始化
	const networks = useMemo(() => data || [], [data]);

	// 使用useMemo优化网络分组计算
	const groupedNetworks = useMemo(() => {
		const groups: Record<string, Network[]> = {};
		networks.forEach(network => {
			if (!groups[network.network]) {
				groups[network.network] = [];
			}
			groups[network.network].push(network);
		});
		return groups;
	}, [networks]);

	// 使用useMemo优化网络类型分类
	const networkTypes = useMemo(() => {
		const types = new Set<string>();
		networks.forEach(network => types.add(network.network_type));
		return Array.from(types);
	}, [networks]);

	const [activeFilter, setActiveFilter] = useState<string | null>(null);
	const [searchTerm, setSearchTerm] = useState("");

	// 使用useMemo优化过滤后的网络列表
	const filteredNetworks = useMemo(() => {
		return networks.filter(network => {
			const matchesFilter = !activeFilter || network.network_type === activeFilter;
			const matchesSearch = !searchTerm ||
				network.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
				network.network.toLowerCase().includes(searchTerm.toLowerCase());
			return matchesFilter && matchesSearch;
		});
	}, [networks, activeFilter, searchTerm]);

	if (!networks || networks.length === 0) return null;

	return (
		<div className="flex flex-col space-y-4 p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full">
			<h2 className="text-xl font-bold text-center">Supported Networks</h2>

			<div className="flex flex-col sm:flex-row gap-2 justify-between">
				<div className="flex flex-wrap gap-2">
					<button
						className={`text-xs px-3 py-1 rounded-full transition-colors ${!activeFilter ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
						onClick={() => setActiveFilter(null)}
					>
						All
					</button>
					{networkTypes.map(type => (
						<button
							key={type}
							className={`text-xs px-3 py-1 rounded-full transition-colors ${activeFilter === type ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
							onClick={() => setActiveFilter(type)}
						>
							{type}
						</button>
					))}
				</div>

				<input
					type="text"
					placeholder="Search networks..."
					className="px-3 py-1 text-sm bg-gray-700 border border-gray-600 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
					value={searchTerm}
					onChange={(e) => setSearchTerm(e.target.value)}
				/>
			</div>

			<div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
				{filteredNetworks.map((network, index) => (
					<NetworkCard key={`${network.network}-${network.network_type}-${index}`} network={network} />
				))}
			</div>

			<div className="text-xs text-gray-400 text-center mt-2">
				Total Networks: {networks.length} | Filtered: {filteredNetworks.length}
			</div>
		</div>
	);
};

export const useSupportedNetworks = () => useAssistantToolUI({
	toolName: "get_supported_networks",
	render: (input) => <NetworksDisplay data={input.args.data} />,
});
