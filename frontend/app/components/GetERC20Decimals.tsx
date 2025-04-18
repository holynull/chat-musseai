"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import Image from "next/image";
import { useState, useEffect } from "react";

export type Decimals = {
	success: boolean,
	token_address: string,
	symbol: string,
	decimals: number,
	chainId: number,
};

export const useGetERC20Decimals = () => useAssistantToolUI({
	toolName: "get_erc20_decimals",
	render: (input) => {
		const data: Decimals = input.args.data;


		return (
			<>
				{JSON.stringify(data)}
			</>
		);
	},
});