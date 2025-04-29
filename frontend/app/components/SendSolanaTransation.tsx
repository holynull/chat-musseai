"use client";
import { useAppKitProvider, useAppKitAccount, useAppKitNetwork, useAppKit } from "@reown/appkit/react"
import { useAssistantToolUI } from "@assistant-ui/react";
import type { Provider } from '@reown/appkit-adapter-solana'
import { useState } from "react";
import { Button, useToast } from '@chakra-ui/react'
import { CopyIcon, CheckIcon, ExternalLinkIcon } from "@chakra-ui/icons"
import { mainnet, bsc, tron, arbitrum, sepolia, solana, solanaTestnet, solanaDevnet } from '@reown/appkit/networks'
import type { AppKitNetwork } from '@reown/appkit-common';
import { wcModal } from "../contexts/appkit";
import {
	SystemProgram,
	PublicKey,
	Keypair,
	Transaction,
	TransactionInstruction,
	LAMPORTS_PER_SOL
} from '@solana/web3.js'
import { useAppKitConnection } from "@reown/appkit-adapter-solana/react";

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

// Format number with proper decimals
const formatNumber = (value: number | string, decimals: number = 6): string => {
	const num = typeof value === 'string' ? parseFloat(value) : value;
	if (isNaN(num)) return '0';

	return num.toLocaleString('en-US', {
		minimumFractionDigits: 2,
		maximumFractionDigits: decimals
	});
};

export const useSendSolanaTransaction = () => useAssistantToolUI({
	toolName: "send_solana_transaction",
	render: (input) => <SolanaTransactionComponent input={input} />,
});

// 创建独立的React组件
const SolanaTransactionComponent = ({ input }: { input: any }) => {
	// 将hooks移到组件顶层
	const { walletProvider } = useAppKitProvider<Provider>('solana')
	const { connection } = useAppKitConnection()
	const { open } = useAppKit();
	const { address, isConnected } = useAppKitAccount()
	const { caipNetwork } = useAppKitNetwork();
	const [isLoading, setLoading] = useState<boolean>(false);
	const toast = useToast();
	const { txData, name, orderInfo, tx_detail } = input.args;
	const [copySuccess, setCopySuccess] = useState(false);
	const [showRawData, setShowRawData] = useState(false);
	// 新增状态用于移动端的详情展开/折叠
	const [showDetails, setShowDetails] = useState(true);
	const networks: AppKitNetwork[] = [solana, solanaDevnet, solanaTestnet];

	// Extract transaction info from tx_detail
	const extractTransactionInfo = () => {
		try {
			// Parse tx_detail if it's a string
			const txDetailObj = typeof tx_detail === 'string' ? JSON.parse(tx_detail) : tx_detail;

			// Get basic transaction information
			const fromToken = txDetailObj?.from_token_symbol || "SOL";
			const toToken = txDetailObj?.to_token_symbol || "Unknown";
			const fromAmount = txDetailObj?.from_token_amount || "0";
			const toAmount = txDetailObj?.amount_out_min || txDetailObj?.to_token_amount || "0";
			const fromDecimals = txDetailObj?.from_token_decimals || 9;  // SOL uses 9 decimals
			const toDecimals = txDetailObj?.to_token_decimals || 9;

			// Format the amounts with proper decimals
			const formattedFromAmount = parseFloat(fromAmount) / Math.pow(10, parseInt(fromDecimals.toString()));
			const formattedToAmount = parseFloat(toAmount) / Math.pow(10, parseInt(toDecimals.toString()));

			// Get addresses
			const fromAddress = txDetailObj?.from_address || address || "";
			const toAddress = txDetailObj?.to_address || (txData?.tx && txData.tx[0]?.keys?.[0]?.pubkey) || "";

			// Get network information
			const networkName = "Solana";
			const networkIcon = getNetworkIcon(networkName);

			// Get other transaction details
			const slippage = txDetailObj?.slippage || "0.5";
			const sourceType = txDetailObj?.source_type || "Unknown";

			// Get exchange rate
			const exchangeRate = formattedFromAmount > 0 ? formattedToAmount / formattedFromAmount : 0;

			return {
				fromToken,
				toToken,
				fromAmount: formattedFromAmount,
				toAmount: formattedToAmount,
				fromAddress,
				toAddress,
				networkName,
				networkIcon,
				slippage,
				sourceType,
				exchangeRate,
				rawData: txDetailObj
			};
		} catch (error) {
			console.error("Error parsing transaction details:", error);
			return {
				fromToken: "SOL",
				toToken: "Unknown",
				fromAmount: 0,
				toAmount: 0,
				fromAddress: address || "",
				toAddress: (txData?.tx && txData.tx[0]?.keys?.[0]?.pubkey) || "",
				networkName: "Solana",
				networkIcon: getNetworkIcon("Solana"),
				slippage: "0.5",
				sourceType: "Unknown",
				exchangeRate: 0,
				rawData: null
			};
		}
	};

	// Helper function to get network icon
	const getNetworkIcon = (networkName: string) => {
		switch (networkName.toLowerCase()) {
			case 'ethereum':
			case 'mainnet':
				return '🔷';
			case 'bsc':
			case 'binance smart chain':
				return '🟡';
			case 'arbitrum':
				return '🔵';
			case 'solana':
				return '🟣';
			default:
				return '🌐';
		}
	};

	const transactionInfo = extractTransactionInfo();

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

	// 用于移动端的详情切换函数
	const toggleDetails = () => {
		setShowDetails(!showDetails);
	};

	const signAndSendTransaction = async () => {
		if (isLoading) return;

		setLoading(true);

		if (!connection) {
			showToast(
				toast,
				'Connection Error',
				'No connection to Solana network. Please try again.',
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
			// Switch to Solana network if needed
			const solanaNetwork = networks.find(n => n.id === 'solana');
			if (solanaNetwork && caipNetwork?.id !== solanaNetwork.id) {
				try {
					await wcModal.switchNetwork(solanaNetwork);
				} catch (e) {
					console.error("Failed to switch to Solana network:", e);
					showToast(
						toast,
						'Network Switch Failed',
						'Failed to switch to Solana network.',
						'error'
					);
					setLoading(false);
					return;
				}
			}

			// Create Transaction instance
			const transaction = new Transaction();

			// Add transaction instructions
			for (const instruction of txData.tx) {
				// Process account keys
				const keys = instruction.keys.map((key: any) => ({
					pubkey: new PublicKey(key.pubkey),
					isSigner: key.isSigner,
					isWritable: key.isWritable
				}));

				// Convert programId
				const programId = new PublicKey(instruction.programId);

				// Convert data to Buffer
				const data = Buffer.from(instruction.data);

				// Create TransactionInstruction
				const txInstruction = new TransactionInstruction({
					keys,
					programId,
					data
				});

				// Add instruction to Transaction
				transaction.add(txInstruction);
			}

			// Get latest blockhash and set transaction properties
			const { blockhash } = await connection.getLatestBlockhash();
			transaction.recentBlockhash = blockhash;
			transaction.feePayer = new PublicKey(address as any);

			// Add signer if provided
			if (txData.signer) {
				const privateKey = Uint8Array.from(txData.signer);
				const signer = Keypair.fromSecretKey(privateKey);
				transaction.sign(signer);
			}

			// Show wallet confirmation toast
			showToast(
				toast,
				"Confirm Transaction",
				'Please confirm the transaction in your wallet.',
				'warning',
				null
			);

			// Send transaction
			const signedTx = await walletProvider.sendTransaction(transaction, connection);

			// Show success message
			showToast(toast, 'Transaction Sent', 'Transaction successfully sent.', 'success');

			if (signedTx) {
				const hash = signedTx;
				console.log('Transaction hash:', hash);

				// Generate order record after transaction is sent
				if (name === 'Send Swap Transaction' && orderInfo) {
					try {
						await fetch(process.env.NEXT_PUBLIC_API_URL + '/api/generate_swap_order', {
							method: 'POST',
							headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem("auth_token")}` },
							body: JSON.stringify({
								hash: hash,
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
				}
			}
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

	return txData && (
		<div className="flex flex-col space-y-3 p-2 sm:p-4 rounded-lg border border-gray-700 bg-gray-800 text-white w-full max-w-full sm:max-w-3xl mx-auto">
			{/* Header */}
			<div className="p-3 sm:p-4 border-b border-gray-700 bg-gray-900 rounded-t-lg">
				<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
					<h3 className="text-lg sm:text-xl font-semibold text-white">
						{name || "Send Solana Transaction"}
					</h3>
					<div className="text-xs sm:text-sm font-medium text-blue-400 px-2 py-1 bg-gray-700 rounded-full self-start sm:self-auto">
						{transactionInfo.networkIcon} {transactionInfo.networkName}
					</div>
				</div>
			</div>

			{/* Transaction explanation */}
			<div className="p-3 sm:p-4 bg-gray-700 border-b border-gray-600 text-xs sm:text-sm">
				<p className="text-blue-200">
					<span className="font-semibold text-white">About this transaction:</span> You are about to swap
					{transactionInfo.fromToken ? ` ${formatNumber(transactionInfo.fromAmount)} ${transactionInfo.fromToken} ` : " tokens "}
					for
					{transactionInfo.toToken ? ` ${formatNumber(transactionInfo.toAmount)} ${transactionInfo.toToken}` : " tokens"}.
					Please review the details below before confirming.
				</p>
			</div>

			<div className="p-3 sm:p-4">
				<div className="grid gap-3 sm:gap-4">
					{/* Transaction visualization */}
					<div className="bg-gray-900 p-3 sm:p-5 rounded-lg border border-gray-700">
						<div className="flex flex-col sm:flex-row items-center justify-between gap-4">
							{/* From Token Display */}
							<div className="text-center w-full sm:w-auto">
								<div className="text-xs text-gray-400 mb-1">From</div>
								<div className="bg-gray-800 rounded-lg p-2 flex flex-col items-center">
									<div className="font-semibold text-sm sm:text-lg text-white">
										{formatNumber(transactionInfo.fromAmount)}
									</div>
									<div className="text-xs text-blue-400 font-medium">{transactionInfo.fromToken}</div>
								</div>
							</div>
							{/* Arrow/Direction Indicator */}
							<div className="flex-none sm:flex-1 w-full sm:w-auto flex justify-center items-center py-1 sm:py-2 sm:px-4">
								<div className="hidden sm:block h-0.5 w-full bg-gray-700 relative">
									<div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-gray-800 p-2 border border-gray-600 rounded-full">
										<svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 sm:h-6 sm:w-6 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
											<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
										</svg>
									</div>
								</div>
								<div className="sm:hidden">
									<svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
									</svg>
								</div>
							</div>{/* To Token Display */}
							<div className="text-center w-full sm:w-auto">
								<div className="text-xs sm:text-sm text-gray-400 mb-1">To</div>
								<div className="bg-gray-800 rounded-lg p-2 sm:p-3 flex flex-col items-center">
									<div className="font-semibold text-base sm:text-lg text-white">
										{formatNumber(transactionInfo.toAmount)}
									</div>
									<div className="text-xs sm:text-sm text-green-400 font-medium">{transactionInfo.toToken}</div>
								</div>
							</div>
						</div>

						{/* Exchange rate info */}
						<div className="mt-4 text-center">
							<div className="text-xs text-gray-400">Exchange Rate</div>
							<div className="text-xs sm:text-base font-medium text-gray-300">
								1 {transactionInfo.fromToken} ≈ {formatNumber(transactionInfo.exchangeRate, 4)} {transactionInfo.toToken}
							</div>
						</div>
					</div>

					{/* Mobile Toggle Button for Details */}
					<button
						className="sm:hidden w-full py-2 px-3 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm font-medium text-white flex items-center justify-between"
						onClick={toggleDetails}
					>
						<span>Transaction Details</span>
						<svg
							className={`h-4 w-4 transform transition-transform ${showDetails ? 'rotate-180' : ''}`}
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
						</svg>
					</button>

					{/* Transaction details section */}
					<div className={`${!showDetails ? 'hidden sm:block' : ''} mt-2`}>
						<div className="bg-gray-900 p-2 sm:p-4 rounded-md border border-gray-700">
							<div className="space-y-2 sm:space-y-3">
								{/* From Token */}
								<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 sm:gap-2 border-b border-gray-700 pb-2">
									<span className="text-xs sm:text-sm text-gray-300 font-medium">You Send</span>
									<div className="flex flex-col sm:items-end">
										<span className="text-sm font-semibold text-white">
											{formatNumber(transactionInfo.fromAmount)} {transactionInfo.fromToken}
										</span>
									</div>
								</div>

								{/* To Token */}
								<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-gray-700 pb-2">
									<span className="text-sm text-gray-300 font-medium">You Receive</span>
									<div className="flex flex-col sm:items-end">
										<span className="text-sm sm:text-base font-semibold text-white">
											{formatNumber(transactionInfo.toAmount)} {transactionInfo.toToken}
										</span>
										<span className="text-xs text-gray-400">
											Min. received after slippage ({transactionInfo.slippage}%)
										</span>
									</div>
								</div>

								{/* Recipient Address */}
								<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-gray-700 pb-2">
									<span className="text-sm text-gray-300 font-medium">Recipient</span>
									<div className="flex items-center space-x-2 overflow-x-auto">
										<span className="text-xs sm:text-sm text-gray-300 font-mono bg-gray-800 px-2 py-1 rounded whitespace-nowrap">
											{shortenAddress(transactionInfo.toAddress)}
										</span>
										<button
											onClick={() => copyToClipboard(transactionInfo.toAddress)}
											className="flex-shrink-0 text-gray-400 hover:text-blue-400 transition-colors p-1"
											title="Copy full address"
										>
											{copySuccess ? <CheckIcon className="h-4 w-4 text-green-400" /> : <CopyIcon className="h-4 w-4" />}
										</button>
									</div>
								</div>

								{/* Network */}
								<div className="flex justify-between items-center">
									<span className="text-sm text-gray-300 font-medium">Network</span>
									<span className="text-sm text-gray-300 font-medium flex items-center space-x-1">
										<span className="text-white">{transactionInfo.networkIcon}</span>
										<span>{transactionInfo.networkName}</span>
									</span>
								</div>
							</div>
						</div>
					</div>

					{/* Security reminders */}
					<div className="bg-gray-900 p-3 sm:p-4 rounded-md text-xs sm:text-sm text-amber-200 mt-4 border border-amber-900">
						<div className="flex items-start space-x-3">
							<div className="flex-shrink-0">
								<svg className="h-5 w-5 text-amber-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
									<path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
								</svg>
							</div>
							<div>
								<h4 className="font-semibold text-amber-300">Security Reminders:</h4>
								<ul className="mt-2 space-y-2 list-disc pl-5">
									<li>Verify the receiving amount is correct</li>
									<li>Double-check the recipient address</li>
									<li>Ensure you&apos;re on the correct network ({transactionInfo.networkName})</li>
									<li>Transaction cannot be reversed once confirmed</li>
								</ul>
							</div>
						</div>
					</div>

					{/* Advanced Details Toggle */}
					<div className="mt-2">
						<button
							onClick={() => setShowRawData(!showRawData)}
							className="text-xs sm:text-sm text-gray-400 hover:text-gray-200 flex items-center"
						>
							<span>{showRawData ? 'Hide' : 'Show'} Advanced Details</span>
							<svg
								className={`ml-1 h-4 w-4 transform transition-transform ${showRawData ? 'rotate-180' : ''}`}
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
							</svg>
						</button>

						{showRawData && (
							<div className="mt-2 p-3 bg-gray-900 rounded-md border border-gray-700 overflow-x-auto">
								<pre className="text-xs text-gray-400">
									{JSON.stringify(transactionInfo.rawData, null, 2)}
								</pre>
							</div>
						)}
					</div>

					{/* Action button */}
					<div className="mt-6">
						<Button
							onClick={signAndSendTransaction}
							isDisabled={isLoading}
							colorScheme="blue"
							size="lg"
							className="w-full min-h-[48px] sm:min-h-[56px] px-4 sm:px-6 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors duration-200 shadow-sm flex items-center justify-center space-x-2"
						>
							{isLoading ? (
								<>
									<svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
										<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
										<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
									</svg>
									<span>Processing...</span>
								</>
							) : (
								<>
									<span>Confirm {name}</span>
									<ExternalLinkIcon className="h-5 w-5" />
								</>
							)}
						</Button>

						<div className="text-xs text-gray-400 mt-2 text-center">
							Click the button to confirm this transaction in your wallet
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};