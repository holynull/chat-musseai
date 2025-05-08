"use client";

import React from "react";
import Link from "next/link";
import Image from "next/image";

export default function HomePage(): React.ReactElement {
	return (
		<>
			{/* 装饰性背景元素 */}
			<div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none z-0 opacity-10">
				<div className="absolute top-1/4 left-1/4 animate-float-slow">
					<svg className="w-16 h-16" viewBox="0 0 24 24" fill="currentColor">
						<path d="M11.944 17.97L4.58 13.62 11.943 24l7.37-10.38-7.372 4.35h.003zM12.056 0L4.69 12.223l7.365 4.354 7.365-4.35L12.056 0z" />
					</svg>
				</div>
				<div className="absolute top-3/4 left-1/3 animate-float">
					<svg className="w-12 h-12" viewBox="0 0 24 24" fill="currentColor">
						<path d="M12 0C5.374 0 0 5.374 0 12s5.374 12 12 12 12-5.374 12-12S18.626 0 12 0zm-.037 18.844c-3.774 0-6.844-3.07-6.844-6.844s3.07-6.844 6.844-6.844 6.844 3.07 6.844 6.844-3.07 6.844-6.844 6.844z" />
					</svg>
				</div>
				<div className="absolute top-1/3 right-1/4 animate-float-slow">
					<svg className="w-20 h-20" viewBox="0 0 24 24" fill="currentColor">
						<path d="M12 0C5.374 0 0 5.374 0 12s5.374 12 12 12 12-5.374 12-12S18.626 0 12 0zm-1.537 18.745l-6.26-3.682 6.26 8.852 6.26-8.852-6.26 3.682zM12.004 4.5l-6.26 10.417 6.26 3.683 6.26-3.683L12.004 4.5z" />
					</svg>
				</div>
			</div>

			{/* 主要内容 */}
			<div className="relative flex flex-col items-center justify-center min-h-screen p-4 text-center">
				{/* 渐变背景 */}
				<div className="absolute inset-0 bg-gradient-to-b from-blue-900/30 to-purple-900/30 z-0"></div>

				{/* 头部区域 */}
				<div className="relative z-10 max-w-5xl mx-auto">
					{/* Logo */}
					<div className="logo-container relative mb-8 inline-block">
						{/* 添加发光效果 */}
						<div className="absolute inset-0 rounded-full bg-gradient-to-r from-blue-500/30 to-purple-500/30 blur-xl animate-pulse-slow"></div>

						{/* 添加旋转的外环 */}
						<div className="absolute inset-0 rounded-full border-2 border-blue-400/30 animate-spin-slow"></div>

						{/* Logo图片 */}
						<div className="relative">
							<Image
								src="/images/logo.png"
								alt="Musse AI Logo"
								width={96}  // 增大尺寸
								height={96} // 增大尺寸
								className="mx-auto rounded-full animate-float-slow shadow-lg shadow-blue-500/20 border-2 border-blue-500/20 z-10"
							/>

							{/* 内部光晕 */}
							<div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 to-purple-500/10 rounded-full blur-md"></div>
						</div>
					</div>

					{/* 标题和描述 */}
					<h1 className="text-5xl font-bold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-500 title-enhanced">
						Welcome to Musse AI
					</h1>

					<p className="text-xl mb-8 max-w-2xl mx-auto text-gray-300/90 leading-relaxed">
						Your intelligent AI assistant for cryptocurrency and blockchain information,
						<br />
						providing real-time insights and seamless interactions.
					</p>

					{/* 主要按钮 */}
					<div className="flex flex-col sm:flex-row gap-4 mt-6 justify-center">
						<Link
							href="/chat"
							className="px-8 py-4 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-lg hover:from-blue-700 hover:to-blue-800 transition-all shadow-lg hover:shadow-blue-500/20 font-semibold"
						>
							Start Musse AI
						</Link>
					</div>

					{/* 功能卡片区域 */}
					<div className="mt-24 grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
						{/* AI Chat 卡片 */}
						<div className="p-8 bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl transition-all hover:border-blue-500/50 hover:shadow-lg hover:shadow-blue-500/10 group">
							<div className="mb-4 text-blue-400">
								<svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
								</svg>
							</div>
							<h2 className="text-2xl font-semibold mb-3 group-hover:text-blue-400 transition-colors">AI Chat</h2>
							<p className="text-gray-400 group-hover:text-gray-300 transition-colors">
								Interact with our advanced AI to get answers about cryptocurrency and blockchain technology in real-time.
							</p>
							<div className="mt-6">
								<Link href="/chat" className="text-blue-400 inline-flex items-center">
									Try it now
									<svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
									</svg>
								</Link>
							</div>
						</div>

						{/* Token Swap 卡片 */}
						<div className="p-8 bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl transition-all hover:border-green-500/50 hover:shadow-lg hover:shadow-green-500/10 group">
							<div className="mb-4 text-green-400">
								<svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
								</svg>
							</div>
							<h2 className="text-2xl font-semibold mb-3 group-hover:text-green-400 transition-colors">Token Swap</h2>
							<p className="text-gray-400 group-hover:text-gray-300 transition-colors">
								Swap tokens across multiple chains with real-time price data and optimized routing for the best rates.
							</p>
							<div className="mt-6">
								<Link href="/chat" className="text-green-400 inline-flex items-center">
									Swap tokens
									<svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
									</svg>
								</Link>
							</div>
						</div>

						{/* Market Insights 卡片 */}
						<div className="p-8 bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl transition-all hover:border-purple-500/50 hover:shadow-lg hover:shadow-purple-500/10 group">
							<div className="mb-4 text-purple-400">
								<svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
								</svg>
							</div>
							<h2 className="text-2xl font-semibold mb-3 group-hover:text-purple-400 transition-colors">Market Insights</h2>
							<p className="text-gray-400 group-hover:text-gray-300 transition-colors">
								Get real-time market data and insights about cryptocurrencies and tokens to make informed decisions.
							</p>
							<div className="mt-6">
								<Link href="/chat" className="text-purple-400 inline-flex items-center">
									View insights
									<svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
									</svg>
								</Link>
							</div>
						</div>
					</div>

					{/* 特色部分 */}
					<div className="mt-24 max-w-6xl mx-auto px-4">
						<h2 className="text-3xl font-bold mb-8 text-center">Why Choose Musse AI</h2>

						<div className="grid grid-cols-1 md:grid-cols-2 gap-12">
							<div className="flex items-start">
								<div className="bg-blue-500/20 p-3 rounded-lg mr-4">
									<svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
									</svg>
								</div>
								<div>
									<h3 className="text-xl font-semibold mb-2">Fast & Reliable</h3>
									<p className="text-gray-400">Get instant responses powered by advanced AI technology with high accuracy for crypto inquiries.</p>
								</div>
							</div>

							<div className="flex items-start">
								<div className="bg-green-500/20 p-3 rounded-lg mr-4">
									<svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
									</svg>
								</div>
								<div>
									<h3 className="text-xl font-semibold mb-2">Secure Transactions</h3>
									<p className="text-gray-400">All interactions and token swaps are secured with industry-leading encryption standards.</p>
								</div>
							</div>

							<div className="flex items-start">
								<div className="bg-purple-500/20 p-3 rounded-lg mr-4">
									<svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
									</svg>
								</div>
								<div>
									<h3 className="text-xl font-semibold mb-2">Multi-chain Support</h3>
									<p className="text-gray-400">Support for all major blockchains including Ethereum, Solana, Binance Smart Chain and more.</p>
								</div>
							</div>

							<div className="flex items-start">
								<div className="bg-yellow-500/20 p-3 rounded-lg mr-4">
									<svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
									</svg>
								</div>
								<div>
									<h3 className="text-xl font-semibold mb-2">Real-time Data</h3>
									<p className="text-gray-400">Access up-to-the-minute market data, price movements, and blockchain analytics.</p>
								</div>
							</div>
						</div>
					</div>

					{/* 底部内容 */}
					<div className="mt-24 border-t border-gray-800 py-8 text-center text-gray-500">
						<p>© {new Date().getFullYear()} Musse AI. All rights reserved.</p>
						<div className="mt-4 flex justify-center space-x-6">
							<a href="#" className="hover:text-gray-300 transition-colors">Terms</a>
							<a href="/privacy" className="hover:text-gray-300 transition-colors">Privacy</a>
							<a href="#" className="hover:text-gray-300 transition-colors">Contact</a>
						</div>
					</div>
				</div>
			</div>
		</>
	);
}