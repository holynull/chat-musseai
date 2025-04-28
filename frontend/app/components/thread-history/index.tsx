import { TooltipIconButton } from "../ui/assistant-ui/tooltip-icon-button";
import { SquarePen, History } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "../ui/sheet";
import { Skeleton } from "../ui/skeleton";
import React from "react";
import { useGraphContext } from "../../contexts/GraphContext";
import { groupThreads } from "./utils";
import { ThreadsList } from "./thread-list";
import { useQueryState } from "nuqs";
import { LogOut } from "lucide-react"; // 添加登出图标
import { SelectModel } from "../SelectModel";
import { WalletIndicator } from "../WalletIndicator";

const LoadingThread = () => <Skeleton className="w-full h-8 bg-[#373737]" />;

function ThreadHistoryComponent() {
	const { threadsData, userData, graphData } = useGraphContext();
	const { userThreads, isUserThreadsLoading, deleteThread } = threadsData;
	const { user, logout } = userData;
	const { switchSelectedThread, setMessages } = graphData;
	const [_threadId, setThreadId] = useQueryState("threadId");

	const clearMessages = () => {
		setMessages([]);
	};

	const deleteThreadAndClearMessages = async (id: string) => {
		clearMessages();
		await deleteThread(id, clearMessages);
	};

	const groupedThreads = groupThreads(
		userThreads,
		switchSelectedThread,
		deleteThreadAndClearMessages,
	);

	const createNewSession = async () => {
		setThreadId(null);
		clearMessages();
	};

	return (
		<span>
			{/* Tablet & up */}
			<div className="hidden md:flex flex-col w-[260px] h-full">
				<div className="flex-grow border-r-[1px] border-[#393939] my-6 flex flex-col overflow-hidden">
					<div className="flex flex-row items-center justify-between border-b-[1px] border-[#393939] pt-3 px-2 mx-4 -mt-4 text-gray-200">
						<p className="text-lg font-medium">Chat History</p>
						{user?.user_id ? (
							<>
								<TooltipIconButton
									tooltip="New chat"
									className="w-fit p-2"
									onClick={createNewSession}
								>
									<SquarePen className="w-5 h-5" />
								</TooltipIconButton>
								<div className="fixed top-2 sm:top-4 right-2 sm:right-4 z-[100] flex flex-row gap-2 items-center">
									<SelectModel />
									<WalletIndicator />
								</div>
							</>
						) : null}
					</div>
					<div className="overflow-y-auto flex-grow scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-transparent">
						{isUserThreadsLoading && !userThreads.length ? (
							<div className="flex flex-col gap-1 px-3 pt-3">
								{Array.from({ length: 25 }).map((_, i) => (
									<LoadingThread key={`loading-thread-${i}`} />
								))}
							</div>
						) : (
							<ThreadsList groupedThreads={groupedThreads} />
						)}
					</div>
					{user && (
						<div className="fixed bottom-0 left-0 w-[260px] border-t-[1px] border-[#393939] p-3 ">
							<TooltipIconButton
								tooltip="Logout"
								className="w-full flex items-center justify-center gap-2 p-2 hover:bg-gray-700 rounded"
								onClick={logout}
							>
								<LogOut className="w-5 h-5" />
								<span>Logout</span>
							</TooltipIconButton>
						</div>
					)}
				</div>
			</div>
			{/* Mobile */}
			<span className="md:hidden fixed top-2 left-2 z-[100] flex flex-row gap-2">
				<Sheet>
					<SheetTrigger asChild>
						<TooltipIconButton
							tooltip="New chat"
							className="w-fit h-fit p-2"
						>
							<History className="w-6 h-6" />
						</TooltipIconButton>
					</SheetTrigger>
					<SheetContent side="left" className="bg-[#282828] border-none">
						{isUserThreadsLoading && !userThreads.length ? (
							<div className="flex flex-col gap-1 px-3 pt-3">
								{Array.from({ length: 25 }).map((_, i) => (
									<LoadingThread key={`loading-thread-${i}`} />
								))}
							</div>
						) : (
							<ThreadsList groupedThreads={groupedThreads} />
						)}
						{user && (
							<div className="fixed bottom-0 left-0 w-[260px] border-t-[1px] border-[#393939] p-3 flex justify-center">
								<TooltipIconButton
									tooltip="Logout"
									className="flex items-center justify-center gap-2 p-2 hover:bg-gray-700 rounded"
									onClick={logout}
								>
									<LogOut className="w-5 h-5" />
									<span>Logout</span>
								</TooltipIconButton>
							</div>
						)}
					</SheetContent>
				</Sheet>
				{user?.user_id ? (
					<div className="bg-[#313338] rounded-md">
						<TooltipIconButton
							tooltip="New chat"
							className="w-fit h-fit p-2"
							onClick={createNewSession}
						>
							<SquarePen className="w-6 h-6" />
						</TooltipIconButton>
						<div className="fixed top-2 sm:top-4 right-2 sm:right-4 z-[100] flex flex-row gap-2 items-center bg-[#313338] rounded-md">
							<SelectModel />
							<WalletIndicator />
						</div>
					</div>
				) : null}
			</span>
		</span>
	);
}

export const ThreadHistory = React.memo(ThreadHistoryComponent);
