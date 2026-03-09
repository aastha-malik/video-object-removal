"use client";

import { useCallback, useRef, useState } from "react";
import { Button } from "@/components/ui/button";

interface Props {
  onUpload: (file: File) => Promise<void>;
}

export default function VideoUploader({ onUpload }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [fileName, setFileName] = useState("");

  const handleFile = useCallback(
    async (file: File) => {
      if (!file.type.startsWith("video/")) {
        alert("Please upload a video file");
        return;
      }
      setFileName(file.name);
      setIsLoading(true);
      try {
        await onUpload(file);
      } finally {
        setIsLoading(false);
      }
    },
    [onUpload]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      className={`border-2 border-dashed rounded-xl p-16 text-center transition-colors ${
        isDragging
          ? "border-blue-400 bg-blue-950/20"
          : "border-gray-600 hover:border-gray-400"
      }`}
    >
      {isLoading ? (
        <div className="space-y-3">
          <div className="text-4xl animate-spin inline-block">⏳</div>
          <p className="text-gray-300">Uploading and extracting first frame...</p>
          <p className="text-gray-500 text-sm">{fileName}</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="text-5xl">🎬</div>
          <p className="text-xl text-gray-200">Drop your video here</p>
          <p className="text-gray-500">or</p>
          <Button variant="outline" onClick={() => inputRef.current?.click()}>
            Browse files
          </Button>
          <input
            ref={inputRef}
            type="file"
            accept="video/*"
            className="hidden"
            onChange={(e) =>
              e.target.files?.[0] && handleFile(e.target.files[0])
            }
          />
          <p className="text-gray-600 text-sm">MP4, MOV, AVI, WebM supported</p>
        </div>
      )}
    </div>
  );
}
