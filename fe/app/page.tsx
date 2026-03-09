"use client";

import { useState } from "react";
import VideoUploader from "@/components/VideoUploader";
import FrameSelector, { Coordinate } from "@/components/FrameSelector";
import ProgressBar from "@/components/ProgressBar";
import ResultViewer from "@/components/ResultViewer";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

type Step = "upload" | "select" | "processing" | "result";

const STEPS: Step[] = ["upload", "select", "processing", "result"];
const STEP_LABELS = ["Upload", "Select", "Processing", "Result"];

export default function Home() {
  const [step, setStep] = useState<Step>("upload");
  const [sessionId, setSessionId] = useState("");
  const [frame, setFrame] = useState("");
  const [coordinates, setCoordinates] = useState<Coordinate[]>([]);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState("");
  const [resultUrl, setResultUrl] = useState("");
  const [error, setError] = useState("");

  const handleUpload = async (file: File) => {
    setError("");
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_URL}/api/upload`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as { detail?: string }).detail || "Upload failed");
    }
    const data = await res.json();
    setSessionId(data.session_id);
    setFrame(data.frame);
    setStep("select");
  };

  const handleRemove = () => {
    if (coordinates.length === 0) return;
    setError("");
    setStep("processing");
    setProgress(0);
    setProgressMessage("Connecting to ML pipeline...");

    const ws = new WebSocket(`${WS_URL}/ws/process`);

    ws.onopen = () => {
      ws.send(JSON.stringify({ session_id: sessionId, coordinates }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data as string);
      if (data.error) {
        setError(data.error);
        setStep("select");
      } else if (data.done) {
        setResultUrl(`${API_URL}${data.result_url}`);
        setStep("result");
      } else {
        setProgress(data.progress ?? 0);
        setProgressMessage(data.message ?? "Processing...");
      }
    };

    ws.onerror = () => {
      setError("WebSocket connection failed. Is the backend running?");
      setStep("select");
    };
  };

  const handleReset = () => {
    setStep("upload");
    setSessionId("");
    setFrame("");
    setCoordinates([]);
    setProgress(0);
    setProgressMessage("");
    setResultUrl("");
    setError("");
  };

  const currentStepIndex = STEPS.indexOf(step);

  return (
    <main className="min-h-screen bg-gray-950 text-white p-6">
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Video Object Remover</h1>
          <p className="text-gray-400">
            Upload a video, click objects to remove, download the result
          </p>
        </div>

        {/* Step indicator */}
        <div className="flex justify-center items-center gap-2 mb-10">
          {STEPS.map((s, i) => {
            const isActive = step === s;
            const isPast = currentStepIndex > i;
            return (
              <div key={s} className="flex items-center gap-2">
                <div
                  className={`flex items-center gap-2 ${
                    isActive
                      ? "text-white"
                      : isPast
                      ? "text-green-400"
                      : "text-gray-600"
                  }`}
                >
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 ${
                      isActive
                        ? "border-white bg-white text-black"
                        : isPast
                        ? "border-green-400 bg-green-400 text-black"
                        : "border-gray-700 text-gray-600"
                    }`}
                  >
                    {isPast ? "✓" : i + 1}
                  </div>
                  <span className="text-sm hidden sm:inline">{STEP_LABELS[i]}</span>
                </div>
                {i < STEPS.length - 1 && (
                  <div
                    className={`w-8 h-0.5 ${
                      currentStepIndex > i ? "bg-green-400" : "bg-gray-700"
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-950/50 border border-red-700 rounded-lg text-red-300 text-sm">
            {error}
          </div>
        )}

        {step === "upload" && <VideoUploader onUpload={handleUpload} />}

        {step === "select" && (
          <FrameSelector
            frame={frame}
            coordinates={coordinates}
            onAddCoordinate={(c) => setCoordinates((prev) => [...prev, c])}
            onClear={() => setCoordinates([])}
            onRemove={handleRemove}
          />
        )}

        {step === "processing" && (
          <ProgressBar progress={progress} message={progressMessage} />
        )}

        {step === "result" && (
          <ResultViewer resultUrl={resultUrl} onReset={handleReset} />
        )}
      </div>
    </main>
  );
}
