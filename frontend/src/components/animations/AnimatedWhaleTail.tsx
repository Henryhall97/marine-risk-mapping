"use client";

/**
 * Animated whale tail (fluke) that performs a gentle tail-flick motion.
 * Drop-in replacement for the static WhaleTail with configurable animation.
 */
export default function AnimatedWhaleTail({
  className = "h-12 w-12",
  animate = true,
  glowColor = "rgba(34,211,238,0.25)",
}: {
  className?: string;
  animate?: boolean;
  glowColor?: string;
}) {
  return (
    <div
      className={`inline-flex items-center justify-center ${className}`}
      style={{
        filter: animate
          ? `drop-shadow(0 0 12px ${glowColor})`
          : undefined,
      }}
    >
      <svg
        viewBox="0 0 64 48"
        fill="currentColor"
        xmlns="http://www.w3.org/2000/svg"
        className="h-full w-full"
        aria-hidden="true"
        style={{
          animation: animate
            ? "tail-flick 4s ease-in-out infinite"
            : undefined,
          transformOrigin: "50% 85%",
        }}
      >
        {/* Left fluke */}
        <path d="M4 4C4 4 8 20 20 28C14 26 6 28 2 36C8 32 16 30 24 32L32 40L40 32C48 30 56 32 62 36C58 28 50 26 44 28C56 20 60 4 60 4C52 12 44 18 36 22L32 24L28 22C20 18 12 12 4 4Z" />
        {/* Central ridge */}
        <path
          d="M32 24L32 44"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          opacity="0.3"
        />
      </svg>
    </div>
  );
}
