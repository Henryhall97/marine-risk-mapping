"use client";

import { useEffect, useRef, useState, useCallback } from "react";

interface AudioWaveformProps {
  /** URL to the audio file */
  src: string;
  /** Optional label */
  label?: string;
  /** Height in px */
  height?: number;
  /** Waveform colour (unplayed portion) */
  color?: string;
  /** Progress colour (played portion) */
  progressColor?: string;
}

/**
 * Audio waveform visualiser — renders a canvas waveform from an audio
 * file with playback controls, time display, and click-to-seek.
 */
export default function AudioWaveform({
  src,
  label,
  height = 80,
  color = "#334155",
  progressColor = "#38bdf8",
}: AudioWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const animRef = useRef<number>(0);
  const waveDataRef = useRef<Float32Array | null>(null);

  const [playing, setPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* ── Decode audio → waveform data ────────────────────── */

  useEffect(() => {
    let cancelled = false;
    setLoaded(false);
    setError(null);

    (async () => {
      try {
        const res = await fetch(src);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const buf = await res.arrayBuffer();

        const ctx = new AudioContext();
        const decoded = await ctx.decodeAudioData(buf);
        ctx.close();

        if (cancelled) return;

        // Down-sample to ~1000 bars for the canvas
        const raw = decoded.getChannelData(0);
        const bars = Math.min(raw.length, 1000);
        const step = Math.floor(raw.length / bars);
        const peaks = new Float32Array(bars);
        for (let i = 0; i < bars; i++) {
          let max = 0;
          for (let j = 0; j < step; j++) {
            const abs = Math.abs(raw[i * step + j]);
            if (abs > max) max = abs;
          }
          peaks[i] = max;
        }

        waveDataRef.current = peaks;
        setDuration(decoded.duration);
        setLoaded(true);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load audio");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [src]);

  /* ── Draw waveform ────────────────────────────────────── */

  const draw = useCallback(
    (progress: number) => {
      const canvas = canvasRef.current;
      const data = waveDataRef.current;
      if (!canvas || !data) return;

      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;

      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        ctx.scale(dpr, dpr);
      }

      ctx.clearRect(0, 0, w, h);

      const barW = Math.max(1, w / data.length - 0.5);
      const mid = h / 2;
      const progressX = progress * w;

      for (let i = 0; i < data.length; i++) {
        const x = (i / data.length) * w;
        const barH = Math.max(1, data[i] * mid * 0.95);
        ctx.fillStyle = x < progressX ? progressColor : color;
        ctx.fillRect(x, mid - barH, barW, barH * 2);
      }
    },
    [color, progressColor],
  );

  /* ── Animation loop for playback ──────────────────────── */

  useEffect(() => {
    if (!loaded) return;

    const tick = () => {
      const audio = audioRef.current;
      if (audio && duration > 0) {
        setCurrentTime(audio.currentTime);
        draw(audio.currentTime / duration);
      }
      animRef.current = requestAnimationFrame(tick);
    };

    if (playing) {
      animRef.current = requestAnimationFrame(tick);
    } else {
      cancelAnimationFrame(animRef.current);
      draw(duration > 0 ? currentTime / duration : 0);
    }

    return () => cancelAnimationFrame(animRef.current);
  }, [playing, loaded, duration, currentTime, draw]);

  /* ── Initial draw once loaded ─────────────────────────── */

  useEffect(() => {
    if (loaded) draw(0);
  }, [loaded, draw]);

  /* ── Handlers ─────────────────────────────────────────── */

  function togglePlay() {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause();
      setPlaying(false);
    } else {
      audio.play();
      setPlaying(true);
    }
  }

  function handleCanvasClick(e: React.MouseEvent<HTMLCanvasElement>) {
    const audio = audioRef.current;
    const canvas = canvasRef.current;
    if (!audio || !canvas || !duration) return;

    const rect = canvas.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    audio.currentTime = pct * duration;
    setCurrentTime(audio.currentTime);
    draw(pct);
  }

  function handleEnded() {
    setPlaying(false);
    setCurrentTime(0);
    draw(0);
  }

  function formatTime(s: number): string {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  }

  /* ── Render ───────────────────────────────────────────── */

  if (error) {
    /* Fallback: waveform decode failed (e.g. unusual sample rate),
       but the browser's native <audio> player may still handle it. */
    return (
      <div className="space-y-2">
        {label && (
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            {label}
          </p>
        )}
        <div
          className="relative flex items-center justify-center overflow-hidden rounded-lg border border-ocean-800 bg-abyss-800"
          style={{ height }}
        >
          {/* Decorative static bars */}
          <div className="flex items-center gap-[3px] opacity-30">
            {Array.from({ length: 40 }, (_, i) => (
              <div
                key={i}
                className="w-[3px] rounded-full bg-ocean-600"
                style={{
                  height: `${20 + Math.sin(i * 0.4) * 15 + Math.random() * 10}%`,
                }}
              />
            ))}
          </div>
        </div>
        <audio controls src={src} className="w-full [&]:h-10" preload="metadata">
          <track kind="captions" />
        </audio>
        <a
          href={src}
          download
          className="inline-block text-xs text-ocean-400 hover:text-ocean-300"
        >
          ⬇ Download
        </a>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {label && (
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          {label}
        </p>
      )}

      {/* Waveform canvas */}
      <div
        className="relative overflow-hidden rounded-lg border border-ocean-800 bg-abyss-800"
        style={{ height }}
      >
        {!loaded && (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-slate-500">
            Decoding audio…
          </div>
        )}
        <canvas
          ref={canvasRef}
          className="h-full w-full cursor-pointer"
          onClick={handleCanvasClick}
        />
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3">
        <button
          onClick={togglePlay}
          disabled={!loaded}
          className="flex h-8 w-8 items-center justify-center rounded-full bg-ocean-600 text-white transition-colors hover:bg-ocean-500 disabled:opacity-40"
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? (
            <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="currentColor">
              <rect x="3" y="2" width="4" height="12" rx="1" />
              <rect x="9" y="2" width="4" height="12" rx="1" />
            </svg>
          ) : (
            <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 ml-0.5" fill="currentColor">
              <path d="M4 2l10 6-10 6z" />
            </svg>
          )}
        </button>

        <span className="text-xs tabular-nums text-slate-400">
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>

        {/* Download link */}
        <a
          href={src}
          download
          className="ml-auto text-xs text-ocean-400 hover:text-ocean-300"
        >
          ⬇ Download
        </a>
      </div>

      {/* Hidden <audio> element */}
      <audio
        ref={audioRef}
        src={src}
        preload="none"
        onEnded={handleEnded}
      />
    </div>
  );
}
