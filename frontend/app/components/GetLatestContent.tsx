"use client";
import { useAssistantToolUI } from "@assistant-ui/react";
import Image from "next/image";
import { useState, useEffect } from "react";

export const useGetLatestContent = () => useAssistantToolUI({
	toolName: "getLatestContent",
	render: (input) => {
		const data: any = input.args.data;

		return (
			<>{JSON.stringify(data)}</>
		);
	},
});