"use client";
import { useAppKitProvider, useAppKitAccount, useAppKitNetwork, useAppKit } from "@reown/appkit/react"
import { useAssistantToolUI } from "@assistant-ui/react";
import { ethers } from 'ethers'
import type { Provider } from '@reown/appkit-adapter-solana'
import UniversalProvider from '@walletconnect/universal-provider'
import { useState } from "react";
import { ButtonGroup, Button, Tooltip, useToast } from '@chakra-ui/react'
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
// import { useSendTransaction } from 'wagmi'

export const useSendSolanaTransaction = () => useAssistantToolUI({
	toolName: "send_solana_transaction",
	render: (input) => {
		const { walletProvider } = useAppKitProvider<Provider>('solana')
		const { connection } = useAppKitConnection()
		const { open, close } = useAppKit();
		const { address, isConnected, caipAddress, status, embeddedWalletInfo } = useAppKitAccount()
		const [isLoading, setLoading] = useState<boolean>(false);
		const toast = useToast();
		const { txData, name, orderInfo } = input.args;
		const isDisabled = isLoading || !isConnected || !connection || !txData;

		const signAndSendTransaction = async () => {
			if (!isConnected) {
				toast.closeAll();
				toast({
					title: 'Wallet Connection',
					description: 'Connect to the wallet. And try again.',
					status: 'warning',
					duration: 5000,
					isClosable: true,
					position: 'top'
				});
				await open({ view: "Connect" });
				return
			}
			if (!isLoading) {
				try {
					setLoading(true);
					wcModal.switchNetwork(solana)
					// await open({ view: 'Connect' })
					// 1. 创建Transaction实例
					const transaction = new Transaction();
					console.log(txData)

					// 2. 遍历tx数组,构建每个TransactionInstruction
					for (const instruction of txData.tx) {
						// 2.1 处理account keys
						const keys = instruction.keys.map((key: any) => ({
							pubkey: new PublicKey(key.pubkey),
							isSigner: key.isSigner,
							isWritable: key.isWritable
						}));

						// 2.2 转换programId
						const programId = new PublicKey(instruction.programId);

						// 2.3 将data数组转为Buffer
						const data = Buffer.from(instruction.data);

						// 2.4 创建TransactionInstruction
						const txInstruction = new TransactionInstruction({
							keys,
							programId,
							data
						});

						// 2.5 添加指令到Transaction
						transaction.add(txInstruction);
					}
					if (connection) {
						const { blockhash } = await connection.getLatestBlockhash();
						transaction.recentBlockhash = blockhash;
						transaction.feePayer = new PublicKey(address as any);
						if (txData.signer) {
							const privateKey = Uint8Array.from(txData.signer);
							const signer = Keypair.fromSecretKey(privateKey);
							transaction.sign(signer);
						}
						// Show wallet confirmation toast
						toast({
							title: "Confirm Transaction",
							description: 'Please confirm the transaction in your wallet APP.',
							status: 'warning',
							duration: null,
							isClosable: true,
							position: 'top'
						});

						// First sign the transaction
						let signedTx;
						try {
							signedTx = await walletProvider.sendTransaction(transaction, connection);
							// Close wallet confirmation toast and show success
							toast.closeAll();
							toast({
								title: 'Transaction Send',
								description: 'Success.',
								status: 'success',
								duration: 5000,
								isClosable: true,
								position: 'top'
							});
						} catch (error: any) {
							// Close wallet confirmation toast and show error
							toast.closeAll();
							toast({
								title: 'Transaction Failed',
								description: error?.message || 'Transaction failed.',
								status: 'error',
								duration: 5000,
								isClosable: true,
								position: 'top'
							});
							console.log(error);
						}
						if (signedTx) {
							const hash = signedTx;
							console.log('Transaction hash:', hash);
							// Generate order record after transaction is sent
							try {
								await fetch(process.env.NEXT_PUBLIC_API_URL + '/api/generate_swap_order', {
									method: 'POST',
									headers: { 'Content-Type': 'application/json' },
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
								toast.closeAll();
								toast({
									title: 'Order Updated Success',
									description: 'Order update successful.',
									status: 'success',
									duration: 5000,
									isClosable: true,
									position: 'top'
								});
								console.log("Update order info success.")
							} catch (error: any) {
								toast.closeAll();
								toast({
									title: 'Order Update Failed',
									description: error?.message || 'Order update failed.',
									status: 'error',
									duration: 5000,
									isClosable: true,
									position: 'top'
								});
								console.error('Error generating swap order:', error);
							}
							// setShow(false)
						}
					}
				} catch (e: any) {
					toast.closeAll();
					toast({
						title: 'Error',
						description: e?.message || 'Error occured.',
						status: 'error',
						duration: 5000,
						isClosable: true,
						position: 'top'
					});
					console.log(e)
				} finally {
					setLoading(false)
				}
			}
		}
		return <Button onClick={async () => await signAndSendTransaction()} isDisabled={isLoading}>{name}</Button>
	},
});