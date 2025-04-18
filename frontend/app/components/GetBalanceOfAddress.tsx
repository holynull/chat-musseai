"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import Image from "next/image";
import { useState, useEffect } from "react";

export type Balance = {
    success: boolean,
    balance: string,
    wallet_address: string,
    token_address: string,
    symbol: string,
    decimals: number,
    chainId: number,
};

// Format number function
const formatNumber = (value: string, decimals: number = 6): string => {
    const num = parseFloat(value);
    if (isNaN(num)) return value;

    const maxDecimals = Math.min(decimals, 8);

    return num.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: maxDecimals
    });
};

// Format wallet address to show only first and last characters
const formatAddress = (address: string, chars: number = 6): string => {
    if (!address || address.length <= chars * 2) return address;
    return `${address.substring(0, chars)}...${address.substring(address.length - chars)}`;
};

// Get chain name based on chainId
const getChainName = (chainId: number): string => {
    const chains: Record<number, string> = {
        1: "Ethereum",
        56: "BSC",
        137: "Polygon",
        250: "Fantom",
        43114: "Avalanche",
        42161: "Arbitrum",
        10: "Optimism",
        // Add more chains
    };

    return chains[chainId] || `Chain ID: ${chainId}`;
};

export const useGetBalanceOfAddress = () => useAssistantToolUI({
    toolName: "get_balance_of_address",
    render: (input) => {
        const data: Balance = input.args.data;

        if (!data || !data.success) {
            return (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
                    <p className="font-medium">Balance Query Failed</p>
                    <p className="text-sm">Unable to retrieve balance information for this address</p>
                </div>
            );
        }

        // Calculate formatted balance
        const formattedBalance = formatNumber(
            (parseFloat(data.balance) / Math.pow(10, data.decimals)).toString(),
            data.decimals
        );

        const chainName = getChainName(data.chainId);

        return (
            <div className="rounded-lg border border-gray-200 overflow-hidden bg-white shadow-sm">
                <div className="p-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
                    <div className="flex items-center justify-between">
                        <h3 className="text-lg font-medium text-gray-800">Wallet Balance Query</h3>
                        <div className="flex items-center">
                            <span className="text-sm font-medium text-gray-700 mr-2">{chainName}</span>
                            <div className="w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center text-white text-xs font-bold">
                                {data.chainId}
                            </div>
                        </div>
                    </div>
                </div>

                <div className="p-4">
                    <div className="grid gap-4">
                        {/* Main balance information */}
                        <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg border border-gray-200">
                            <div>
                                <p className="text-sm text-gray-700">Token Balance</p>
                                <p className="text-xl font-semibold text-gray-800">
                                    {formattedBalance}
                                    <span className="text-gray-600 text-base ml-1">{data.symbol}</span>
                                </p>
                            </div>
                        </div>

                        {/* Transaction details */}
                        <div className="mt-4">
                            <h4 className="text-sm font-medium text-gray-800 mb-2">Address Information</h4>
                            <div className="grid grid-cols-1 gap-2 text-sm">
                                <div className="flex justify-between p-2 border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
                                    <span className="text-gray-700">Wallet Address</span>
                                    <span className="font-medium text-gray-800 flex items-center">
                                        <span className="text-xs font-mono bg-gray-100 px-2 py-1 rounded">{formatAddress(data.wallet_address)}</span>
                                        <button
                                            className="ml-2 text-blue-500 hover:text-blue-700"
                                            onClick={() => {
                                                navigator.clipboard.writeText(data.wallet_address);
                                                // Can add logic to show a copy success notification
                                            }}
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                            </svg>
                                        </button>
                                    </span>
                                </div>
                                {data.token_address && (
                                    <div className="flex justify-between p-2 border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
                                        <span className="text-gray-700">Token Contract</span>
                                        <span className="font-medium text-gray-800 flex items-center">
                                            <span className="text-xs font-mono bg-gray-100 px-2 py-1 rounded">{formatAddress(data.token_address)}</span>
                                            <button
                                                className="ml-2 text-blue-500 hover:text-blue-700"
                                                onClick={() => {
                                                    navigator.clipboard.writeText(data.token_address);
                                                    // Can add logic to show a copy success notification
                                                }}
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                                </svg>
                                            </button>
                                        </span>
                                    </div>
                                )}
                                <div className="flex justify-between p-2 border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
                                    <span className="text-gray-700">Network</span>
                                    <span className="font-medium text-gray-800">{chainName}</span>
                                </div>
                                <div className="flex justify-between p-2 border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
                                    <span className="text-gray-700">Token Decimals</span>
                                    <span className="font-medium text-gray-800">{data.decimals}</span>
                                </div>
                            </div>
                        </div>

                        {/* Raw JSON data (collapsible) */}
                        <details className="mt-2 text-xs">
                            <summary className="text-sm font-medium text-gray-800 cursor-pointer hover:text-blue-600">
                                View Raw Data
                            </summary>
                            <div className="p-2 mt-2 bg-gray-50 rounded border border-gray-200 overflow-auto max-h-40">
                                <pre className="text-gray-700 whitespace-pre-wrap break-words">
                                    {JSON.stringify(data, null, 2)}
                                </pre>
                            </div>
                        </details>
                    </div>
                </div>
            </div>
        );
    },
});