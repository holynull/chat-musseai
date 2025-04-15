import { useThreadRuntime } from "@assistant-ui/react";
import { Card, CardTitle } from "./ui/card";

const suggestedQuestions = [
  "Hi~!",
  "What are latest news about BTC?",
  "Help me swap some USDT on Solana.",
  "What is the price of ETH?",
];

export function SuggestedQuestions() {
  const threadRuntime = useThreadRuntime();

  const handleSend = (text: string) => {
    threadRuntime.append({
      role: "user",
      content: [{ type: "text", text }],
    });
  };

  return (
    <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-4">
      {suggestedQuestions.map((question, idx) => (
        <Card
          onClick={() => handleSend(question)}
          key={`suggested-question-${idx}`}
          className="w-full bg-[#282828] border-gray-600 cursor-pointer transition-colors ease-in hover:bg-[#2b2b2b]"
        >
          <CardTitle className="p-4 text-gray-200 font-normal text-sm">
            {question}
          </CardTitle>
        </Card>
      ))}
    </div>
  );
}
