"use client";

export default function DivingWhaleLoader({
  className = "",
  size = 64,
  label = "Loading...",
}: {
  className?: string;
  size?: number;
  label?: string;
}) {
  return (
    <div className={`flex flex-col items-center gap-4 ${className}`}>
      {/* Whale + spout */}
      <div
        className="relative"
        style={{
          width: size * 1.6,
          height: size,
          animation: "whale-float 3s ease-in-out infinite",
        }}
      >
        {/* V-shaped blow spout */}
        <svg
          viewBox="0 0 20 24"
          className="absolute text-ocean-300/60"
          style={{
            width: size * 0.22,
            height: size * 0.3,
            left: "12%",
            top: "-22%",
            animation: "spout-burst 3s ease-out infinite",
          }}
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M10 24 L3 8 Q0 0 5 2 L10 10 L15 2 Q20 0 17 8 Z" />
        </svg>

        {/* Whale silhouette — proper side-profile humpback */}
        <svg
          viewBox="0 0 160 80"
          fill="currentColor"
          className="text-ocean-400"
          style={{ width: size * 1.6, height: size }}
          aria-hidden="true"
        >
          {/* Main body */}
          <path d="
            M 24,46
            C 20,38 24,26 36,22
            C 48,18 66,18 82,20
            C 100,22 116,26 126,32
            L 138,20 L 136,34 L 140,48
            L 126,42
            C 116,48 100,52 82,54
            C 66,56 48,54 36,50
            C 28,48 24,50 24,46 Z
          " />
          {/* Dorsal fin */}
          <path d="M 88,20 C 92,10 100,6 104,12 L 98,22 Z" />
          {/* Pectoral fin */}
          <path
            d="M 68,50 C 62,62 52,66 46,60 C 56,56 64,52 66,44 Z"
            opacity="0.6"
          />
          {/* Eye */}
          <circle cx="36" cy="36" r="3" fill="rgba(0,0,0,0.25)" />
          <circle cx="35" cy="35" r="1.2" fill="rgba(255,255,255,0.3)" />
        </svg>

        {/* Water surface line */}
        <div
          className="absolute bottom-0 left-0 h-px w-full rounded-full"
          style={{
            background:
              "linear-gradient(90deg,transparent 0%,rgba(8,145,178,0.35) 50%,transparent 100%)",
            animation: "glow-pulse 3s ease-in-out infinite",
          }}
        />
      </div>

      {label && (
        <span className="text-xs font-medium tracking-wide text-ocean-400/70">
          {label}
        </span>
      )}

      {/* Bubble dots */}
      <div className="flex gap-1.5">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-1.5 w-1.5 rounded-full bg-bioluminescent-400/40"
            style={{
              animation: "glow-pulse 1.5s ease-in-out infinite",
              animationDelay: `${i * 0.3}s`,
            }}
          />
        ))}
      </div>

      <style>{`
        @keyframes whale-float {
          0%, 100% { transform: translateY(0px); }
          50%       { transform: translateY(-6px); }
        }
        @keyframes spout-burst {
          0%, 60%, 100% { opacity: 0; transform: scaleY(0.3); }
          70%            { opacity: 1; transform: scaleY(1); }
          90%            { opacity: 0; transform: scaleY(1.1); }
        }
      `}</style>
    </div>
  );
}
