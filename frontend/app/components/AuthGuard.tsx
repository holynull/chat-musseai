"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "../contexts/UserContext";

export function AuthGuard({ children }: { children: React.ReactNode }) {
	const { user, isLoading } = useUser();
	const router = useRouter();

	useEffect(() => {
		// 如果用户未登录且加载完成，则重定向到登录页面
		if (!isLoading && (!user || !user.isAuthenticated)) {
			router.push("/login");
		}
	}, [user, isLoading, router]);

	// 显示加载状态
	if (isLoading) {
		return (
			<div className="flex items-center justify-center min-h-screen">
				<div className="text-white">Loading...</div>
			</div>
		);
	}

	// 如果用户已登录，则显示子组件
	if (user && user.isAuthenticated) {
		return <>{children}</>;
	}

	// 默认不渲染任何内容，等待重定向
	return null;
}