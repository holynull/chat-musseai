"use client";
// reown appkit
import { createAppKit } from '@reown/appkit/react'
import { SolanaAdapter } from '@reown/appkit-adapter-solana'
import { Ethers5Adapter } from '@reown/appkit-adapter-ethers5'
import type { AppKitNetwork } from '@reown/appkit-common';
import { mainnet, bsc, tron, arbitrum, sepolia, solana, polygon, optimism } from '@reown/appkit/networks'
import { SolflareWalletAdapter, PhantomWalletAdapter } from '@solana/wallet-adapter-wallets'
import React, { type ReactNode } from 'react'

export const ethersAdapter = new Ethers5Adapter()
const solanaWeb3JsAdapter = new SolanaAdapter({
	wallets: [new PhantomWalletAdapter(), new SolflareWalletAdapter()]
})
const networks: [AppKitNetwork, ...AppKitNetwork[]] = [mainnet, bsc, arbitrum, solana, polygon, optimism]; //tron
export const wcModal = createAppKit({
	adapters: [ethersAdapter, solanaWeb3JsAdapter],
	networks: networks,
	projectId: process.env.NEXT_PUBLIC_WALLET_CONNECT_PROJECT_ID || '',
	metadata: {
		name: 'Musse AI',
		description: 'Musse AI',
		url: typeof window !== 'undefined' ? window.location.origin : '',
		icons: ['https://yourapp.com/icon.png'],
	},
	features: {
		analytics: true,
	},
});
// wcModal.getProvider()

// 添加接口定义
interface AppKitProps {
	children?: React.ReactNode;  // 定义 children 属性
}

// 修改组件定义,接收并使用 children 属性
export function AppKit({ children, cookies }: { children: ReactNode; cookies: string | null }): JSX.Element {
	// const initialState = cookieToInitialState(wagmiAdapter.wagmiConfig as Config, cookies)
	return (<>{children}</>)
	// return <WagmiProvider config={wagmiAdapter.wagmiConfig as Config} initialState={initialState}>
	//   <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	// </WagmiProvider>

}