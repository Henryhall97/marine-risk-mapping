"use client";

import { useEffect, useState, useRef } from "react";

/**
 * Subtle whale silhouette that swims across the screen on scroll.
 * Ghost-like parallax Easter egg — very low opacity, drifts horizontally.
 */
export default function SwimmingWhale({
  className = "",
  direction = "left-to-right",
  opacity = 0.06,
  size = 80,
  speed = 0.15,
}: {
  className?: string;
  direction?: "left-to-right" | "right-to-left";
  opacity?: number;
  size?: number;
  speed?: number;
}) {
  const [offset, setOffset] = useState(0);
  const rafRef = useRef<number>(0);
  const lastScrollRef = useRef(0);

  useEffect(() => {
    const onScroll = () => {
      if (rafRef.current) return;
      rafRef.current = requestAnimationFrame(() => {
        const scrollY = window.scrollY;
        const delta = scrollY * speed;
        setOffset(
          direction === "left-to-right" ? delta % (window.innerWidth + size * 2) : -(delta % (window.innerWidth + size * 2)),
        );
        lastScrollRef.current = scrollY;
        rafRef.current = 0;
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [direction, speed, size]);

  // Gentle vertical bob using sine
  const verticalBob = Math.sin(offset * 0.02) * 6;

  return (
    <div
      className={`pointer-events-none fixed z-0 ${className}`}
      style={{
        opacity,
        transform: `translateX(${offset - size}px) translateY(${verticalBob}px)`,
        transition: "transform 0.1s linear",
      }}
    >
      <svg
        viewBox="0 0 120 40"
        fill="currentColor"
        className="text-ocean-400"
        style={{ width: size, height: size * 0.33 }}
        aria-hidden="true"
      >
        {/* Simplified whale side-profile */}
        <ellipse cx="55" cy="20" rx="42" ry="14" />
        {/* Head bulge */}
        <ellipse cx="18" cy="18" rx="16" ry="12" />
        {/* Fluke */}
        <path d="M95 16 Q108 6 115 8 Q105 14 100 20 Q105 26 115 32 Q108 34 95 24 Z" />
        {/* Eye */}
        <circle cx="14" cy="16" r="1.5" fill="rgba(0,0,0,0.3)" />
        {/* Pectoral fin */}
        <path d="M40 28 Q36 38 32 36 Q38 34 42 28 Z" opacity="0.5" />
      </svg>
    </div>
  );
}
