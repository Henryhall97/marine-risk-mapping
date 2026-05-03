"use client";

/* Deterministic seeded PRNG — same output on server & client */
function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

/**
 * Underwater caustic light rays — animated refracted sunlight patterns
 * as a subtle background layer. Evokes the dancing light patterns
 * visible just below the ocean surface.
 */
export default function CausticRays({
  className = "",
  rayCount = 5,
  opacity = 0.04,
}: {
  className?: string;
  rayCount?: number;
  opacity?: number;
}) {
  const rng = seededRandom(7919);
  return (
    <div
      className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`}
      aria-hidden="true"
    >
      {/* Diagonal light shafts */}
      {Array.from({ length: rayCount }).map((_, i) => {
        const left = 10 + i * (80 / rayCount) + rng() * 10;
        const width = 60 + rng() * 140;
        const skew = -15 + rng() * 30;
        const dur = 8 + rng() * 8;
        const delay = rng() * 6;

        return (
          <div
            key={i}
            className="absolute"
            style={{
              left: `${left}%`,
              top: "-20%",
              width: `${width}px`,
              height: "140%",
              background: `linear-gradient(180deg, rgba(34,211,238,${opacity * 1.5}) 0%, rgba(8,145,178,${opacity}) 40%, transparent 80%)`,
              transform: `skewX(${skew}deg)`,
              animation: `caustic-shift ${dur}s ease-in-out ${delay}s infinite`,
              filter: "blur(30px)",
            }}
          />
        );
      })}

      {/* Dappled light spots */}
      {Array.from({ length: 8 }).map((_, i) => {
        const x = 5 + rng() * 90;
        const y = 5 + rng() * 90;
        const size = 80 + rng() * 160;
        const dur = 6 + rng() * 10;
        const delay = rng() * 8;

        return (
          <div
            key={`spot-${i}`}
            className="absolute rounded-full"
            style={{
              left: `${x}%`,
              top: `${y}%`,
              width: size,
              height: size,
              background: `radial-gradient(circle, rgba(34,211,238,${opacity * 1.2}) 0%, transparent 70%)`,
              animation: `caustic-shimmer ${dur}s ease-in-out ${delay}s infinite`,
            }}
          />
        );
      })}
    </div>
  );
}
