export function useRuns() {
	/**
	 * Generates a public shared run ID for the given run ID.
	 */
	const shareRun = async (runId: string): Promise<string | undefined> => {

		const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3000/api";
		const res = await fetch(apiUrl + "/api/runs/share", {
			method: "POST",
			body: JSON.stringify({ runId }),
			headers: {
				"Content-Type": "application/json",
			},
		});

		if (!res.ok) {
			return;
		}

		const { success, message, sharedRunURL } = await res.json();
		return success ? sharedRunURL : "";
	};

	return {
		shareRun,
	};
}
