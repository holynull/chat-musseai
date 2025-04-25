export function BackgroundDecoration() {
	return (
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
	);
}