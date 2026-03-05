/**
 * Organic wave divider SVG. Place between page sections.
 * `flip` mirrors it vertically; `color` sets the fill.
 */
export default function WaveDivider({
  className = "",
  flip = false,
  color = "var(--abyss-surface, #0b1a30)",
}: {
  className?: string;
  flip?: boolean;
  color?: string;
}) {
  return (
    <div
      className={`w-full overflow-hidden leading-none ${flip ? "rotate-180" : ""} ${className}`}
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 1440 120"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="relative block w-full"
        preserveAspectRatio="none"
        style={{ height: "80px" }}
      >
        {/* Back wave — subtle */}
        <path
          d="M0 60L48 55C96 50 192 40 288 42C384 44 480 58 576 64C672 70 768 68 864 60C960 52 1056 38 1152 35C1248 32 1344 40 1392 44L1440 48V120H0Z"
          fill={color}
          opacity="0.4"
        />
        {/* Front wave — primary */}
        <path
          d="M0 80L48 76C96 72 192 64 288 60C384 56 480 56 576 62C672 68 768 80 864 82C960 84 1056 76 1152 68C1248 60 1344 52 1392 48L1440 44V120H0Z"
          fill={color}
        />
      </svg>
    </div>
  );
}
