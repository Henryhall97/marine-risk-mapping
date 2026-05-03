"use client";

import { useEffect, useRef } from "react";

/**
 * Whale song waveform divider — an animated, organic sine wave that
 * evokes a whale song spectrogram. Replaces static WaveDivider
 * between sections for a living, breathing feel.
 */
export default function WhaleSongDivider({
  className = "",
  height = 60,
  waveCount = 3,
  color = "rgba(8,145,178,0.25)",
  accentColor = "rgba(34,211,238,0.15)",
}: {
  className?: string;
  height?: number;
  waveCount?: number;
  color?: string;
  accentColor?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const timeRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio;
      canvas.height = height * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };
    resize();
    window.addEventListener("resize", resize);

    const drawWave = (
      t: number,
      amplitude: number,
      frequency: number,
      phase: number,
      strokeColor: string,
      lineWidth: number,
    ) => {
      const w = canvas.offsetWidth;
      const mid = height / 2;
      ctx.beginPath();
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = lineWidth;
      ctx.lineCap = "round";

      for (let x = 0; x <= w; x += 2) {
        const normalX = x / w;
        // Envelope: fade edges
        const envelope =
          Math.sin(normalX * Math.PI) *
          (0.6 + 0.4 * Math.sin(normalX * 4 + t * 0.3));
        // Multi-frequency organic shape
        const y =
          mid +
          amplitude *
            envelope *
            (Math.sin(normalX * frequency + t + phase) +
              0.3 * Math.sin(normalX * frequency * 2.3 + t * 1.4 + phase) +
              0.15 * Math.sin(normalX * frequency * 4.7 + t * 0.7));
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    };

    const animate = () => {
      timeRef.current += 0.015;
      const t = timeRef.current;
      const w = canvas.offsetWidth;

      ctx.clearRect(0, 0, w, height);

      // Background waves (wide, low amplitude)
      for (let i = 0; i < waveCount; i++) {
        const amp = 6 + i * 3;
        const freq = 8 + i * 4;
        const phase = i * 2.1;
        const alpha = 0.08 + i * 0.04;
        drawWave(
          t + i * 0.5,
          amp,
          freq,
          phase,
          `rgba(8,145,178,${alpha})`,
          1.5 - i * 0.2,
        );
      }

      // Accent wave (brighter, sharper)
      drawWave(t * 0.8, 10, 14, 0, accentColor, 2);

      // "Pulse" dots — like clicks in whale song
      for (let i = 0; i < 5; i++) {
        const px =
          ((t * 30 + i * w * 0.22) % (w + 40)) - 20;
        const normalPx = px / w;
        const py =
          height / 2 +
          8 *
            Math.sin(normalPx * 12 + t) *
            Math.sin(normalPx * Math.PI);
        const pulseAlpha =
          0.3 *
          Math.sin(normalPx * Math.PI) *
          (0.5 + 0.5 * Math.sin(t * 2 + i));

        if (pulseAlpha > 0.05) {
          ctx.beginPath();
          ctx.arc(px, py, 2, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(103,232,249,${pulseAlpha})`;
          ctx.fill();

          // Glow
          ctx.beginPath();
          ctx.arc(px, py, 6, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(103,232,249,${pulseAlpha * 0.3})`;
          ctx.fill();
        }
      }

      animRef.current = requestAnimationFrame(animate);
    };

    animRef.current = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(animRef.current);
    };
  }, [height, waveCount, color, accentColor]);

  return (
    <div className={`w-full ${className}`} style={{ height }}>
      <canvas
        ref={canvasRef}
        className="h-full w-full"
        style={{ height }}
        aria-hidden="true"
      />
    </div>
  );
}
