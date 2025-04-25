interface StatsCardProps {
	value: string;
	label: string;
	color: "blue" | "green" | "purple";
}

const colorStyles = {
	blue: "text-blue-400",
	green: "text-green-400",
	purple: "text-purple-400"
};

export function StatsCard({ value, label, color }: StatsCardProps) {
	return (
		<div className="p-4 bg-gray-800/50 rounded-lg backdrop-blur-sm">
			<div className={`text-2xl sm:text-3xl font-bold ${colorStyles[color]}`}>
				{value}
			</div>
			<div className="text-gray-400 text-sm">
				{label}
			</div>
		</div>
	);
}