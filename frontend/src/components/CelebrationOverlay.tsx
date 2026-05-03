"use client";

/**
 * Celebration overlay shown after a successful sighting report.
 * Features the 3D humpback whale GLB model doing a dramatic
 * leap/dive animation with expanding water-ripple rings
 * radiating from the center.
 *
 * Three.js scene is dynamically imported (SSR-unsafe) —
 * the overlay shell itself is SSR-safe.
 */

import { useEffect, useState, useCallback } from "react";
import dynamic from "next/dynamic";

const WhaleScene = dynamic(
  () => import("./CelebrationWhaleScene"),
  { ssr: false, loading: () => null },
);

/* ── Seeded PRNG (SSR-safe deterministic values) ── */

function seededRandom(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

/* ── Types ── */

interface CelebrationOverlayProps {
  show: boolean;
  onClose: () => void;
}

/* ── Component ── */

export default function CelebrationOverlay({
  show,
  onClose,
}: CelebrationOverlayProps) {
  type Phase = "hidden" | "enter" | "visible" | "exit";
  const [phase, setPhase] = useState<Phase>("hidden");
  const alive = phase === "enter" || phase === "visible";

  /* Phase state-machine — no auto-dismiss, only on click */
  useEffect(() => {
    if (show && phase === "hidden") setPhase("enter");
  }, [show, phase]);

  useEffect(() => {
    if (phase === "enter") {
      const id = setTimeout(() => setPhase("visible"), 100);
      return () => clearTimeout(id);
    }
    if (phase === "exit") {
      const id = setTimeout(() => {
        setPhase("hidden");
        onClose();
      }, 600);
      return () => clearTimeout(id);
    }
  }, [phase, onClose]);

  const dismiss = useCallback(() => {
    if (phase === "visible" || phase === "enter") setPhase("exit");
  }, [phase]);

  if (phase === "hidden") return null;

  /* ── Ripple rings (expanding ovals from center) ── */
  const ripples = Array.from({ length: 10 }, (_, i) => ({
    delay: 0.3 + i * 0.28,
    dur: 2.8 + i * 0.15,
    opacity: 0.55 - i * 0.04,
  }));

  /* ── Water spray particles ── */
  const rng = seededRandom(271);
  const drops = Array.from({ length: 55 }, (_, i) => {
    const angle = rng() * Math.PI * 2;
    const dist = 35 + rng() * 160;
    return {
      id: i,
      dx: Math.cos(angle) * dist,
      dy:
        -Math.abs(Math.sin(angle) * dist * 0.7) -
        15 -
        rng() * 70,
      sz: 2 + rng() * 5,
      del: 0.15 + rng() * 0.7,
      op: 0.25 + rng() * 0.45,
    };
  });

  return (
    <div
      className={
        "fixed inset-0 z-[9999] flex flex-col items-center"
        + " justify-center transition-opacity duration-500 "
        + (phase === "exit" ? "opacity-0" : "opacity-100")
      }
      style={{
        background:
          "radial-gradient(ellipse at 50% 45%,"
          + " rgba(2,12,26,0.82) 0%,"
          + " rgba(0,0,0,0.92) 100%)",
      }}
      onClick={dismiss}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Escape" && dismiss()}
    >
      {/* ── Expanding ripple rings ── */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {ripples.map((r, i) => (
          <div
            key={i}
            className={
              "absolute left-1/2 top-[42%]"
              + " -translate-x-1/2 -translate-y-1/2"
            }
            style={{
              borderRadius: "50%",
              border:
                `1.5px solid rgba(56,189,248,${r.opacity})`,
              boxShadow:
                `0 0 12px rgba(56,189,248,${r.opacity * 0.35}),`
                + ` inset 0 0 8px rgba(56,189,248,`
                + `${r.opacity * 0.15})`,
              animation: alive
                ? `cel-ripple ${r.dur}s ease-out`
                  + ` ${r.delay}s infinite both`
                : "none",
            }}
          />
        ))}
      </div>

      {/* ── Central glow (whale splash point) ── */}
      <div
        className={
          "pointer-events-none absolute left-1/2 top-[42%]"
          + " -translate-x-1/2 -translate-y-1/2 rounded-full"
        }
        style={{
          width: 140,
          height: 55,
          background:
            "radial-gradient(ellipse,"
            + " rgba(56,189,248,0.25) 0%,"
            + " rgba(56,189,248,0.05) 60%,"
            + " transparent 100%)",
          animation: alive
            ? "cel-glow-pulse 2s ease-in-out 0.5s infinite both"
            : "none",
        }}
      />

      {/* ── Spray particles ── */}
      <div
        className={
          "pointer-events-none absolute inset-0 overflow-hidden"
        }
      >
        {drops.map((d) => (
          <div
            key={d.id}
            className="absolute left-1/2 top-[42%] rounded-full"
            style={{
              width: d.sz,
              height: d.sz,
              background:
                `rgba(147,197,253,${d.op})`,
              boxShadow:
                `0 0 ${d.sz * 2}px rgba(56,189,248,0.2)`,
              animation: alive
                ? `cel-spray ${0.9 + d.del * 0.5}s ease-out`
                  + ` ${d.del}s both`
                : "none",
              ["--sdx" as string]: `${d.dx}px`,
              ["--sdy" as string]: `${d.dy}px`,
            }}
          />
        ))}
      </div>

      {/* ── Text (behind whale, no background) ── */}
      <div
        className={
          "pointer-events-none absolute inset-x-0 bottom-0"
          + " z-10 flex flex-col items-center pb-10 pt-16"
        }
      >
        <h2
          className={
            "font-display text-3xl font-bold tracking-tight"
            + " text-white sm:text-4xl"
          }
          style={{
            animation: alive
              ? "cel-text-in 0.7s ease-out 0.8s both"
              : "none",
            textShadow:
              "0 2px 30px rgba(0,0,0,0.8),"
              + " 0 0 60px rgba(0,0,0,0.4)",
          }}
        >
          Thank you for your report!
        </h2>
        <p
          className={
            "mt-2.5 text-sm text-ocean-200/80 sm:text-base"
          }
          style={{
            animation: alive
              ? "cel-text-in 0.7s ease-out 1s both"
              : "none",
            textShadow: "0 1px 12px rgba(0,0,0,0.6)",
          }}
        >
          Every interaction helps protect whales
          from ship strikes
        </p>
        <p
          className="mt-4 text-xs text-slate-400"
          style={{
            animation: alive
              ? "cel-text-in 0.6s ease-out 1.3s both"
              : "none",
          }}
        >
          click anywhere to close
        </p>
      </div>

      {/* ── 3D humpback whale (last child = paints on top) ── */}
      <div
        className="pointer-events-none absolute inset-0 z-50"
        style={{
          animation: alive
            ? "cel-scene-in 0.9s ease-out 0.05s both"
            : "none",
        }}
      >
        <WhaleScene playing={alive} />
      </div>

      {/* ── Keyframes ── */}
      <style jsx>{`
        @keyframes cel-ripple {
          0% {
            width: 0;
            height: 0;
            opacity: 0.8;
            transform: translate(-50%, -50%) scaleY(0.4);
          }
          100% {
            width: min(170vw, 1700px);
            height: min(170vw, 1700px);
            opacity: 0;
            transform: translate(-50%, -50%) scaleY(0.4);
          }
        }
        @keyframes cel-spray {
          0% {
            transform: translate(0, 0) scale(1);
            opacity: 0;
          }
          8% {
            opacity: 0.7;
          }
          100% {
            transform: translate(
              var(--sdx, 0),
              var(--sdy, -80px)
            )
              scale(0.12);
            opacity: 0;
          }
        }
        @keyframes cel-scene-in {
          0% {
            opacity: 0;
          }
          100% {
            opacity: 1;
          }
        }
        @keyframes cel-glow-pulse {
          0%,
          100% {
            opacity: 0.5;
            transform: translate(-50%, -50%) scale(1);
          }
          50% {
            opacity: 0.8;
            transform: translate(-50%, -50%) scale(1.3);
          }
        }
        @keyframes cel-text-in {
          0% {
            opacity: 0;
            transform: translateY(20px) scale(0.95);
          }
          100% {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }
      `}</style>
    </div>
  );
}
