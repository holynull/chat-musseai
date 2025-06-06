"use client";

import { ComposerPrimitive, ThreadPrimitive, useAttachment, useAttachmentRuntime, useComposerRuntime, SimpleImageAttachmentAdapter, useComposer } from "@assistant-ui/react";
import { ComponentType, useMemo, type FC, useState, useEffect } from "react";

import { PaperclipIcon, SendHorizontalIcon } from "lucide-react";
import { BaseMessage } from "@langchain/core/messages";
import { TooltipIconButton } from "../ui/assistant-ui/tooltip-icon-button";
import { cn } from "@/app/utils/cn";
import Image from "next/image";
import { ClipboardEvent } from 'react';


export interface ChatComposerProps {
	currentThreadId: string | null;
	messages: BaseMessage[];
	submitDisabled: boolean;
}

const CircleStopIcon = () => {
	return (
		<svg
			xmlns="http://www.w3.org/2000/svg"
			viewBox="0 0 16 16"
			fill="currentColor"
			width="16"
			height="16"
		>
			<rect width="10" height="10" x="3" y="3" rx="2" />
		</svg>
	);
};
// Add proper types
interface AttachmentPanelProps {
	file: File | Blob;
	name?: string;
}
const getFileDataURL = (file: File) =>
	new Promise<string>((resolve, reject) => {
		const reader = new FileReader();

		reader.onload = () => resolve(reader.result as string);
		reader.onerror = (error) => reject(error);

		reader.readAsDataURL(file);
	});
export const ImagePanel: ComponentType<any> = (data) => {
	const state = useAttachment();
	const attachmentsRuntime = useAttachmentRuntime();
	const [imageUrl, setImageUrl] = useState<string | null>(null);

	useEffect(() => {
		if (state.file) {
			getFileDataURL(state.file)
				.then(url => setImageUrl(url))
				.catch(err => console.error('Error getting file data URL:', err));
		}
	}, [state.file]);

	return (
		<div className="relative group flex flex-col p-2 hover:bg-gray-700/30 rounded-lg transition-colors">
			{/* 图片预览区域优化 */}
			<div className="w-48 h-36 relative rounded-lg overflow-hidden border border-gray-600 bg-gray-800/50">
				{imageUrl ? (
					<div className="relative w-full h-full">
						<Image
							src={imageUrl}
							alt={state.file?.name || 'Image attachment'}
							fill
							className="object-contain"
							sizes="(max-width: 768px) 100vw, 192px"
						/>
						{/* 添加图片类型标识 */}
						<div className="absolute bottom-0 left-0 bg-gray-800/70 text-xs text-gray-200 px-2 py-0.5 rounded-tr-md">
							{state.file?.type?.split('/')[1]?.toUpperCase() || 'IMAGE'}
						</div>
					</div>
				) : (
					<div className="flex items-center justify-center w-full h-full">
						<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-gray-400">
							<rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
							<circle cx="8.5" cy="8.5" r="1.5"></circle>
							<polyline points="21 15 16 10 5 21"></polyline>
						</svg>
					</div>
				)}
			</div>

			{/* 文件信息区域优化 */}
			<div className="flex items-center justify-between w-full mt-2 px-1">
				<div className="flex flex-col">
					<div className="text-sm text-gray-200 truncate max-w-[170px] font-medium">
						{state.file?.name || 'Image attachment'}
					</div>
					{state.file && (
						<div className="text-xs text-gray-400">
							{formatFileSize(state.file.size)}
						</div>
					)}
				</div>

				{/* 删除按钮优化 */}
				<button
					onClick={() => attachmentsRuntime.remove()}
					className="p-1.5 rounded-full bg-gray-700 hover:bg-gray-600 hover:text-red-400 text-gray-300 transition-colors"
					aria-label="Remove attachment"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
						<line x1="18" y1="6" x2="6" y2="18"></line>
						<line x1="6" y1="6" x2="18" y2="18"></line>
					</svg>
				</button>
			</div>
		</div>
	);
};

// 辅助函数：格式化文件大小
const formatFileSize = (bytes: number): string => {
	if (bytes < 1024) return bytes + ' B';
	if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
	if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
	return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
};

export const DocumentPanel: ComponentType<any> = ({ }) => {
	const state = useAttachment();
	const attachmentsRuntime = useAttachmentRuntime();
	return (
		<div className="relative group flex items-center gap-2 p-3 hover:bg-gray-700/30 rounded-md transition-colors w-full max-w-[200px]">
			<div className="w-10 h-10 flex items-center justify-center bg-gray-700 rounded">
				<span className="text-xs">DOC</span>
			</div>
			<div className="flex-1 min-w-0">
				<div className="text-sm truncate" title={state.file?.name || 'Document'}>
					{state.file?.name || 'Document'}
				</div>
			</div>
			<div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity">
				<button
					onClick={() => attachmentsRuntime.remove()}
					className="p-1 rounded-full bg-gray-800/80 hover:bg-gray-700 text-gray-300"
					aria-label="Remove attachment"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
						<line x1="18" y1="6" x2="6" y2="18"></line>
						<line x1="6" y1="6" x2="18" y2="18"></line>
					</svg>
				</button>
			</div>
		</div>
	);
};

export const FilePanel: ComponentType<any> = ({ file }) => {
	const state = useAttachment();
	const attachmentsRuntime = useAttachmentRuntime();
	return (
		<div className="relative group flex items-center gap-2 p-3 hover:bg-gray-700/30 rounded-md transition-colors w-full max-w-[200px]">
			<div className="w-10 h-10 flex items-center justify-center bg-gray-700 rounded">
				<span className="text-xs">FILE</span>
			</div>
			<div className="flex-1 min-w-0">
				<div className="text-sm truncate" title={state.file?.name || 'File'}>
					{state.file?.name || 'File'}
				</div>
			</div>
			<div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity">
				<button
					onClick={() => attachmentsRuntime.remove()}
					className="p-1 rounded-full bg-gray-800/80 hover:bg-gray-700 text-gray-300"
					aria-label="Remove attachment"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
						<line x1="18" y1="6" x2="6" y2="18"></line>
						<line x1="6" y1="6" x2="18" y2="18"></line>
					</svg>
				</button>
			</div>
		</div>
	);
};

export const ChatComposer: FC<ChatComposerProps> = (
	props: ChatComposerProps,
) => {
	const isEmpty = props.messages.length === 0;

	const composerRuntime = useComposerRuntime();

	const handlePaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
		const items = Array.from(e.clipboardData?.items || []);

		// 辅助函数：生成唯一文件名
		const generateUniqueFileName = (originalFile: File): File => {
			// 获取现有附件列表中的文件名
			const existingFileNames = composerRuntime.getState().attachments.map(att => att.name);

			const fileName = originalFile.name;
			const lastDotIndex = fileName.lastIndexOf('.');
			const nameWithoutExt = lastDotIndex !== -1 ? fileName.substring(0, lastDotIndex) : fileName;
			const extension = lastDotIndex !== -1 ? fileName.substring(lastDotIndex) : '';

			let newFileName = fileName;
			let counter = 1;

			// 如果文件名已存在，添加计数后缀
			while (existingFileNames.includes(newFileName)) {
				newFileName = `${nameWithoutExt} (${counter})${extension}`;
				counter++;
			}

			// 如果文件名发生改变，创建新的File对象
			if (newFileName !== fileName) {
				return new File([originalFile], newFileName, { type: originalFile.type });
			}

			return originalFile;
		};

		// 处理所有可能的文件类型
		for (const item of items) {
			// 检查是否是文件类型
			if (item.kind === 'file') {
				const file = item.getAsFile();
				if (file) {
					// 检查文件大小 (例如：限制为10MB)
					const maxSize = 10 * 1024 * 1024; // 10MB
					if (file.size > maxSize) {
						// 可以在这里添加提示逻辑，例如使用toast通知
						console.warn(`文件大小超过限制: ${file.name} (${formatFileSize(file.size)})`);
						continue;
					}

					// 生成唯一文件名
					const uniqueFile = generateUniqueFileName(file);

					// 根据文件类型分别处理
					if (item.type.startsWith('image/')) {
						// 处理图片
						composerRuntime.addAttachment(uniqueFile);
					} else if (item.type.includes('pdf') ||
						item.type.includes('document') ||
						item.type.includes('text/plain')) {
						// 处理文档类型
						composerRuntime.addAttachment(uniqueFile);
					} else {
						// 其他文件类型
						composerRuntime.addAttachment(uniqueFile);
					}
				}
			}
		}

		// 如果有文件被添加，阻止默认粘贴行为
		if (items.some(item => item.kind === 'file')) {
			e.preventDefault();
		}
	};

	// 辅助函数：格式化文件大小
	const formatFileSize = (bytes: number): string => {
		if (bytes < 1024) return bytes + ' B';
		if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
		if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
		return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
	};

	return (
		<>
			<ComposerPrimitive.Root
				className={cn(
					"focus-within:border-aui-ring/20 flex w-full items-center md:justify-left justify-center rounded-lg border px-2.5 py-2.5 shadow-sm transition-all duration-300 ease-in-out bg-[#282828] border-gray-600",
					isEmpty ? "" : "md:ml-24 ml-3 mb-6",
					isEmpty ? "w-full" : "md:w-[70%] w-[95%] md:max-w-[832px]",
				)}
			>

				<ComposerPrimitive.Input
					autoFocus
					placeholder="How can I..."
					rows={1}
					className="placeholder:text-gray-400 text-gray-100 max-h-40 flex-1 resize-none border-none bg-transparent px-2 py-2 text-sm outline-none focus:ring-0 disabled:cursor-not-allowed"
					onPaste={handlePaste}
				/>
				<div className="flex-shrink-0">
					<ThreadPrimitive.If running={false} >
						<ComposerPrimitive.AddAttachment asChild>
							<TooltipIconButton
								tooltip="Add Attachments"
								variant="ghost"
								// className="my-1 size-8 p-2 transition-opacity ease-in hover:bg-gray-700/50 rounded-full"
								className="my-1 size-8 p-2 transition-opacity ease-in"
							>
								<PaperclipIcon />
							</TooltipIconButton>
						</ComposerPrimitive.AddAttachment>
					</ThreadPrimitive.If>
					<ThreadPrimitive.If running={false} disabled={props.submitDisabled}>
						<ComposerPrimitive.Send asChild>
							<TooltipIconButton
								tooltip="Send"
								variant="ghost"
								className="my-1 size-8 p-2 transition-opacity ease-in"
							>
								<SendHorizontalIcon />
							</TooltipIconButton>
						</ComposerPrimitive.Send>
					</ThreadPrimitive.If>
					<ThreadPrimitive.If running>
						<ComposerPrimitive.Cancel asChild>
							<TooltipIconButton
								tooltip="Cancel"
								variant="ghost"
								className="my-1 size-8 p-2 transition-opacity ease-in"
							>
								<CircleStopIcon />
							</TooltipIconButton>
						</ComposerPrimitive.Cancel>
					</ThreadPrimitive.If>
				</div>

			</ComposerPrimitive.Root>
			<div className="flex flex-wrap gap-3 p-3 max-h-[300px] overflow-y-auto w-full">
				<ComposerPrimitive.Attachments
					components={{
						Image: ImagePanel,
						Document: DocumentPanel,
						File: FilePanel,
						Attachment: FilePanel,
					}}
				/>
			</div>
		</>
	);
};
