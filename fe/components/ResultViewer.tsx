"use client";

import { Button, buttonVariants } from "@/components/ui/button";

interface Props {
  resultUrl: string;
  onReset: () => void;
}

export default function ResultViewer({ resultUrl, onReset }: Props) {
  return (
    <div className="space-y-6 text-center">
      <div>
        <div className="text-4xl mb-2">✅</div>
        <h2 className="text-xl font-semibold">Object removed successfully!</h2>
      </div>

      <div className="rounded-xl overflow-hidden bg-gray-900">
        <video
          src={resultUrl}
          controls
          autoPlay
          className="w-full"
        />
      </div>

      <div className="flex justify-center gap-4">
        <a
          href={resultUrl}
          download="result.mp4"
          className={buttonVariants({ variant: "outline" })}
        >
          Download Video
        </a>
        <Button onClick={onReset} variant="secondary">
          Start Over
        </Button>
      </div>
    </div>
  );
}
