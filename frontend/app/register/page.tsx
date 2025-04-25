"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Card } from "../components/ui/card";
import { useToast } from "../hooks/use-toast";

export default function RegisterPage() {
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [confirmPassword, setConfirmPassword] = useState("");
	const [isLoading, setIsLoading] = useState(false);
	const router = useRouter();
	const { toast } = useToast();

	const handleRegister = async (e: React.FormEvent) => {
		e.preventDefault();

		if (password !== confirmPassword) {
			toast({
				title: "密码不匹配",
				description: "请确保两次输入的密码一致",
				variant: "destructive",
			});
			return;
		}

		setIsLoading(true);

		try {
			// 这里应该是实际的注册API调用
			// 例如: const response = await fetch('/api/register', {...})

			// 模拟注册成功
			setTimeout(() => {
				toast({
					title: "注册成功",
					description: "您的账号已创建，请登录",
				});
				router.push("/login");
			}, 1000);
		} catch (error) {
			toast({
				title: "注册失败",
				description: "请稍后再试",
				variant: "destructive",
			});
		} finally {
			setIsLoading(false);
		}
	};

	return (
		<div className="flex items-center justify-center min-h-screen bg-gray-900">
			<Card className="w-full max-w-md p-8 space-y-6 bg-gray-800 text-white">
				<div className="text-center">
					<h1 className="text-2xl font-bold">创建 Musse AI 账号</h1>
					<p className="text-gray-400 mt-2">请填写以下信息注册账号</p>
				</div>

				<form onSubmit={handleRegister} className="space-y-4">
					<div className="space-y-2">
						<label htmlFor="email" className="text-sm font-medium">邮箱</label>
						<Input
							id="email"
							type="email"
							placeholder="your@email.com"
							value={email}
							onChange={(e) => setEmail(e.target.value)}
							required
							className="bg-gray-700 border-gray-600"
						/>
					</div>

					<div className="space-y-2">
						<label htmlFor="password" className="text-sm font-medium">密码</label>
						<Input
							id="password"
							type="password"
							placeholder="••••••••"
							value={password}
							onChange={(e) => setPassword(e.target.value)}
							required
							className="bg-gray-700 border-gray-600"
						/>
					</div>

					<div className="space-y-2">
						<label htmlFor="confirm-password" className="text-sm font-medium">确认密码</label>
						<Input
							id="confirm-password"
							type="password"
							placeholder="••••••••"
							value={confirmPassword}
							onChange={(e) => setConfirmPassword(e.target.value)}
							required
							className="bg-gray-700 border-gray-600"
						/>
					</div>

					<Button
						className="w-full"
						disabled={isLoading}
					>
						{isLoading ? "注册中..." : "注册"}
					</Button>
				</form>

				<div className="text-center text-sm">
					<p className="text-gray-400">
						已有账号？
						<a href="/login" className="text-blue-400 hover:underline ml-1">
							登录
						</a>
					</p>
				</div>
			</Card>
		</div>
	);
}