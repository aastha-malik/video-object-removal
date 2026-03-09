"use client";

import { Progress } from "@/components/ui/progress";

interface Props {
  progress: number;
  message: string;
}

export default function ProgressBar({ progress, message }: Props) {
  return (
    <div className="space-y-6 py-16 text-center">
      <div className="text-5xl">⚙️</div>
      <h2 className="text-xl font-semibold">Processing your video...</h2>
      <div className="max-w-md mx-auto space-y-3">
        <Progress value={progress} className="h-3" />
        <p className="text-gray-400 text-sm">{message || "Working..."}</p>
        <p className="text-gray-600 text-xs">{progress}% complete</p>
      </div>
      <p className="text-gray-500 text-sm">
        This may take several minutes depending on video length
      </p>
    </div>
  );
}
