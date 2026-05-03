"use client";

import { useEffect, useRef, useCallback } from "react";

/* ── Whale "views" — each selects a region of the composite sprite ── */

interface WhaleView {
  /** Human label */
  name: string;
  /** Background-position to centre on this whale (% of image) */
  bgX: number;
  bgY: number;
  /** How much to zoom in (higher = tighter crop on this whale) */
  zoom: number;
  /** Width-to-height ratio of the viewing ellipse */
  aspect: number;
  /** Base rotation of the whale in the image (degrees, 0 = facing right) */
  baseAngle: number;
}

const WHALE_VIEWS: WhaleView[] = [
  // Top whale — side profile, mostly horizontal
  { name: "top", bgX: 50, bgY: 12, zoom: 2.8, aspect: 2.2, baseAngle: 0 },
  // Upper-left whale — angled slightly downward
  { name: "upper-left", bgX: 38, bgY: 38, zoom: 2.4, aspect: 1.8, baseAngle: 15 },
  // Centre whale — the big one, horizontal
  { name: "center", bgX: 55, bgY: 48, zoom: 2.0, aspect: 2.0, baseAngle: -5 },
  // Lower-left whale — diving pose
  { name: "lower-left", bgX: 35, bgY: 78, zoom: 2.5, aspect: 1.7, baseAngle: 25 },
  // Lower-right whale — swimming right
  { name: "lower-right", bgX: 68, bgY: 78, zoom: 2.3, aspect: 1.9, baseAngle: -10 },
];

/* ── Swimming instance state ── */

interface SwimInstance {
  view: WhaleView;
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number; // height in px (width = height * aspect)
  opacity: number;
  depth: number; // 0–1, affects speed + opacity
  phase: number; // animation phase offset
  flipX: boolean; // mirror horizontally
  /** Target heading for smooth turning (radians) */
  heading: number;
  /** Current visual heading (smoothly interpolated) */
  visualHeading: number;
  /** Time until next direction change */
  turnTimer: number;
}

/* ── Seeded PRNG for deterministic init ── */

function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

/* ── Component ── */

export default function SwimmingWhaleSprites({
  className = "",
  whaleCount = 6,
  baseOpacity = 0.15,
}: {
  className?: string;
  whaleCount?: number;
  baseOpacity?: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const whalesRef = useRef<SwimInstance[]>([]);
  const animRef = useRef<number>(0);
  const timeRef = useRef(0);
  const sizeRef = useRef({ w: 0, h: 0 });
  const elemsRef = useRef<HTMLDivElement[]>([]);

  /* ── Initialise whale instances ── */
  const initWhales = useCallback(
    (w: number, h: number) => {
      const rng = seededRandom(42);
      const whales: SwimInstance[] = [];

      for (let i = 0; i < whaleCount; i++) {
        const depth = 0.2 + (i / Math.max(whaleCount - 1, 1)) * 0.8;
        const view = WHALE_VIEWS[i % WHALE_VIEWS.length];

        // Random initial heading
        const heading = (rng() - 0.5) * Math.PI * 0.6;
        const speed = 0.15 + depth * 0.35;

        whales.push({
          view,
          x: rng() * w,
          y: h * 0.08 + rng() * h * 0.84,
          vx: Math.cos(heading) * speed * (rng() > 0.5 ? 1 : -1),
          vy: Math.sin(heading) * speed * 0.3,
          size: 80 + depth * 100 + rng() * 40,
          opacity: baseOpacity * (0.4 + depth * 0.6),
          depth,
          phase: rng() * Math.PI * 2,
          flipX: rng() > 0.5,
          heading,
          visualHeading: heading,
          turnTimer: 3 + rng() * 8,
        });
      }

      whalesRef.current = whales;
    },
    [whaleCount, baseOpacity],
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    /* ── Create DOM elements for each whale ── */
    const setupElements = () => {
      container.innerHTML = "";
      elemsRef.current = [];

      for (let i = 0; i < whaleCount; i++) {
        // Outer wrapper — positions + transforms
        const wrapper = document.createElement("div");
        wrapper.style.position = "absolute";
        wrapper.style.willChange = "transform, opacity";
        wrapper.style.pointerEvents = "none";

        // Inner element — shows the composite with mask
        const inner = document.createElement("div");
        inner.style.width = "100%";
        inner.style.height = "100%";
        inner.style.backgroundImage = "url(/whales/whale_composite.png)";
        inner.style.backgroundRepeat = "no-repeat";
        inner.style.borderRadius = "50%";
        // Soft feathered edge via radial mask
        inner.style.maskImage =
          "radial-gradient(ellipse 48% 48% at center, black 55%, transparent 100%)";
        inner.style.webkitMaskImage =
          "radial-gradient(ellipse 48% 48% at center, black 55%, transparent 100%)";

        wrapper.appendChild(inner);
        container.appendChild(wrapper);
        elemsRef.current.push(wrapper);
      }
    };

    /* ── Resize handler ── */
    const resize = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      sizeRef.current = { w, h };
      if (whalesRef.current.length === 0) {
        initWhales(w, h);
        setupElements();
      }
    };
    resize();
    window.addEventListener("resize", resize);

    /* ── Animation loop ── */
    const dt = 1 / 60; // fixed timestep

    const animate = () => {
      timeRef.current += dt;
      const t = timeRef.current;
      const { w, h } = sizeRef.current;

      for (let i = 0; i < whalesRef.current.length; i++) {
        const whale = whalesRef.current[i];
        const el = elemsRef.current[i];
        if (!el) continue;

        /* ── Direction changes ── */
        whale.turnTimer -= dt;
        if (whale.turnTimer <= 0) {
          // Pick a new gentle heading
          const newAngle = (Math.random() - 0.5) * Math.PI * 0.5;
          whale.heading = newAngle;
          whale.turnTimer = 4 + Math.random() * 10;

          // Occasionally flip horizontal direction
          if (Math.random() < 0.3) {
            whale.flipX = !whale.flipX;
            whale.vx = -whale.vx;
          }
        }

        /* ── Smooth heading interpolation ── */
        whale.visualHeading +=
          (whale.heading - whale.visualHeading) * 0.01;

        /* ── Update velocity toward heading ── */
        const speed = Math.sqrt(whale.vx * whale.vx + whale.vy * whale.vy);
        const targetVx =
          Math.cos(whale.heading) * speed * (whale.vx >= 0 ? 1 : -1);
        const targetVy = Math.sin(whale.heading) * speed * 0.4;
        whale.vx += (targetVx - whale.vx) * 0.005;
        whale.vy += (targetVy - whale.vy) * 0.008;

        /* ── Position update ── */
        whale.x += whale.vx;
        whale.y += whale.vy;

        // Gentle vertical bobbing
        whale.y += Math.sin(t * 0.3 + whale.phase) * 0.12;

        /* ── Screen wrapping with generous buffer ── */
        const whalePxW = whale.size * whale.view.aspect;
        const buf = whalePxW * 0.6;

        if (whale.vx > 0 && whale.x > w + buf) {
          whale.x = -buf;
          whale.y = h * 0.1 + Math.random() * h * 0.8;
        } else if (whale.vx < 0 && whale.x < -buf) {
          whale.x = w + buf;
          whale.y = h * 0.1 + Math.random() * h * 0.8;
        }

        // Soft vertical containment
        if (whale.y < h * 0.02) whale.vy += 0.01;
        if (whale.y > h * 0.95) whale.vy -= 0.01;
        whale.vy = Math.max(-0.4, Math.min(0.4, whale.vy));

        /* ── Apply to DOM ── */
        const pxW = whale.size * whale.view.aspect;
        const pxH = whale.size;

        // Subtle rotation follows swim direction
        const swimAngle =
          whale.view.baseAngle + whale.visualHeading * (180 / Math.PI) * 0.15;

        const flipScale = whale.flipX ? -1 : 1;

        el.style.width = `${pxW}px`;
        el.style.height = `${pxH}px`;
        el.style.opacity = `${whale.opacity}`;
        el.style.transform =
          `translate(${whale.x - pxW / 2}px, ${whale.y - pxH / 2}px) ` +
          `scaleX(${flipScale}) ` +
          `rotate(${swimAngle}deg)`;

        // Update the inner element's background positioning
        const inner = el.firstElementChild as HTMLDivElement;
        if (inner) {
          inner.style.backgroundPosition =
            `${whale.view.bgX}% ${whale.view.bgY}%`;
          inner.style.backgroundSize =
            `${whale.view.zoom * 100}% auto`;
        }
      }

      animRef.current = requestAnimationFrame(animate);
    };

    animRef.current = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(animRef.current);
    };
  }, [initWhales, whaleCount]);

  return (
    <div
      ref={containerRef}
      className={`pointer-events-none fixed inset-0 z-0 overflow-hidden ${className}`}
      aria-hidden="true"
    />
  );
}
