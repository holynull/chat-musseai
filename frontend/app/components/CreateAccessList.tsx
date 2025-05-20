"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { FC, useMemo } from "react";

export type CreateAccessListData = {
	accessList: Array<{
		address: string;
		storageKeys: string[];
	}>;
	gasUsed: string;
	network: string;
	network_type: string;
	tx_object: {
		from?: string;
		to?: string;
		data?: string;
		value?: string;
		gas?: string;
		gasPrice?: string;
	};
};

// Function to truncate address
const truncateAddress = (address: string, length = 6) => {
	if (!address) return '';
	if (address.length <= length * 2) return address;
	return `${address.substring(0, length)}...${address.substring(address.length - length)}`;
};

// Format hex to number
const formatHex = (hex: string): string => {
	if (!hex) return '0';
	try {
		return parseInt(hex, 16).toString();
	} catch (e) {
		return hex;
	}
};

// 创建一个独立的 React 组件来渲染内容
const CreateAccessListContent: FC<{ data: CreateAccessListData }> = ({ data }) => {
	// 将 useMemo 移到组件内部
	const networkInfo = useMemo(() => {
		const networkName = data.network.charAt(0).toUpperCase() + data.network.slice(1);
		const networkType = data.network_type.charAt(0).toUpperCase() + data.network_type.slice(1);
		return `${networkName} ${networkType}`;
	}, [data.network, data.network_type]);

	return (
		<div className="flex flex-col space-y-4 p-3 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto">
			<h2 className="text-xl sm:text-2xl font-bold text-center">Access List</h2>
			<div className="flex items-center justify-center">
				<span className="text-xs sm:text-sm text-blue-400">{networkInfo}</span>
			</div>

			<div className="grid gap-3 sm:gap-4">
				{/* Transaction Info Section */}
				<div className="mt-2 sm:mt-3">
					<h4 className="text-xs sm:text-sm font-medium text-white mb-2">Transaction Info</h4>
					<div className="bg-gray-900 rounded-lg p-3 space-y-2">
						{data.tx_object.from && (
							<div className="flex justify-between text-xs sm:text-sm">
								<span className="text-gray-400">From:</span>
								<span className="font-medium text-white truncate ml-2 max-w-[200px] sm:max-w-none">
									<span className="hidden sm:inline">{data.tx_object.from}</span>
									<span className="inline sm:hidden">{truncateAddress(data.tx_object.from)}</span>
								</span>
							</div>
						)}
						{data.tx_object.to && (
							<div className="flex justify-between text-xs sm:text-sm">
								<span className="text-gray-400">To:</span>
								<span className="font-medium text-white truncate ml-2 max-w-[200px] sm:max-w-none">
									<span className="hidden sm:inline">{data.tx_object.to}</span>
									<span className="inline sm:hidden">{truncateAddress(data.tx_object.to)}</span>
								</span>
							</div>
						)}
						{data.tx_object.value && (
							<div className="flex justify-between text-xs sm:text-sm">
								<span className="text-gray-400">Value:</span>
								<span className="font-medium text-white">{formatHex(data.tx_object.value)} Wei</span>
							</div>
						)}
						<div className="flex justify-between text-xs sm:text-sm">
							<span className="text-gray-400">Gas Used:</span>
							<span className="font-medium text-white">{formatHex(data.gasUsed)}</span>
						</div>
					</div>
				</div>

				{/* Access List Section */}
				<div className="mt-1 sm:mt-2">
					<h4 className="text-xs sm:text-sm font-medium text-white mb-2">
						Access List ({data.accessList.length} address{data.accessList.length !== 1 ? 'es' : ''})
					</h4>
					{data.accessList.length > 0 ? (
						<div className="space-y-2">
							{data.accessList.map((item, index) => (
								<div key={index} className="bg-gray-900 p-2 rounded-lg border border-gray-700">
									<div className="mb-1">
										<span className="text-xs font-medium text-gray-400">Address:</span>
										<div className="text-xs sm:text-sm font-medium text-white break-all">
											{item.address}
										</div>
									</div>
									{item.storageKeys.length > 0 && (
										<div>
											<span className="text-xs font-medium text-gray-400">
												Storage Keys ({item.storageKeys.length}):
											</span>
											<div className="mt-1 max-h-28 overflow-y-auto">
												{item.storageKeys.map((key, keyIndex) => (
													<div key={keyIndex} className="text-xxs sm:text-xs text-gray-300 break-all mb-1">
														{key}
													</div>
												))}
											</div>
										</div>
									)}
								</div>
							))}
						</div>
					) : (
						<div className="text-center py-4 text-gray-400 text-sm">No access list items</div>
					)}
				</div>

				{/* Help Text */}
				<div className="mt-1 text-xs text-gray-400 italic">
					<p>Access lists specify the storage addresses a transaction will access, helping optimize gas usage.</p>
				</div>
			</div>
		</div>
	);
};

// 导出 hook
export const useCreateAccessList = () => useAssistantToolUI({
	toolName: "eth_createAccessList",
	render: (input) => {
		const data: CreateAccessListData = input.args.data;
		if (!data) return null;
		return <CreateAccessListContent data={data} />;
	},
});
