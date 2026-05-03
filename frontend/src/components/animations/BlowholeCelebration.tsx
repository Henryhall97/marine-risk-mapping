"use client";

import { useState, useEffect, useCallback } from "react";

/**
 * Blowhole spout celebration — a V-shaped spray burst triggered
 * on success events (classification complete, interaction submitted).
 * Call `trigger()` to fire the animation. Auto-dismisses after duration.
 */
export function useBlowholeCelebration(duration = 2000) {
  const [active, setActive] = useState(false);

  const trigger = useCallback(() => {
    setActive(true);
  }, []);

  useEffect(() => {
    if (!active) return;
    const timer = setTimeout(() => setActive(false), duration);
    return () => clearTimeout(timer);
  }, [active, duration]);

  return { active, trigger };
}

/** Pre-computed droplet trajectories */
const DROPLETS = Array.from({ length: 16 }).map((_, i) => {
  const angle = -90 + (i - 7.5) * 12 + Math.random() * 8;
  const rad = (angle * Math.PI) / 180;
  const dist = 30 + Math.random() * 50;
  return {
    dx: Math.cos(rad) * dist,
    dy: Math.sin(rad) * dist - 10,
    size: 2 + Math.random() * 4,
    delay: Math.random() * 0.2,
    duration: 0.6 + Math.random() * 0.4,
  };
});

export default function BlowholeCelebration({
  active,
  className = "",
}: {
  active: boolean;
  className?: string;
}) {
  if (!active) return null;

  return (
    <div
      className={`pointer-events-none fixed inset-0 z-[60] flex items-center justify-center ${className}`}
    >
      {/* Central spout column */}
      <div className="relative">
        {/* V-shaped spray */}
        <svg
          viewBox="0 0 60 80"
          className="absolute left-1/2 -translate-x-1/2 text-bioluminescent-400"
          style={{
            width: 60,
            height: 80,
            bottom: 0,
            animation: `spout-burst ${1}s ease-out forwards`,
            transformOrigin: "50% 100%",
          }}
          fill="currentColor"
        >
          <path
            d="M30 80 L22 40 Q18 20 10 10 M30 80 L38 40 Q42 20 50 10"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            opacity="0.6"
          />
          <path
            d="M30 80 L26 45 Q22 25 16 15 M30 80 L34 45 Q38 25 44 15"
            fill="none"
            stroke="currentColor"
            strokeWidth="1"
            opacity="0.3"
          />
        </svg>

        {/* Spray droplets */}
        {DROPLETS.map((d, i) => (
          <div
            key={i}
            className="absolute rounded-full bg-bioluminescent-400/70"
            style={{
              width: d.size,
              height: d.size,
              left: "50%",
              top: "50%",
              "--dx": `${d.dx}px`,
              "--dy": `${d.dy}px`,
              animation: `spout-droplet ${d.duration}s ease-out ${d.delay}s forwards`,
            } as React.CSSProperties}
          />
        ))}

        {/* Glow flash */}
        <div
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{
            width: 120,
            height: 120,
            background:
              "radial-gradient(circle, rgba(103,232,249,0.25) 0%, transparent 70%)",
            animation: "spout-burst 1.2s ease-out forwards",
            transformOrigin: "50% 50%",
          }}
        />
      </div>
    </div>
  );
}
