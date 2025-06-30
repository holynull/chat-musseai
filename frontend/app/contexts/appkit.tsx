"use client";
// reown appkit
import { ConnectorType, createAppKit, useAppKit, useAppKitAccount, UseAppKitAccountReturn, useAppKitNetwork, UseAppKitNetworkReturn, useAppKitProvider } from '@reown/appkit/react'
import { SolanaAdapter } from '@reown/appkit-adapter-solana'
import { Ethers5Adapter } from '@reown/appkit-adapter-ethers5'
import type { AppKitNetwork } from '@reown/appkit-common';
import { mainnet, bsc, tron, arbitrum, sepolia, solana, polygon, optimism } from '@reown/appkit/networks'
import React, { createContext, useContext, type ReactNode } from 'react'
import type { Provider } from '@reown/appkit-adapter-solana'
import type { Connection } from '@reown/appkit-utils/solana'
import { useAppKitConnection } from '@reown/appkit-adapter-solana/react';

export const ethersAdapter = new Ethers5Adapter()
const solanaWeb3JsAdapter = new SolanaAdapter();
export const networks: [AppKitNetwork, ...AppKitNetwork[]] = [mainnet, bsc, arbitrum, solana, polygon, optimism]; //tron
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
interface WalletConnectContextType {
	open: (options?: any) => Promise<void>;
	close: () => Promise<void>;
	account: UseAppKitAccountReturn;
	network: UseAppKitNetworkReturn;
	walletProvider: unknown;
	solanaProvider: unknown;
	solConnetction: Connection | null;
}
const WalletConnectContext = createContext<WalletConnectContextType | undefined>(undefined);
// 修改组件定义,接收并使用 children 属性
export function AppKit({ children, cookies }: { children: ReactNode; cookies: string | null }): JSX.Element {
	const { open, close } = useAppKit();
	const { address, isConnected, caipAddress, status, embeddedWalletInfo, allAccounts } = useAppKitAccount()
	const { caipNetwork, caipNetworkId, chainId, switchNetwork } = useAppKitNetwork()
	const { walletProvider } = useAppKitProvider('eip155')
	const { walletProvider: solanaProvider } = useAppKitProvider<Provider>('solana')
	const { connection } = useAppKitConnection()
	// const initialState = cookieToInitialState(wagmiAdapter.wagmiConfig as Config, cookies)
	return (<WalletConnectContext.Provider value={{
		open: open, close: close, account: {
			address: address,
			isConnected: isConnected,
			caipAddress: caipAddress,
			status: status, embeddedWalletInfo: embeddedWalletInfo,
			allAccounts: allAccounts,
		},
		network: {
			caipNetwork: caipNetwork,
			caipNetworkId: caipNetworkId,
			chainId: chainId,
			switchNetwork: switchNetwork
		},
		walletProvider: walletProvider,
		solanaProvider: solanaProvider,
		solConnetction: connection ?? null,
	}}>{children}</WalletConnectContext.Provider>)
	// return <WagmiProvider config={wagmiAdapter.wagmiConfig as Config} initialState={initialState}>
	//   <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	// </WagmiProvider>

}

export const useWalletConnect = () => {
	const context = useContext(WalletConnectContext);
	if (context === undefined) {
		throw new Error('useUser must be used within a UserProvider');
	}
	return context;
};