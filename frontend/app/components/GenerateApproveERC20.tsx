"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import { useAppKitProvider, useAppKitAccount, useAppKitNetwork, useAppKit } from "@reown/appkit/react";
import { ethers } from 'ethers';
import UniversalProvider from '@walletconnect/universal-provider';
import { useState } from "react";
import { Button, useToast } from '@chakra-ui/react';
import { mainnet, bsc, tron, arbitrum, sepolia, solana } from '@reown/appkit/networks';
import type { AppKitNetwork } from '@reown/appkit-common';
import { wcModal, networks } from "../contexts/appkit";
import { CopyIcon, CheckIcon } from "@chakra-ui/icons"; // 或使用其他图标库

// Transaction interface type
export type ApproveERC20Transaction = {
	to: string;
	data: string;
	value: string;
	gasLimit: string;
	gasPrice: string;
};

// Helper function to shorten addresses for display
const shortenAddress = (address: string) => {
	return address ? `${address.substring(0, 6)}...${address.substring(address.length - 4)}` : '';
};

// Toast notification helper function
const showToast = (toast: any, title: string, description: string, status: 'info' | 'warning' | 'success' | 'error', duration: number | null = 5000) => {
	toast.closeAll();
	toast({
		title,
		description,
		status,
		duration,
		isClosable: true,
		position: 'top'
	});
};

export const useGenerateApproveERC20 = () => useAssistantToolUI({
	toolName: "generate_approve_erc20",
	render: (input) => {
		// 将render函数改为组件调用
		return <ApproveERC20Component input={input} />;
	},
});

// 创建独立的React组件
const ApproveERC20Component = ({ input }: { input: any }) => {
	const { txData, name, orderInfo, tx_detail } = input.args;

	const [isLoading, setLoading] = useState<boolean>(false);
	const toast = useToast();

	const { address, isConnected } = useAppKitAccount();
	const { walletProvider } = useAppKitProvider('eip155');
	const { caipNetwork, chainId, switchNetwork } = useAppKitNetwork();
	const { open } = useAppKit();

	const networks: [AppKitNetwork, ...AppKitNetwork[]] = [mainnet, bsc, tron, arbitrum, sepolia, solana];

	// Extract key information from transaction data
	const extractApprovalInfo = () => {
		// Extract token information
		const tokenName = tx_detail?.symbol || "Unknown Token";
		const tokenSymbol = tx_detail?.symbol || "";

		// Extract spender information
		const spender = tx_detail?.spender_address || txData?.to || "";
		const spenderName = tx_detail?.spenderName || "Unknown Contract";
		const decimals = tx_detail?.decimals || 1;

		// Extract approval amount
		const amount = tx_detail?.amount || 0;
		const formattedAmount = parseFloat(amount) / Math.pow(10, parseInt(decimals));

		// Extract network information
		const networkName = networks.find(n => n.id === chainId)?.name || "Unknown Network";

		return {
			tokenName,
			tokenSymbol,
			spender,
			spenderName,
			formattedAmount,
			networkName
		};
	};

	const approvalInfo = extractApprovalInfo();

	const signAndSendTransaction = async () => {
		if (isLoading) return;

		setLoading(true);

		if (!caipNetwork || !chainId) {
			showToast(
				toast,
				'Network Error',
				'No blockchain network connected. Please connect to a network first.',
				'error'
			);
			setLoading(false);
			return;
		}

		// Check wallet connection
		if (!isConnected) {
			showToast(
				toast,
				'Wallet Connection',
				'Please connect your wallet and try again.',
				'warning'
			);
			await open({ view: "Connect" });
			setLoading(false);
			return;
		}

		try {
			// Switch to correct network
			if (chainId) {
				// 直接判断当前网络是否匹配
				const currentNetwork = networks.find(network => network.id === chainId);
				if (!currentNetwork) {
					showToast(toast, "Network Error", "The required network is not supported.", "error");
					setLoading(false);
					return;
				}
			} else {
				// 没有chainId时显示错误
				showToast(toast, "Network Error", "No network selected.", "error");
				setLoading(false);
				return;
			}

			// Setup provider and signer
			const provider = new ethers.providers.Web3Provider(walletProvider as UniversalProvider);
			const signer = provider.getSigner(address);

			// Prepare transaction data
			let _v = txData.value.indexOf('0x') === 0 ? txData.value : '0x' + txData.value;
			let _d = txData.data.indexOf('0x') === 0 ? txData.data : '0x' + txData.data;

			const transaction = {
				from: address,
				to: txData.to,
				data: _d,
				value: _v,
				gasLimit: txData.gasLimit,
				gasPrice: txData.gasPrice,
				chainId: chainId as number,
			};

			showToast(
				toast,
				"Confirm Transaction",
				'Please confirm the transaction in your wallet.',
				'warning',
				null
			);
			try {
				const _network = await provider.getNetwork()
			} catch (e: any) {
				await wcModal.disconnect()
				await open({ view: "Connect" });
				console.error(e)
				showToast(
					toast,
					'Network Error. Please Connect your wallet again.',
					e?.message,
					'error'
				);
				return;
			}
			// Send transaction
			const tx = await signer.sendTransaction(transaction);

			if (tx && name === 'Send Swap Transaction') {
				console.log('Transaction hash:', tx.hash);
				showToast(toast, 'Transaction Sent', 'Transaction successfully sent.', 'success');

				// Generate order record after transaction is sent
				try {
					await fetch(process.env.NEXT_PUBLIC_API_URL + '/generate_swap_order', {
						method: 'POST',
						headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem("auth_token")}` },
						body: JSON.stringify({
							hash: tx.hash,
							from_token_address: orderInfo.from_token_address,
							to_token_address: orderInfo.to_token_address,
							from_address: orderInfo.from_address,
							to_address: orderInfo.to_address,
							from_token_chain: orderInfo.from_token_chain,
							to_token_chain: orderInfo.to_token_chain,
							from_token_amount: orderInfo.from_token_amount,
							amount_out_min: orderInfo.amount_out_min,
							from_coin_code: orderInfo.from_coin_code,
							to_coin_code: orderInfo.to_coin_code,
							source_type: orderInfo.source_type,
							slippage: orderInfo.slippage
						})
					});

					showToast(toast, 'Order Update', 'Order successfully updated.', 'success');
				} catch (error: any) {
					showToast(
						toast,
						'Order Update Failed',
						error?.message || 'Failed to update order.',
						'error'
					);
					console.error('Error generating swap order:', error);
				}
			} else {
				showToast(toast, 'Approval Sent', 'Approval transaction successfully sent.', 'success');
			}

			console.log('Transaction hash:', tx.hash);
		} catch (e: any) {
			showToast(
				toast,
				'Transaction Failed',
				e?.message || 'Failed to process transaction.',
				'error'
			);
			console.error('Transaction error:', e);
		} finally {
			setLoading(false);
		}
	};
	const [copySuccess, setCopySuccess] = useState(false);

	const copyToClipboard = (text: string) => {
		navigator.clipboard.writeText(text)
			.then(() => {
				setCopySuccess(true);
				showToast(toast, 'Copied!', 'Address copied to clipboard', 'success', 2000);
				setTimeout(() => setCopySuccess(false), 2000);
			})
			.catch(err => {
				console.error('Failed to copy: ', err);
				showToast(toast, 'Copy Failed', 'Failed to copy address', 'error');
			});
	};
	return txData && (
		<div className="rounded-lg border border-gray-200 overflow-hidden bg-white shadow-sm sm:mt-6 md:mt-8">
			{/* Header */}
			<div className="p-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
				<div className="flex items-center justify-between">
					<h3 className="text-lg font-semibold text-gray-900">
						{approvalInfo.tokenSymbol ? `${approvalInfo.tokenSymbol} Token Approval` : "Token Approval"}
					</h3>
				</div>
			</div>

			{/* Approval explanation */}
			<div className="p-4 bg-blue-100 border-b border-blue-200">
				<p className="text-sm text-blue-900">
					<span className="font-semibold text-blue-950">About this approval:</span> You are authorizing a smart contract to access your
					{approvalInfo.tokenSymbol ? ` ${approvalInfo.tokenSymbol} ` : " "}
					tokens. This is a required step for subsequent operations like swapping or staking.
				</p>
			</div>

			<div className="p-4">
				<div className="grid gap-4">
					{/* Transaction details section */}
					<div className="mt-2">
						<h4 className="text-sm font-semibold text-gray-900 mb-3">Approval Details</h4>

						<div className="bg-gray-50 p-4 rounded-md border border-gray-200">
							<div className="space-y-3">
								<div className="flex justify-between border-b border-gray-200 pb-2">
									<span className="text-gray-700 font-medium">Token</span>
									<span className="font-semibold text-gray-900">{approvalInfo.tokenName}</span>
								</div>

								<div className="flex justify-between border-b border-gray-200 pb-2">
									<span className="text-gray-700 font-medium">Spender</span>
									<div className="flex flex-col items-end">
										<span className="block text-sm text-gray-900">{approvalInfo.spenderName}</span>
										<div className="flex items-center">
											<span className="text-xs text-gray-500 mr-2">{shortenAddress(approvalInfo.spender)}</span>
											<button
												onClick={() => copyToClipboard(approvalInfo.spender)}
												className="text-gray-500 hover:text-blue-600 transition-colors"
												title="Copy full address"
											>
												{copySuccess ?
													<CheckIcon className="h-4 w-4 text-green-500" /> :
													<CopyIcon className="h-4 w-4" />
												}
											</button>
										</div>
									</div>
								</div>

								<div className="flex justify-between border-b border-gray-200 pb-2">
									<span className="text-gray-700 font-medium">Amount</span>
									<span className="font-medium">
										{String(approvalInfo.formattedAmount) === "1.157920892373162e+59" ? (
											<span className="text-red-600 font-semibold">Unlimited</span>
										) : (
											<span className="text-gray-900">{approvalInfo.formattedAmount}</span>
										)} <span className="text-gray-900">{approvalInfo.tokenSymbol}</span>
									</span>
								</div>

								<div className="flex justify-between">
									<span className="text-gray-700 font-medium">Network</span>
									<span className="font-semibold text-gray-900">{approvalInfo.networkName}</span>
								</div>
							</div>
						</div>
					</div>

					{/* Security reminders */}
					<div className="bg-amber-100 p-4 rounded-md text-sm text-amber-900 mt-4 border border-amber-200">
						<p className="font-semibold mb-2">Security Reminders:</p>
						<ul className="list-disc pl-5 space-y-2">
							<li className="text-amber-900">Verify that you trust the contract requesting approval</li>
							<li className="text-amber-900 font-medium">
								Be cautious with &quot;<span className="text-red-600">Unlimited</span>&quot; approvals - consider approving only the needed amount
							</li>
							<li className="text-amber-900">You can revoke this approval at any time after the transaction</li>
						</ul>
					</div>

					{/* Action button */}
					<div className="mt-6">
						<Button
							onClick={signAndSendTransaction}
							isDisabled={isLoading}
							colorScheme="blue"
							size="md"
							className="w-full px-6 py-3 bg-blue-700 hover:bg-blue-800 text-white font-semibold rounded-md transition-colors duration-200 shadow-sm"
						>
							{isLoading ? "Processing..." : `Approve ${approvalInfo.tokenSymbol}`}
						</Button>

						<div className="text-xs text-gray-600 mt-2 text-center">
							Click the button to confirm this approval in your wallet
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};