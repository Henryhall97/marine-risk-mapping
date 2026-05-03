"use client";

/**
 * Whale breach silhouette — a whale arcing out of the water with splash particles.
 * Dramatic hero/footer animation. Loops continuously with a pause between breaches.
 */
export default function WhaleBreach({
  className = "",
  width = 200,
  height = 160,
}: {
  className?: string;
  width?: number;
  height?: number;
}) {
  return (
    <div
      className={`relative overflow-hidden ${className}`}
      style={{ width, height }}
    >
      {/* Water line */}
      <div
        className="absolute left-0 right-0"
        style={{ top: height * 0.6 }}
      >
        <svg
          viewBox="0 0 200 20"
          className="w-full text-ocean-500/20"
          preserveAspectRatio="none"
        >
          <path
            d="M0,10 Q25,2 50,10 T100,10 T150,10 T200,10"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            style={{ animation: "wave-drift 6s linear infinite" }}
          />
          <path
            d="M0,14 Q30,6 60,14 T120,14 T180,14 T200,14"
            fill="none"
            stroke="currentColor"
            strokeWidth="1"
            opacity="0.5"
            style={{ animation: "wave-drift 8s linear infinite" }}
          />
        </svg>
      </div>

      {/* Breaching whale silhouette */}
      <div
        className="absolute left-1/2 -translate-x-1/2"
        style={{
          top: height * 0.15,
          animation: "breach-arc 5s ease-in-out infinite",
        }}
      >
        <svg
          viewBox="0 0 80 120"
          className="text-ocean-400/70"
          fill="currentColor"
          style={{ width: width * 0.35, height: height * 0.65 }}
        >
          {/* Stylised whale body — elongated, arcing pose */}
          <ellipse cx="40" cy="55" rx="16" ry="40" />
          {/* Head */}
          <ellipse cx="40" cy="20" rx="12" ry="14" />
          {/* Fluke */}
          <path d="M28 90 Q20 98 14 94 Q22 100 32 96 L40 100 L48 96 Q58 100 66 94 Q60 98 52 90 Z" />
          {/* Pectoral fin */}
          <path d="M25 48 Q12 56 10 52 Q18 60 26 54 Z" opacity="0.6" />
          {/* Eye */}
          <circle cx="36" cy="18" r="1.5" fill="rgba(0,0,0,0.4)" />
        </svg>
      </div>

      {/* Splash droplets (scattered around water line) */}
      {Array.from({ length: 8 }).map((_, i) => {
        const angle = -90 + (i - 3.5) * 25;
        const rad = (angle * Math.PI) / 180;
        const dist = 15 + Math.random() * 25;
        return (
          <div
            key={i}
            className="absolute rounded-full bg-ocean-300/40"
            style={{
              width: 3 + Math.random() * 4,
              height: 3 + Math.random() * 4,
              left: `calc(50% + ${Math.cos(rad) * dist}px)`,
              top: height * 0.55,
              animation: `splash-drop ${0.8 + Math.random() * 0.4}s ease-out infinite`,
              animationDelay: `${2.2 + i * 0.08}s`,
            }}
          />
        );
      })}
    </div>
  );
}
