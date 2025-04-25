export function LoadingSpinner({ className = "" }) {
	return (
	  <div className={`inline-block animate-spin rounded-full border-2 border-current border-t-transparent h-4 w-4 ${className}`} role="status">
		<span className="sr-only">Loading...</span>
	  </div>
	);
  }