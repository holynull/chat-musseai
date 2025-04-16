"use client";
import { useAppKitProvider, useAppKitAccount, useAppKitNetwork, useAppKit } from "@reown/appkit/react"
import { useAssistantToolUI } from "@assistant-ui/react";
import { ethers } from 'ethers'
import UniversalProvider from '@walletconnect/universal-provider'
import { useState } from "react";
import { ButtonGroup, Button, Tooltip, useToast } from '@chakra-ui/react'
import { mainnet, bsc, tron, arbitrum, sepolia, solana, solanaTestnet, solanaDevnet } from '@reown/appkit/networks'
import type { AppKitNetwork } from '@reown/appkit-common';
import { wcModal } from "../contexts/appkit";
// import { useSendTransaction } from 'wagmi'

export const useSendEVMTransaction = () => useAssistantToolUI({
	toolName: "send_evm_transaction",
	render: (input) => {
		const [isShow, setShow] = useState(true)
		const { address, isConnected, caipAddress, status, embeddedWalletInfo } = useAppKitAccount()
		const { walletProvider } = useAppKitProvider('eip155')
		const { caipNetwork, caipNetworkId, chainId, switchNetwork } = useAppKitNetwork()
		const { open, close } = useAppKit();
		const networks: [AppKitNetwork, ...AppKitNetwork[]] = [mainnet, bsc, tron, arbitrum, sepolia, solana];
		const toast = useToast();
		const [isLoading, setLoading] = useState<boolean>(false);
		const { txData, name, orderInfo } = input.args;

		const signAndSendTransaction = async () => {
			if (!isLoading) {
				setLoading(true);
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
					setLoading(false);
					return
				}
				try {
					console.log("Wallet connected?" + isConnected)
					let curNet = networks.filter(network => network.id === chainId);
					if (curNet && curNet.length > 0) {
						wcModal.switchNetwork(curNet[0]);
						switchNetwork(curNet[0]);
					}
					// const provider = new ethers.providers.(walletProvider as UniversalProvider)
					const provider = new ethers.providers.Web3Provider(walletProvider as UniversalProvider)
					const signer = provider.getSigner(address)
					// await provider.connect()
					// let signer = await provider.getSigner(address)
					// Construct transaction object
					let _v = txData.value.indexOf('0x') === 0 ? txData.value : '0x' + txData.value
					let _d = txData.data.indexOf('0x') === 0 ? txData.data : '0x' + txData.data
					const transaction = {
						from: address,
						to: txData.to,
						data: _d,
						value: _v,
						gasLimit: txData.gasLimit,
						gasPrice: txData.gasPrice,
						chainId: chainId as number,
					};
					toast({
						title: "Confirm Transaction",
						description: 'Please confirm the transaction in your wallet APP.',
						status: 'warning',
						duration: null,
						isClosable: true,
						position: 'top'
					});
					// Send transaction
					// const tx = await provider.request({ "method": "eth_sendTransaction", "params": transaction }, chainId?.toString()) as any;
					const tx = await signer.sendTransaction(transaction)
					// await sendTransaction(transaction)
					if (tx && name === 'Send Swap Transaction') {
						console.log('Transaction hash:', tx.hash);
						toast.closeAll();
						toast({
							title: 'Transaction Send',
							description: 'Success.',
							status: 'success',
							duration: 5000,
							isClosable: true,
							position: 'top'
						});
						// Generate order record after transaction is sent
						try {
							await fetch(process.env.NEXT_PUBLIC_API_URL + '/generate_swap_order', {
								method: 'POST',
								headers: { 'Content-Type': 'application/json' },
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
							console.log("Update order info success.")
							toast.closeAll();
							toast({
								title: 'Order Update',
								description: 'Success.',
								status: 'success',
								duration: 5000,
								isClosable: true,
								position: 'top'
							});
						} catch (error: any) {
							toast.closeAll();
							toast({
								title: 'Order Update',
								description: error?.message || 'Order Update failed.',
								status: 'error',
								duration: 5000,
								isClosable: true,
								position: 'top'
							});
							console.error('Error generating swap order:', error);
						}
					}
					console.log('Transaction hash:', tx.hash);

					// Wait for transaction confirmation
					// const receipt = await tx.wait();
					// console.log('Transaction confirmed:', receipt);
					// setShow(false)
					setLoading(false)
				} catch (e: any) {
					toast.closeAll();
					toast({
						title: 'Transaction Failed',
						description: e?.message || 'Transaction failed.',
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
		return <Button onClick={() => { setLoading(true); signAndSendTransaction(); }} isDisabled={isLoading}>
			{name}
		</Button>;
	},
});