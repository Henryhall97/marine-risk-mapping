"use client";

/**
 * Pod formation section divider — 3-5 small whale silhouettes swimming
 * in staggered formation across the full width. An organic, living
 * alternative to the static WaveDivider.
 */

const WHALES = [
  { delay: 0, scale: 1, y: 12, speed: 5.5 },
  { delay: 0.8, scale: 0.8, y: 22, speed: 6.2 },
  { delay: 0.3, scale: 0.9, y: 8, speed: 5.0 },
  { delay: 1.5, scale: 0.7, y: 28, speed: 6.8 },
  { delay: 0.6, scale: 0.85, y: 18, speed: 5.8 },
];

export default function PodFormation({
  className = "",
  height = 48,
  whaleCount = 5,
  color = "text-ocean-400/[0.12]",
}: {
  className?: string;
  height?: number;
  whaleCount?: number;
  color?: string;
}) {
  const whales = WHALES.slice(0, whaleCount);

  return (
    <div
      className={`relative w-full overflow-hidden ${className}`}
      style={{ height }}
      aria-hidden="true"
    >
      {/* Faint water line */}
      <div
        className="absolute left-0 right-0 top-1/2 h-px -translate-y-1/2"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, rgba(8,145,178,0.1) 20%, rgba(8,145,178,0.15) 50%, rgba(8,145,178,0.1) 80%, transparent 100%)",
        }}
      />

      {whales.map((w, i) => (
        <div
          key={i}
          className={`absolute ${color}`}
          style={{
            top: w.y,
            left: `${10 + i * 18}%`,
            transform: `scale(${w.scale})`,
            animation: `pod-swim ${w.speed}s ease-in-out ${w.delay}s infinite`,
          }}
        >
          <svg
            viewBox="0 0 60 20"
            fill="currentColor"
            style={{ width: 40 * w.scale, height: 14 * w.scale }}
          >
            {/* Sleek side-profile whale */}
            <ellipse cx="28" cy="10" rx="22" ry="7" />
            {/* Head */}
            <ellipse cx="10" cy="9" rx="8" ry="6" />
            {/* Fluke */}
            <path d="M48 8 Q54 3 58 5 Q53 8 50 10 Q53 12 58 15 Q54 17 48 12 Z" />
            {/* Dorsal fin */}
            <path d="M30 4 Q33 0 36 4 Z" opacity="0.6" />
          </svg>
        </div>
      ))}

      {/* Trailing tiny bubbles per whale */}
      {whales.map((w, i) => (
        <div
          key={`b-${i}`}
          className="absolute"
          style={{
            top: w.y + 4,
            left: `${14 + i * 18}%`,
            animation: `pod-swim ${w.speed}s ease-in-out ${w.delay + 0.3}s infinite`,
          }}
        >
          {[0, 1, 2].map((b) => (
            <div
              key={b}
              className="mb-0.5 inline-block rounded-full bg-bioluminescent-400/[0.08]"
              style={{
                width: 2 + b,
                height: 2 + b,
                marginLeft: b * 3,
                animation: `glow-pulse ${2 + b}s ease-in-out ${w.delay + b * 0.4}s infinite`,
              }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
