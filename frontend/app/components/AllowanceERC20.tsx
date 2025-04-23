"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import Image from "next/image";
import { useState, useEffect } from "react";

export type Allowance = {
  success: boolean,
  allowance: string,
  owner_address: string,
  spender_address: string,
  token_address: string,
  symbol: string,
  decimals: number,
  chainId: number,
};

// Format number function
const formatNumber = (value: string, decimals: string | number = 6): string => {
  const num = parseFloat(value);
  if (isNaN(num)) return value;

  const decimalPlaces = typeof decimals === 'string' ? parseInt(decimals) : decimals;
  const maxDecimals = Math.min(decimalPlaces, 8);

  return num.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: maxDecimals
  });
};

export const useAllowanceERC20 = () => useAssistantToolUI({
  toolName: "allowance_erc20",
  render: (input) => {
    const data: Allowance = input.args.data;
    
    if (!data || !data.success) return null;
    
    // Calculate formatted allowance amount
    const allowanceAmount = data.allowance 
      ? parseFloat(data.allowance) / Math.pow(10, data.decimals)
      : 0;

    return (
      <div className="rounded-lg border border-gray-200 overflow-hidden bg-white shadow-sm sm:mt-6 md:mt-8">
        <div className="p-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium text-gray-800">Token Allowance</h3>
          </div>
        </div>

        <div className="p-4">
          <div className="grid gap-4">
            {/* Main allowance information */}
            <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg border border-gray-200">
              <div>
                <p className="text-sm text-gray-700">Current Allowance</p>
                <p className="text-xl font-semibold text-gray-800">
                  {formatNumber(allowanceAmount.toString(), data.decimals)}
                  <span className="text-gray-600 text-base ml-1">{data.symbol}</span>
                </p>
              </div>
            </div>

            {/* Allowance details */}
            <div className="mt-4">
              <h4 className="text-sm font-medium text-gray-800 mb-2">Allowance Details</h4>
              <div className="grid grid-cols-1 gap-2 text-sm">
                <div className="flex justify-between p-2 border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
                  <span className="text-gray-700">Owner</span>
                  <span className="font-medium text-gray-800 text-xs truncate max-w-[200px]" title={data.owner_address}>
                    {data.owner_address}
                  </span>
                </div>
                <div className="flex justify-between p-2 border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
                  <span className="text-gray-700">Spender</span>
                  <span className="font-medium text-gray-800 text-xs truncate max-w-[200px]" title={data.spender_address}>
                    {data.spender_address}
                  </span>
                </div>
                <div className="flex justify-between p-2 border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
                  <span className="text-gray-700">Chain ID</span>
                  <span className="font-medium text-gray-800">{data.chainId}</span>
                </div>
              </div>
            </div>

            {/* Token information */}
            <div className="mt-2">
              <h4 className="text-sm font-medium text-gray-800 mb-2">Token Info</h4>
              <div className="text-xs bg-gray-50 p-2 rounded overflow-hidden text-gray-700 border border-gray-200 hover:bg-blue-50 transition-all duration-200">
                <div className="truncate" title={data.token_address}>
                  <span className="font-medium text-gray-800">Token Address: </span>
                  {data.token_address}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  },
});