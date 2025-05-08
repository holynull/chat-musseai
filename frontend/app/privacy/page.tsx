"use client";

import React from "react";
import Link from "next/link";
import Image from "next/image";

export default function PrivacyPage(): React.ReactElement {
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
			<div className="relative min-h-screen p-4">
				{/* 渐变背景 */}
				<div className="absolute inset-0 bg-gradient-to-b from-blue-900/30 to-purple-900/30 z-0"></div>

				{/* 内容区域 */}
				<div className="relative z-10 max-w-4xl mx-auto pt-12 pb-24">
					{/* 返回首页链接 */}
					<div className="mb-8">
						<Link
							href="/"
							className="inline-flex items-center text-blue-400 hover:text-blue-300 transition-colors"
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								className="h-5 w-5 mr-2"
								fill="none"
								viewBox="0 0 24 24"
								stroke="currentColor"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth={2}
									d="M10 19l-7-7m0 0l7-7m-7 7h18"
								/>
							</svg>
							Back to Home
						</Link>
					</div>

					{/* 标题 */}
					<h1 className="text-4xl font-bold mb-8 bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-500">
						Privacy Policy
					</h1>

					{/* 最后更新信息 */}
					<p className="text-gray-400 mb-8">Last Updated: {new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</p>

					{/* 内容区块 */}
					<div className="space-y-8 text-gray-300">
						{/* 介绍 */}
						<section>
							<h2 className="text-2xl font-semibold mb-4 text-blue-400">Introduction</h2>
							<p className="mb-4">
								At Musse AI, we value your privacy and are committed to protecting your personal data. This Privacy Policy explains how we collect, use, and safeguard your information when you use our platform.
							</p>
							<p>
								By using Musse AI, you consent to the collection and use of information in accordance with this policy. We encourage you to read this document carefully to understand our practices regarding your personal data.
							</p>
						</section>

						{/* 信息收集 */}
						<section>
							<h2 className="text-2xl font-semibold mb-4 text-blue-400">Information We Collect</h2>
							<p className="mb-4">We may collect several types of information from and about users of our platform, including:</p>

							<div className="pl-4 mb-4 border-l-2 border-blue-500/30">
								<h3 className="text-xl font-medium mb-2">Personal Information</h3>
								<p>When you register for an account, we collect your email address, username, and password. We may also collect additional profile information you choose to provide.</p>
							</div>

							<div className="pl-4 mb-4 border-l-2 border-blue-500/30">
								<h3 className="text-xl font-medium mb-2">Blockchain and Wallet Information</h3>
								<p>When you connect your cryptocurrency wallet to our platform, we access your public wallet address and transaction history for the purposes of providing our services. We do not store your private keys or seed phrases.</p>
							</div>

							<div className="pl-4 mb-4 border-l-2 border-blue-500/30">
								<h3 className="text-xl font-medium mb-2">Usage Data</h3>
								<p>We collect information about how you interact with our platform, including your queries to our AI assistant, transaction requests, and other activities within our services.</p>
							</div>

							<div className="pl-4 border-l-2 border-blue-500/30">
								<h3 className="text-xl font-medium mb-2">Technical Data</h3>
								<p>We collect technical information such as your IP address, browser type and version, time zone setting, operating system, and device information.</p>
							</div>
						</section>

						{/* 信息使用 */}
						<section>
							<h2 className="text-2xl font-semibold mb-4 text-blue-400">How We Use Your Information</h2>
							<p className="mb-4">We use the information we collect to:</p>
							<ul className="list-disc list-inside space-y-2 mb-4">
								<li>Provide, maintain, and improve our services</li>
								<li>Process and complete cryptocurrency transactions</li>
								<li>Respond to your inquiries and fulfill your requests</li>
								<li>Send you technical notices, updates, security alerts, and support messages</li>
								<li>Monitor and analyze trends, usage, and activities in connection with our services</li>
								<li>Detect, prevent, and address technical issues</li>
								<li>Protect against unauthorized access to our systems and fraudulent transactions</li>
							</ul>
							<p>We may also use your information in an aggregated, de-identified form for research, statistical analysis, and business intelligence purposes.</p>
						</section>

						{/* 信息共享和披露 */}
						<section>
							<h2 className="text-2xl font-semibold mb-4 text-blue-400">Information Sharing and Disclosure</h2>
							<p className="mb-4">We may share your information in the following circumstances:</p>

							<div className="pl-4 mb-4 border-l-2 border-purple-500/30">
								<h3 className="text-xl font-medium mb-2">Service Providers</h3>
								<p>We share information with third-party vendors, consultants, and other service providers who perform services on our behalf, such as blockchain analytics providers and market data services.</p>
							</div>

							<div className="pl-4 mb-4 border-l-2 border-purple-500/30">
								<h3 className="text-xl font-medium mb-2">Compliance with Laws</h3>
								<p>We may disclose your information if required to do so by law or in response to valid requests by public authorities (e.g., a court or government agency).</p>
							</div>

							<div className="pl-4 mb-4 border-l-2 border-purple-500/30">
								<h3 className="text-xl font-medium mb-2">Business Transfers</h3>
								<p>If we are involved in a merger, acquisition, or sale of all or a portion of our assets, your information may be transferred as part of that transaction.</p>
							</div>

							<div className="pl-4 border-l-2 border-purple-500/30">
								<h3 className="text-xl font-medium mb-2">With Your Consent</h3>
								<p>We may share your information with third parties when we have your consent to do so.</p>
							</div>
						</section>

						{/* 数据安全 */}
						<section>
							<h2 className="text-2xl font-semibold mb-4 text-blue-400">Data Security</h2>
							<p className="mb-4">
								We implement appropriate technical and organizational measures to protect the security, integrity, and confidentiality of your personal information. However, no method of transmission over the Internet or electronic storage is 100% secure.
							</p>
							<p>
								While we strive to use commercially acceptable means to protect your personal data, we cannot guarantee its absolute security. You are responsible for maintaining the secrecy of your private keys and wallet credentials.
							</p>
						</section>

						{/* 数据保留 */}
						<section>
							<h2 className="text-2xl font-semibold mb-4 text-blue-400">Data Retention</h2>
							<p>
								We retain your personal information for as long as necessary to fulfill the purposes outlined in this Privacy Policy, unless a longer retention period is required or permitted by law. When we no longer need to use your information, we will take steps to remove it from our systems or de-identify it.
							</p>
						</section>

						{/* 国际数据传输 */}
						<section>
							<h2 className="text-2xl font-semibold mb-4 text-blue-400">International Data Transfers</h2>
							<p>
								Your information may be transferred to, and maintained on, computers located outside of your state, province, country, or other governmental jurisdiction where the data protection laws may differ from those in your jurisdiction. If you are located outside the United States and choose to provide information to us, please note that we transfer the data to the United States and process it there.
							</p>
						</section>

						{/* 您的权利 */}
						<section>
							<h2 className="text-2xl font-semibold mb-4 text-blue-400">Your Rights</h2>
							<p className="mb-4">Depending on your location, you may have certain rights regarding your personal information, including:</p>
							<ul className="list-disc list-inside space-y-2">
								<li>The right to access and receive a copy of your personal data</li>
								<li>The right to rectify or update your personal data</li>
								<li>The right to erase your personal data</li>
								<li>The right to restrict processing of your personal data</li>
								<li>The right to data portability</li>
								<li>The right to object to processing of your personal data</li>
								<li>The right to withdraw consent</li>
							</ul>
						</section>

						{/* 儿童隐私 */}
						<section>
							<h2 className="text-2xl font-semibold mb-4 text-blue-400">Children&apos;s Privacy</h2>
							<p>
								Our services are not intended for children under the age of 18. We do not knowingly collect personal information from children under 18. If you are a parent or guardian and believe that your child has provided us with personal information, please contact us.
							</p>
						</section>

						{/* 政策变更 */}
						<section>
							<h2 className="text-2xl font-semibold mb-4 text-blue-400">Changes to This Privacy Policy</h2>
							<p>
								We may update our Privacy Policy from time to time. We will notify you of any changes by posting the new Privacy Policy on this page and updating the &quot;Last Updated&quot; date. You are advised to review this Privacy Policy periodically for any changes.
							</p>
						</section>

						{/* 联系我们 */}
						<section>
							<h2 className="text-2xl font-semibold mb-4 text-blue-400">Contact Us</h2>
							<p className="mb-4">
								If you have any questions about this Privacy Policy or our data practices, please contact us at:
							</p>
							<div className="p-6 bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl">
								<p className="mb-2"><span className="font-medium">Email:</span> privacy@musseai.com</p>
								{/* <p><span className="font-medium">Address:</span> Musse AI Headquarters, 123 Blockchain Avenue, San Francisco, CA 94105, USA</p> */}
							</div>
						</section>
					</div>
				</div>

				{/* 底部内容 */}
				<div className="relative z-10 mt-12 border-t border-gray-800 py-8 text-center text-gray-500">
					<p>© {new Date().getFullYear()} Musse AI. All rights reserved.</p>
					<div className="mt-4 flex justify-center space-x-6">
						<Link href="#" className="hover:text-gray-300 transition-colors">Terms</Link>
						<Link href="/privacy" className="text-blue-400 hover:text-blue-300 transition-colors">Privacy</Link>
						<Link href="#" className="hover:text-gray-300 transition-colors">Contact</Link>
					</div>
				</div>
			</div>
		</>
	);
}
