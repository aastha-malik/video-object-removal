"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";

export type Coordinate = {
  type: "point";
  x: number;
  y: number;
  frame_time: number;
};

interface Props {
  frame: string;
  coordinates: Coordinate[];
  onAddCoordinate: (coord: Coordinate) => void;
  onClear: () => void;
  onRemove: () => void;
}

export default function FrameSelector({
  frame,
  coordinates,
  onAddCoordinate,
  onClear,
  onRemove,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [dims, setDims] = useState<{ w: number; h: number } | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const img = new Image();
    img.onload = () => {
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      setDims({ w: img.naturalWidth, h: img.naturalHeight });
      ctx.drawImage(img, 0, 0);

      coordinates.forEach((coord, i) => {
        ctx.beginPath();
        ctx.arc(coord.x, coord.y, 14, 0, 2 * Math.PI);
        ctx.strokeStyle = "#00e064";
        ctx.lineWidth = 3;
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(coord.x, coord.y, 5, 0, 2 * Math.PI);
        ctx.fillStyle = "#00e064";
        ctx.fill();

        const label = String(i + 1);
        ctx.font = "bold 14px sans-serif";
        const metrics = ctx.measureText(label);
        const lx = coord.x + 18;
        const ly = coord.y + 6;
        ctx.fillStyle = "rgba(0,0,0,0.6)";
        ctx.fillRect(lx - 2, ly - 14, metrics.width + 4, 18);
        ctx.fillStyle = "#00e064";
        ctx.fillText(label, lx, ly);
      });
    };
    img.src = frame;
  }, [frame, coordinates]);

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    // Use canvas HTML attributes (natural resolution) vs displayed size
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = Math.round((e.clientX - rect.left) * scaleX);
    const y = Math.round((e.clientY - rect.top) * scaleY);
    // Guard: reject clicks outside the natural image bounds
    if (x < 0 || y < 0 || x >= canvas.width || y >= canvas.height) return;
    onAddCoordinate({ type: "point", x, y, frame_time: 0.0 });
  };

  return (
    <div className="space-y-4">
      <p className="text-gray-400 text-center text-sm">
        Click on the objects you want to remove. Each click adds a selection point.
      </p>

      <div className="rounded-xl overflow-hidden bg-gray-900 border border-gray-800">
        <canvas
          ref={canvasRef}
          onClick={handleClick}
          style={dims ? { aspectRatio: `${dims.w}/${dims.h}` } : undefined}
          className="w-full cursor-crosshair block"
        />
      </div>

      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-400 space-y-0.5">
          {coordinates.length === 0 ? (
            <span>No points selected</span>
          ) : (
            <div>
              <span className="text-green-400 font-medium">{coordinates.length} point{coordinates.length > 1 ? "s" : ""} selected</span>
              <div className="text-xs text-gray-500 mt-0.5">
                {coordinates.map((c, i) => (
                  <span key={i} className="mr-3">#{i+1}: ({c.x}, {c.y})</span>
                ))}
                {dims && <span className="text-gray-600">— frame {dims.w}×{dims.h}px</span>}
              </div>
            </div>
          )}
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={onClear} disabled={coordinates.length === 0}>
            Clear
          </Button>
          <Button onClick={onRemove} disabled={coordinates.length === 0}>
            Remove Objects
          </Button>
        </div>
      </div>
    </div>
  );
}
