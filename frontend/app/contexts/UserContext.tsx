"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useToast } from "@/app/hooks/use-toast";

// Define user type
export interface User {
	user_id: string;  // New field
	email: string;
	username: string;
	full_name?: string;
	disabled?: boolean;
	created_at: string;
	isAuthenticated: boolean;
}

// Login request parameters type
export interface LoginCredentials {
	email: string;
	password: string;
}

// Registration request parameters type
export interface RegisterCredentials {
	email: string;
	username: string;
	password: string;
	full_name?: string;
}

// Password change request parameters type
export interface PasswordChangeCredentials {
	current_password: string;
	new_password: string;
}

// API response type
interface ApiResponse<T> {
	success: boolean;
	data?: T;
	error?: string;
}

// Token response type
interface TokenResponse {
	access_token: string;
	token_type: string;
	user: User;
}

// Define context type
interface UserContextType {
	user: User | null;
	login: (credentials: LoginCredentials) => Promise<boolean>;
	register: (credentials: RegisterCredentials) => Promise<boolean>;
	logout: () => Promise<boolean>;
	changePassword: (credentials: PasswordChangeCredentials) => Promise<boolean>;
	isLoading: boolean;
	error: string | null;
	clearError: () => void;
}

// Create context
const UserContext = createContext<UserContextType | undefined>(undefined);

// API request base URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

// Create context provider component
export function UserProvider({ children }: { children: ReactNode }) {
	const [user, setUser] = useState<User | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [token, setToken] = useState<string | null>(null);
	const router = useRouter();
	const { toast } = useToast();

	// Clear error
	const clearError = () => setError(null);

	const fetchApi = useCallback(async <T,>(
		endpoint: string,
		options: RequestInit = {}
	): Promise<ApiResponse<T>> => {
		// function implementation remains the same
		try {
			const headers: HeadersInit = {
				"Content-Type": "application/json",
				...(token && { Authorization: `Bearer ${token}` }),
				...options.headers,
			};

			const response = await fetch(`${API_BASE_URL}${endpoint}`, {
				...options,
				headers,
			});

			const data = await response.json();

			if (!response.ok) {
				throw new Error(data.detail || 'An error occurred');
			}

			return { success: true, data: data as T };
		} catch (err) {
			const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred';
			return { success: false, error: errorMessage };
		}
	}, [token]); // Only re-create when token changes

	// Handle authentication failure
	const handleAuthFailure = useCallback(() => {
		localStorage.removeItem("auth_token");
		setToken(null);
		setUser(null);
		router.push('/login');
	}, [router]);

	// Initialize user state
	useEffect(() => {
		// Fetch current user information from server
		const fetchCurrentUser = async (authToken: string) => {
			try {
				const response = await fetchApi<User>('/api/users/me', {
					headers: {
						Authorization: `Bearer ${authToken}`,
					}
				});

				if (response.success && response.data) {
					// Set user data, ensure fields match
					setUser({
						...response.data,
						isAuthenticated: true,
					});
				} else {
					// Invalid token, clear authentication state
					handleAuthFailure();
				}
			} catch (err) {
				console.error("Error fetching user data:", err);
				handleAuthFailure();
			} finally {
				setIsLoading(false);
			}
		};
		const initializeAuth = async () => {
			const storedToken = localStorage.getItem("auth_token");
			if (storedToken) {
				setToken(storedToken);
				await fetchCurrentUser(storedToken);
			} else {
				setIsLoading(false);
			}
		};

		initializeAuth();
	}, [handleAuthFailure, fetchApi]);

	// Login function
	const login = async (credentials: LoginCredentials): Promise<boolean> => {
		setIsLoading(true);
		clearError();

		try {
			const response = await fetchApi<TokenResponse>('/api/login/email', {
				method: 'POST',
				body: JSON.stringify(credentials),
			});

			if (response.success && response.data) {
				// Store token
				localStorage.setItem("auth_token", response.data.access_token);
				setToken(response.data.access_token);

				// Set user data
				setUser({
					...response.data.user,
					isAuthenticated: true
				});

				toast({
					title: "Login Successful",
					description: `Welcome back, ${response.data.user.username}!`,
				});

				// Redirect to chat page
				router.push('/chat');
				return true;
			} else {
				setError(response.error || 'Login failed');
				toast({
					title: "Login Failed",
					description: response.error || "Username or password incorrect",
					variant: "destructive",
				});
				return false;
			}
		} catch (err) {
			const errorMessage = err instanceof Error ? err.message : 'Error occurred during login';
			setError(errorMessage);
			toast({
				title: "Login Error",
				description: errorMessage,
				variant: "destructive",
			});
			return false;
		} finally {
			setIsLoading(false);
		}
	};

	// Registration function
	const register = async (credentials: RegisterCredentials): Promise<boolean> => {
		setIsLoading(true);
		clearError();

		try {
			const response = await fetchApi<TokenResponse>('/api/register', {
				method: 'POST',
				body: JSON.stringify(credentials),
			});

			if (response.success && response.data) {
				// Store token
				localStorage.setItem("auth_token", response.data.access_token);
				setToken(response.data.access_token);

				// Set user data
				setUser({
					...response.data.user,
					isAuthenticated: true
				});

				toast({
					title: "Registration Successful",
					description: "Your account has been created successfully!",
				});

				// Redirect to home page
				router.push('/');
				return true;
			} else {
				setError(response.error || 'Registration failed');
				toast({
					title: "Registration Failed",
					description: response.error || "Error occurred during registration",
					variant: "destructive",
				});
				return false;
			}
		} catch (err) {
			const errorMessage = err instanceof Error ? err.message : 'Error occurred during registration';
			setError(errorMessage);
			toast({
				title: "Registration Error",
				description: errorMessage,
				variant: "destructive",
			});
			return false;
		} finally {
			setIsLoading(false);
		}
	};

	// Logout function
	const logout = async (): Promise<boolean> => {
		try {
			await fetchApi('/api/logout', {
				method: 'POST',
			});

			// Clear local storage and state
			localStorage.removeItem("auth_token");
			setToken(null);
			setUser(null);

			toast({
				title: "Logout Successful",
				description: "You have been logged out successfully",
			});

			// Redirect to login page
			router.push('/login');
			return true;
		} catch (err) {
			const errorMessage = err instanceof Error ? err.message : 'Error occurred during logout';
			setError(errorMessage);
			toast({
				title: "Logout Error",
				description: errorMessage,
				variant: "destructive",
			});
			return false;
		}
	};

	// Change password function
	const changePassword = async (credentials: PasswordChangeCredentials): Promise<boolean> => {
		setIsLoading(true);
		clearError();

		try {
			const response = await fetchApi('/api/users/change-password', {
				method: 'POST',
				body: JSON.stringify(credentials),
			});

			if (response.success) {
				toast({
					title: "Password Change Successful",
					description: "Your password has been updated successfully",
				});
				return true;
			} else {
				setError(response.error || 'Password change failed');
				toast({
					title: "Password Change Failed",
					description: response.error || "Unable to update password",
					variant: "destructive",
				});
				return false;
			}
		} catch (err) {
			const errorMessage = err instanceof Error ? err.message : 'Error occurred during password change';
			setError(errorMessage);
			toast({
				title: "Password Change Error",
				description: errorMessage,
				variant: "destructive",
			});
			return false;
		} finally {
			setIsLoading(false);
		}
	};

	return (
		<UserContext.Provider
			value={{
				user,
				login,
				register,
				logout,
				changePassword,
				isLoading,
				error,
				clearError
			}}
		>
			{children}
		</UserContext.Provider>
	);
}

// Create hook to use the context
export const useUser = () => {
	const context = useContext(UserContext);
	if (context === undefined) {
		throw new Error('useUser must be used within a UserProvider');
	}
	return context;
};