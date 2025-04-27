"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Card } from "../components/ui/card";
import { useToast } from "../hooks/use-toast";
import { useUser, LoginCredentials } from "../contexts/UserContext";
import { motion } from "framer-motion";
import Link from "next/link";
import Image from "next/image";

export default function LoginPage() {
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const { login, isLoading, error, clearError } = useUser();
	const router = useRouter();
	const { toast } = useToast();

	const handleLogin = async (e: React.FormEvent) => {
		e.preventDefault();
		clearError();
		const credentials: LoginCredentials = {
			email,
			password,
		};
		await login(credentials);
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900 flex items-center justify-center p-4">
			<div className="absolute top-4 left-4">
				<Link href="/" className="flex items-center text-gray-300 hover:text-white transition-colors">
					<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-1">
						<path d="M19 12H5M12 19l-7-7 7-7" />
					</svg>
					<span>Back to Home</span>
				</Link>
			</div>
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
				className="w-full max-w-md"
			>
				<Card className="backdrop-blur-lg bg-gray-800/70 border border-gray-700 rounded-xl shadow-2xl">
					<div className="p-8">
						<div className="text-center mb-8">
							<motion.div
								initial={{ scale: 0.5 }}
								animate={{ scale: 1 }}
								transition={{ duration: 0.5 }}
							>
								<div className="w-20 h-20 mx-auto mb-4 rounded-full bg-white flex items-center justify-center overflow-hidden">
									<Image
										src="/images/logo.png"
										alt="Musse AI Logo"
										width={80}
										height={80}
										className="object-contain"
									/>
								</div>
							</motion.div>
							<h1 className="text-3xl font-bold text-white mb-2">Login to Musse AI</h1>
							<p className="text-gray-400">Please enter your account information</p>
						</div>

						<form onSubmit={handleLogin} className="space-y-6">
							<div className="space-y-2">
								<label className="text-sm font-medium text-gray-300">Email</label>
								<Input
									type="email"
									placeholder="your@email.com"
									value={email}
									onChange={(e) => setEmail(e.target.value)}
									className="h-12 bg-gray-700/50 border-gray-600 text-white placeholder-gray-400 focus:border-purple-500 focus:ring-purple-500 transition-all"
									required
								/>
							</div>

							<div className="space-y-2">
								<label className="text-sm font-medium text-gray-300">Password</label>
								<Input
									type="password"
									placeholder="••••••••"
									value={password}
									onChange={(e) => setPassword(e.target.value)}
									className="h-12 bg-gray-700/50 border-gray-600 text-white placeholder-gray-400 focus:border-purple-500 focus:ring-purple-500 transition-all"
									required
								/>
							</div>

							{error && (
								<motion.div
									initial={{ opacity: 0, y: -10 }}
									animate={{ opacity: 1, y: 0 }}
									className="text-red-400 text-sm bg-red-400/10 p-3 rounded-lg border border-red-400/20"
								>
									{error}
								</motion.div>
							)}

							<Button
								disabled={isLoading}
								className="w-full h-12 bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 text-white font-medium rounded-lg transition-all duration-300"
							>
								{isLoading ? (
									<div className="flex items-center justify-center">
										<div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
										Logging in...
									</div>
								) : (
									"Login"
								)}
							</Button>
						</form>

						<div className="mt-6 text-center text-sm">
							<p className="text-gray-400">
								Don&apos;t have an account?{" "}
								<span
									onClick={() => router.push("/register")}
									className="text-purple-400 hover:text-purple-300 transition-colors duration-200 cursor-pointer"
								>
									Register
								</span>
							</p>
						</div>
					</div>
				</Card>
			</motion.div>
		</div>
	);
}