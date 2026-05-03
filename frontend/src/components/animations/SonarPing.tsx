"use client";

/**
 * Sonar ping pulse — concentric rings expanding outward from a central whale icon.
 * Perfect for classify page headers, audio processing states, and loading indicators.
 */
export default function SonarPing({
  className = "",
  size = 120,
  ringCount = 4,
  color = "rgba(34,211,238,0.35)",
  active = true,
}: {
  className?: string;
  size?: number;
  ringCount?: number;
  color?: string;
  active?: boolean;
}) {
  return (
    <div
      className={`relative inline-flex items-center justify-center ${className}`}
      style={{ width: size, height: size }}
    >
      {/* Expanding sonar rings */}
      {active &&
        Array.from({ length: ringCount }).map((_, i) => (
          <div
            key={i}
            className="absolute inset-0 rounded-full"
            style={{
              border: `1.5px solid ${color}`,
              animation: `sonar-ring ${2.4 + i * 0.2}s ease-out infinite`,
              animationDelay: `${i * 0.6}s`,
            }}
          />
        ))}

      {/* Center icon — small whale */}
      <svg
        viewBox="0 0 64 48"
        fill="currentColor"
        className="relative z-10 text-bioluminescent-400"
        style={{ width: size * 0.3, height: size * 0.22 }}
        aria-hidden="true"
      >
        <path d="M4 4C4 4 8 20 20 28C14 26 6 28 2 36C8 32 16 30 24 32L32 40L40 32C48 30 56 32 62 36C58 28 50 26 44 28C56 20 60 4 60 4C52 12 44 18 36 22L32 24L28 22C20 18 12 12 4 4Z" />
      </svg>

      {/* Faint static glow behind center */}
      <div
        className="absolute rounded-full"
        style={{
          width: size * 0.4,
          height: size * 0.4,
          background: `radial-gradient(circle, ${color} 0%, transparent 70%)`,
          animation: active
            ? "glow-pulse 3s ease-in-out infinite"
            : undefined,
        }}
      />
    </div>
  );
}
