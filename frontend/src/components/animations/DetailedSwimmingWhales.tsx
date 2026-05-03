"use client";

import { useEffect, useRef, useCallback } from "react";

/* ── Types ────────────────────────────────────────────────── */

interface SpinePoint {
  t: number;
  r: number;
}

interface Appendage {
  type: "dorsal" | "pectoral";
  anchor: number;
  /** Bezier outline: [dx,dy] pairs normalised to body length */
  leading: [number, number][];
  trailing: [number, number][];
  side: 1 | -1;
}

interface FlukeShape {
  /** Spine t where flukes attach (peduncle) */
  attachT: number;
  /** Lobe span perpendicular to spine (normalised to L) */
  span: number;
  /** How far back the lobe tips extend past attachment */
  sweepBack: number;
  /** Width of the lobe (chord, normalised to L) */
  chord: number;
  /** Depth of medial notch (normalised to L) */
  notchDepth: number;
}

interface WhaleSpecies {
  name: string;
  spine: SpinePoint[];
  appendages: Appendage[];
  fluke: FlukeShape;
  undulationAmp: number;
  undulationStart: number;
  lengthScale: number;
  hueShift: number;
  dorsalLum: number;
  ventralLum: number;
  markings: { t: number; angle: number; size: number }[];
  mouthLine: [number, number];
  blowholeT: number;
}

interface SwimInstance {
  species: WhaleSpecies;
  x: number;
  y: number;
  vx: number;
  length: number;
  opacity: number;
  phase: number;
  dir: 1 | -1;
  depth: number;
  seed: number;
}

/* ── Seeded PRNG ──────────────────────────────────────────── */

function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

/* ── Species ──────────────────────────────────────────────── */

const HUMPBACK: WhaleSpecies = {
  name: "humpback",
  lengthScale: 1.0,
  undulationAmp: 0.055,
  undulationStart: 0.3,
  hueShift: 0,
  dorsalLum: 28,
  ventralLum: 58,
  blowholeT: 0.07,
  mouthLine: [0, 4],
  fluke: {
    attachT: 0.97,
    span: 0.20,
    sweepBack: 0.10,
    chord: 0.08,
    notchDepth: 0.025,
  },
  markings: (() => {
    const rng = seededRandom(42);
    const m: WhaleSpecies["markings"] = [];
    for (let i = 0; i < 8; i++)
      m.push({
        t: 0.01 + rng() * 0.12,
        angle: -0.6 + rng() * 0.5,
        size: 0.005 + rng() * 0.005,
      });
    for (let i = 0; i < 5; i++)
      m.push({
        t: 0.15 + rng() * 0.25,
        angle: 0.3 + rng() * 0.5,
        size: 0.007 + rng() * 0.006,
      });
    return m;
  })(),
  spine: [
    // Rounded head
    { t: 0.0, r: 0.055 },
    { t: 0.03, r: 0.085 },
    { t: 0.08, r: 0.12 },
    // Throat / max girth
    { t: 0.15, r: 0.145 },
    { t: 0.22, r: 0.15 },
    // Mid-body plateau
    { t: 0.32, r: 0.145 },
    { t: 0.42, r: 0.135 },
    { t: 0.52, r: 0.12 },
    // Taper begins
    { t: 0.62, r: 0.09 },
    { t: 0.72, r: 0.06 },
    // Peduncle — distinct narrowing
    { t: 0.80, r: 0.038 },
    { t: 0.87, r: 0.022 },
    { t: 0.92, r: 0.015 },
    // Tail stock to fluke base
    { t: 0.96, r: 0.011 },
    { t: 1.0, r: 0.008 },
  ],
  appendages: [
    {
      type: "dorsal",
      anchor: 7,
      side: -1,
      leading: [
        [-0.02, -0.02],
        [-0.012, -0.08],
        [0.008, -0.075],
      ],
      trailing: [
        [0.025, -0.05],
        [0.03, -0.015],
      ],
    },
    {
      type: "pectoral",
      anchor: 5,
      side: 1,
      leading: [
        [0.015, 0.04],
        [-0.03, 0.18],
        [-0.08, 0.28],
      ],
      trailing: [
        [-0.12, 0.24],
        [-0.08, 0.08],
      ],
    },
  ],
};

const BLUE_WHALE: WhaleSpecies = {
  name: "blue",
  lengthScale: 1.3,
  undulationAmp: 0.032,
  undulationStart: 0.45,
  hueShift: -10,
  dorsalLum: 35,
  ventralLum: 62,
  blowholeT: 0.06,
  mouthLine: [0, 4],
  fluke: {
    attachT: 0.97,
    span: 0.18,
    sweepBack: 0.09,
    chord: 0.07,
    notchDepth: 0.02,
  },
  markings: (() => {
    const rng = seededRandom(137);
    const m: WhaleSpecies["markings"] = [];
    for (let i = 0; i < 22; i++)
      m.push({
        t: 0.08 + rng() * 0.75,
        angle: -0.8 + rng() * 1.6,
        size: 0.012 + rng() * 0.018,
      });
    return m;
  })(),
  spine: [
    // Narrow U-shaped head
    { t: 0.0, r: 0.035 },
    { t: 0.03, r: 0.06 },
    { t: 0.07, r: 0.09 },
    { t: 0.13, r: 0.115 },
    // Mid-body — very elongated
    { t: 0.22, r: 0.13 },
    { t: 0.32, r: 0.135 },
    { t: 0.42, r: 0.13 },
    { t: 0.52, r: 0.12 },
    { t: 0.62, r: 0.095 },
    // Taper
    { t: 0.72, r: 0.065 },
    { t: 0.80, r: 0.04 },
    // Peduncle
    { t: 0.87, r: 0.022 },
    { t: 0.93, r: 0.014 },
    { t: 0.97, r: 0.009 },
    { t: 1.0, r: 0.006 },
  ],
  appendages: [
    {
      type: "dorsal",
      anchor: 10,
      side: -1,
      leading: [
        [-0.008, -0.012],
        [-0.002, -0.045],
        [0.01, -0.04],
      ],
      trailing: [
        [0.02, -0.025],
        [0.025, -0.006],
      ],
    },
    {
      type: "pectoral",
      anchor: 5,
      side: 1,
      leading: [
        [0.01, 0.03],
        [-0.015, 0.12],
        [-0.04, 0.15],
      ],
      trailing: [
        [-0.06, 0.12],
        [-0.035, 0.045],
      ],
    },
  ],
};

const RIGHT_WHALE: WhaleSpecies = {
  name: "right",
  lengthScale: 0.85,
  undulationAmp: 0.045,
  undulationStart: 0.35,
  hueShift: 15,
  dorsalLum: 22,
  ventralLum: 42,
  blowholeT: 0.06,
  mouthLine: [0, 5],
  fluke: {
    attachT: 0.96,
    span: 0.22,
    sweepBack: 0.10,
    chord: 0.09,
    notchDepth: 0.03,
  },
  markings: (() => {
    const rng = seededRandom(99);
    const m: WhaleSpecies["markings"] = [];
    m.push({ t: 0.01, angle: -0.5, size: 0.014 });
    m.push({ t: 0.02, angle: -0.3, size: 0.011 });
    m.push({ t: 0.04, angle: 0.6, size: 0.01 });
    m.push({ t: 0.08, angle: -0.6, size: 0.009 });
    m.push({ t: 0.09, angle: -0.45, size: 0.008 });
    for (let i = 0; i < 4; i++)
      m.push({
        t: 0.03 + i * 0.025,
        angle: -0.15 + rng() * 0.3,
        size: 0.005 + rng() * 0.004,
      });
    return m;
  })(),
  spine: [
    // Broad arched head (no rostrum bump)
    { t: 0.0, r: 0.065 },
    { t: 0.04, r: 0.10 },
    { t: 0.10, r: 0.14 },
    // Very rotund body
    { t: 0.18, r: 0.165 },
    { t: 0.26, r: 0.17 },
    { t: 0.36, r: 0.16 },
    { t: 0.46, r: 0.145 },
    { t: 0.56, r: 0.12 },
    // Taper
    { t: 0.66, r: 0.085 },
    { t: 0.76, r: 0.055 },
    // Peduncle — no dorsal fin, smooth
    { t: 0.84, r: 0.03 },
    { t: 0.91, r: 0.018 },
    { t: 0.96, r: 0.012 },
    { t: 1.0, r: 0.007 },
  ],
  appendages: [
    {
      type: "pectoral",
      anchor: 5,
      side: 1,
      leading: [
        [0.008, 0.035],
        [-0.012, 0.10],
        [-0.035, 0.12],
      ],
      trailing: [
        [-0.045, 0.10],
        [-0.025, 0.04],
      ],
    },
  ],
};

const SPECIES_POOL: WhaleSpecies[] = [HUMPBACK, BLUE_WHALE, RIGHT_WHALE];

/* ── Spine interpolation ──────────────────────────────────── */

function lerpSpine(
  pts: { x: number; y: number; r: number }[],
  spine: SpinePoint[],
  t: number,
): { x: number; y: number; r: number } {
  if (t <= spine[0].t) return pts[0];
  if (t >= spine[spine.length - 1].t) return pts[pts.length - 1];
  for (let i = 1; i < spine.length; i++) {
    if (t <= spine[i].t) {
      const f = (t - spine[i - 1].t) / (spine[i].t - spine[i - 1].t);
      return {
        x: pts[i - 1].x + (pts[i].x - pts[i - 1].x) * f,
        y: pts[i - 1].y + (pts[i].y - pts[i - 1].y) * f,
        r: pts[i - 1].r + (pts[i].r - pts[i - 1].r) * f,
      };
    }
  }
  return pts[pts.length - 1];
}

/* ── Component ────────────────────────────────────────────── */

export default function DetailedSwimmingWhales({
  className = "",
  whaleCount = 4,
  baseOpacity = 0.07,
}: {
  className?: string;
  whaleCount?: number;
  baseOpacity?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const whalesRef = useRef<SwimInstance[]>([]);
  const timeRef = useRef(0);
  const sizeRef = useRef({ w: 0, h: 0 });

  const initWhales = useCallback(
    (w: number, h: number) => {
      const whales: SwimInstance[] = [];
      for (let i = 0; i < whaleCount; i++) {
        const depth = i / Math.max(whaleCount - 1, 1);
        const sp = SPECIES_POOL[i % SPECIES_POOL.length];
        const baseLen = 140 + depth * 120;
        const len = baseLen * sp.lengthScale;
        whales.push({
          species: sp,
          x: Math.random() * (w + len * 2) - len,
          y: h * 0.15 + (h * 0.7 * i) / whaleCount + Math.random() * 60 - 30,
          vx: (0.25 + depth * 0.55) * (i % 2 === 0 ? 1 : -1),
          length: len,
          opacity: baseOpacity * (0.5 + depth * 0.5),
          phase: Math.random() * Math.PI * 2,
          dir: i % 2 === 0 ? 1 : -1,
          depth,
          seed: 1000 + i * 777,
        });
      }
      whalesRef.current = whales;
    },
    [whaleCount, baseOpacity],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const w = window.innerWidth;
      const h = window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      sizeRef.current = { w, h };
      if (whalesRef.current.length === 0) initWhales(w, h);
    };
    resize();
    window.addEventListener("resize", resize);

    /* ── Spine deformation ─── */
    const deformSpine = (
      species: WhaleSpecies,
      length: number,
      time: number,
      phase: number,
    ) => {
      return species.spine.map((sp) => {
        const mix =
          sp.t < species.undulationStart
            ? 0
            : (sp.t - species.undulationStart) /
              (1 - species.undulationStart);
        const dy =
          species.undulationAmp *
          length *
          mix *
          mix *
          Math.sin(sp.t * 2.5 * Math.PI * 2 - time * 3 + phase);
        return { x: sp.t * length, y: dy, r: sp.r * length };
      });
    };

    /* ── Body outline path ─── */
    const buildBodyPath = (
      pts: { x: number; y: number; r: number }[],
    ) => {
      ctx.beginPath();
      ctx.moveTo(pts[0].x, pts[0].y - pts[0].r);
      for (let i = 1; i < pts.length; i++) {
        const prev = pts[i - 1];
        const curr = pts[i];
        ctx.quadraticCurveTo(
          prev.x + (curr.x - prev.x) * 0.5,
          prev.y -
            prev.r +
            (curr.y - curr.r - (prev.y - prev.r)) * 0.5,
          curr.x,
          curr.y - curr.r,
        );
      }
      for (let i = pts.length - 1; i >= 0; i--) {
        const curr = pts[i];
        const next = i > 0 ? pts[i - 1] : pts[0];
        ctx.quadraticCurveTo(
          curr.x + (next.x - curr.x) * 0.5,
          curr.y +
            curr.r +
            (next.y + next.r - (curr.y + curr.r)) * 0.5,
          next.x,
          next.y + next.r,
        );
      }
      ctx.closePath();
    };

    /* ── Draw flukes as proper crescent shapes ─── */
    const drawFlukes = (
      species: WhaleSpecies,
      pts: { x: number; y: number; r: number }[],
      L: number,
      hue: number,
      sat: number,
    ) => {
      const fl = species.fluke;
      const attach = lerpSpine(pts, species.spine, fl.attachT);
      const ax = attach.x;
      const ay = attach.y;
      const span = fl.span * L;
      const sweep = fl.sweepBack * L;
      const chord = fl.chord * L;
      const notch = fl.notchDepth * L;

      // Each lobe: broad crescent shape
      for (const side of [-1, 1]) {
        const tipY = ay + span * side;
        const tipX = ax + sweep;

        ctx.beginPath();
        ctx.moveTo(ax, ay);
        // Leading edge — sweeps outward from peduncle to lobe tip
        ctx.bezierCurveTo(
          ax,
          ay + span * 0.5 * side,
          ax + sweep * 0.6,
          tipY,
          tipX,
          tipY,
        );
        // Trailing edge — wider return arc creating lobe chord width
        ctx.bezierCurveTo(
          tipX + chord,
          tipY,
          ax + chord,
          ay + span * 0.3 * side,
          ax,
          ay + notch * side,
        );
        ctx.closePath();

        // Gradient fill matching body
        const fGrad = ctx.createLinearGradient(
          ax,
          ay - span,
          ax,
          ay + span,
        );
        fGrad.addColorStop(
          0,
          `hsl(${hue},${sat}%,${species.dorsalLum + 2}%)`,
        );
        fGrad.addColorStop(
          1,
          `hsl(${hue},${sat - 8}%,${species.ventralLum - 2}%)`,
        );
        ctx.fillStyle = fGrad;
        ctx.fill();
        ctx.strokeStyle = `hsla(${hue},${sat}%,${species.dorsalLum - 5}%,0.3)`;
        ctx.lineWidth = 0.6;
        ctx.stroke();
      }

      // Medial notch
      ctx.beginPath();
      ctx.moveTo(ax - chord * 0.2, ay - notch * 0.6);
      ctx.quadraticCurveTo(
        ax + notch * 0.5,
        ay,
        ax - chord * 0.2,
        ay + notch * 0.6,
      );
      ctx.strokeStyle = `hsla(${hue},${sat}%,${species.dorsalLum - 5}%,0.4)`;
      ctx.lineWidth = 0.7;
      ctx.stroke();

      // Trailing edge highlight on each lobe
      for (const side of [-1, 1]) {
        const tipY = ay + span * side;
        const tipX = ax + sweep;
        ctx.beginPath();
        ctx.moveTo(tipX, tipY);
        ctx.quadraticCurveTo(
          tipX - sweep * 0.5,
          tipY + chord * 0.15 * side,
          ax,
          ay + notch * 0.2 * side,
        );
        ctx.strokeStyle = `hsla(${hue + 10},80%,75%,0.1)`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }
    };

    /* ── Draw appendages (dorsal + pectoral) ─── */
    const drawAppendage = (
      app: Appendage,
      pts: { x: number; y: number; r: number }[],
      L: number,
      hue: number,
      sat: number,
      species: WhaleSpecies,
    ) => {
      const anch = pts[Math.min(app.anchor, pts.length - 1)];
      const ox = anch.x;
      const oy = anch.y + anch.r * app.side * 0.8;

      // Convert relative points to absolute (dy sign encodes direction)
      const lead = app.leading.map(([dx, dy]) => ({
        x: ox + dx * L,
        y: oy + dy * L,
      }));
      const trail = app.trailing.map(([dx, dy]) => ({
        x: ox + dx * L,
        y: oy + dy * L,
      }));

      ctx.beginPath();
      ctx.moveTo(ox, oy);

      // Leading edge to tip
      if (lead.length >= 3) {
        ctx.bezierCurveTo(
          lead[0].x, lead[0].y,
          lead[1].x, lead[1].y,
          lead[2].x, lead[2].y,
        );
      }

      // Tip to trailing edge back to body
      if (trail.length >= 2) {
        ctx.bezierCurveTo(
          trail[0].x, trail[0].y,
          trail[1].x, trail[1].y,
          ox, oy,
        );
      }
      ctx.closePath();

      // Gradient
      const aGrad = ctx.createLinearGradient(ox, oy - 10, ox, oy + 10);
      const aD = `hsl(${hue},${sat - 5}%,${species.dorsalLum + 2}%)`;
      const aL = `hsl(${hue},${sat - 8}%,${species.ventralLum - 4}%)`;
      aGrad.addColorStop(0, app.side === -1 ? aD : aL);
      aGrad.addColorStop(1, app.side === -1 ? aL : aD);
      ctx.fillStyle = aGrad;
      ctx.fill();
      ctx.strokeStyle = `hsla(${hue},${sat}%,${species.dorsalLum - 5}%,0.25)`;
      ctx.lineWidth = 0.6;
      ctx.stroke();
    };

    /* ── Draw a single whale ─── */
    const drawWhale = (whale: SwimInstance, time: number) => {
      const sp = whale.species;
      const pts = deformSpine(sp, whale.length, time, whale.phase);
      const rng = seededRandom(whale.seed);
      const hue = 190 + sp.hueShift;
      const sat = 55 + whale.depth * 15;
      const L = whale.length;

      ctx.save();
      ctx.translate(whale.x, whale.y);
      if (whale.dir === 1) {
        ctx.scale(-1, 1);
        ctx.translate(-L, 0);
      }
      ctx.globalAlpha = whale.opacity;

      /* ═══ 1 ─ FLUKES (drawn first, behind body) ═══ */
      drawFlukes(sp, pts, L, hue, sat);

      /* ═══ 2 ─ BODY FILL — countershaded ═══ */
      buildBodyPath(pts);
      const bGrad = ctx.createLinearGradient(0, -L * 0.17, 0, L * 0.17);
      bGrad.addColorStop(
        0,
        `hsla(${hue + 8},${sat + 15}%,${sp.dorsalLum + 28}%,0.4)`,
      );
      bGrad.addColorStop(
        0.1,
        `hsl(${hue},${sat}%,${sp.dorsalLum}%)`,
      );
      bGrad.addColorStop(
        0.5,
        `hsl(${hue},${sat - 5}%,${sp.dorsalLum + 6}%)`,
      );
      bGrad.addColorStop(
        0.85,
        `hsl(${hue},${sat - 10}%,${sp.ventralLum}%)`,
      );
      bGrad.addColorStop(
        1,
        `hsl(${hue},${sat - 8}%,${sp.ventralLum - 5}%)`,
      );
      ctx.fillStyle = bGrad;
      ctx.fill();

      /* ═══ 3 ─ BODY OUTLINE ═══ */
      buildBodyPath(pts);
      ctx.strokeStyle = `hsla(${hue},${sat}%,${sp.dorsalLum - 8}%,0.4)`;
      ctx.lineWidth = 1.0;
      ctx.stroke();

      /* ═══ 4 ─ DORSAL RIM LIGHT ═══ */
      ctx.beginPath();
      ctx.moveTo(pts[1].x, pts[1].y - pts[1].r + 0.5);
      for (let i = 2; i < pts.length - 2; i++) {
        ctx.lineTo(pts[i].x, pts[i].y - pts[i].r + 0.3);
      }
      ctx.strokeStyle = `hsla(${hue + 10},80%,80%,0.22)`;
      ctx.lineWidth = 1.4;
      ctx.stroke();

      /* ═══ 5 ─ SKIN TEXTURE (clipped) ═══ */
      ctx.save();
      buildBodyPath(pts);
      ctx.clip();

      // Blue whale mottling
      if (sp.name === "blue") {
        for (const mk of sp.markings) {
          const pt = lerpSpine(pts, sp.spine, mk.t);
          const mx = pt.x;
          const my = pt.y + pt.r * mk.angle;
          const mr = mk.size * L;
          const mG = ctx.createRadialGradient(mx, my, 0, mx, my, mr);
          mG.addColorStop(
            0,
            `hsla(${hue + 5},${sat - 15}%,${sp.dorsalLum + 20}%,0.35)`,
          );
          mG.addColorStop(1, "transparent");
          ctx.fillStyle = mG;
          ctx.beginPath();
          ctx.ellipse(
            mx, my, mr, mr * 0.6,
            (mk.angle * Math.PI) / 2, 0, Math.PI * 2,
          );
          ctx.fill();
        }
      }

      // Noise dappling (all species)
      for (let i = 0; i < 16; i++) {
        const nt = 0.05 + rng() * 0.85;
        const na = -0.7 + rng() * 1.4;
        const pt = lerpSpine(pts, sp.spine, nt);
        const nx = pt.x + rng() * 4 - 2;
        const ny = pt.y + pt.r * na;
        const nr = L * (0.006 + rng() * 0.014);
        ctx.beginPath();
        ctx.arc(nx, ny, nr, 0, Math.PI * 2);
        ctx.fillStyle =
          rng() > 0.5
            ? `hsla(${hue},${sat - 10}%,${sp.dorsalLum + 14}%,0.18)`
            : `hsla(${hue},${sat}%,${sp.dorsalLum - 8}%,0.14)`;
        ctx.fill();
      }

      /* ═══ 6 ─ SCARS / RAKE MARKS ═══ */
      for (let i = 0; i < 4; i++) {
        const st = 0.2 + rng() * 0.5;
        const sa = -0.4 + rng() * 0.8;
        const pt = lerpSpine(pts, sp.spine, st);
        const sLen = L * (0.025 + rng() * 0.035);
        const sRad = -0.3 + rng() * 0.6;
        ctx.beginPath();
        ctx.moveTo(pt.x, pt.y + pt.r * sa);
        ctx.lineTo(
          pt.x + Math.cos(sRad) * sLen,
          pt.y + pt.r * sa + Math.sin(sRad) * sLen,
        );
        ctx.strokeStyle = `hsla(${hue},${sat - 20}%,${sp.dorsalLum + 18}%,0.18)`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }

      ctx.restore(); // end clip

      /* ═══ 7 ─ VENTRAL GROOVES ═══ */
      if (sp.name === "humpback" || sp.name === "blue") {
        const gc = sp.name === "humpback" ? 7 : 5;
        ctx.lineWidth = 0.5;
        for (let g = 0; g < gc; g++) {
          ctx.beginPath();
          ctx.strokeStyle = `hsla(${hue},${sat}%,${sp.ventralLum - 14}%,0.22)`;
          const si = 3 + Math.floor(g * 0.4);
          const ei = Math.min(si + 4, pts.length - 3);
          for (let j = si; j <= ei; j++) {
            const p = pts[j];
            const gy = p.y + p.r * (0.3 + g * 0.09);
            if (j === si) ctx.moveTo(p.x, gy);
            else ctx.lineTo(p.x, gy);
          }
          ctx.stroke();
        }
      }

      /* ═══ 8 ─ MOUTH LINE ═══ */
      ctx.beginPath();
      for (
        let i = sp.mouthLine[0];
        i <= Math.min(sp.mouthLine[1], pts.length - 1);
        i++
      ) {
        const p = pts[i];
        const my = p.y + p.r * 0.4;
        if (i === sp.mouthLine[0]) ctx.moveTo(p.x, my);
        else ctx.lineTo(p.x, my);
      }
      ctx.strokeStyle = `hsla(${hue},${sat - 10}%,${sp.dorsalLum - 5}%,0.35)`;
      ctx.lineWidth = 0.8;
      ctx.stroke();

      /* ═══ 9 ─ APPENDAGES (dorsal + pectoral) ═══ */
      for (const app of sp.appendages) {
        drawAppendage(app, pts, L, hue, sat, sp);
      }

      /* ═══ 10 ─ EYE ═══ */
      const ePt = lerpSpine(pts, sp.spine, 0.09);
      const eR = Math.max(1.4, L * 0.008);
      const eY = ePt.y - ePt.r * 0.5;
      // Socket
      ctx.beginPath();
      ctx.arc(ePt.x, eY, eR * 2, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${hue},${sat}%,${sp.dorsalLum - 10}%,0.25)`;
      ctx.fill();
      // Iris
      ctx.beginPath();
      ctx.arc(ePt.x, eY, eR, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${hue},15%,15%,0.7)`;
      ctx.fill();
      // Specular
      ctx.beginPath();
      ctx.arc(ePt.x - eR * 0.3, eY - eR * 0.3, eR * 0.4, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(255,255,255,0.3)";
      ctx.fill();

      /* ═══ 11 ─ BLOWHOLE ═══ */
      const bh = lerpSpine(pts, sp.spine, sp.blowholeT);
      ctx.beginPath();
      ctx.ellipse(
        bh.x, bh.y - bh.r * 0.92,
        L * 0.007, L * 0.003,
        0, 0, Math.PI,
      );
      ctx.strokeStyle = `hsla(${hue},${sat}%,${sp.dorsalLum - 10}%,0.35)`;
      ctx.lineWidth = 0.6;
      ctx.stroke();

      /* ═══ 12 ─ SPECIES MARKINGS ═══ */
      if (sp.name === "right") {
        // Callosities
        for (const mk of sp.markings) {
          const mpt = lerpSpine(pts, sp.spine, mk.t);
          const mx = mpt.x;
          const my = mpt.y + mpt.r * mk.angle;
          const mr = mk.size * L;
          for (let c = 0; c < 4; c++) {
            const ox = (rng() - 0.5) * mr * 0.7;
            const oy = (rng() - 0.5) * mr * 0.5;
            ctx.beginPath();
            ctx.arc(
              mx + ox, my + oy,
              mr * (0.4 + rng() * 0.5),
              0, Math.PI * 2,
            );
            ctx.fillStyle = `hsla(45,30%,75%,${0.25 + rng() * 0.12})`;
            ctx.fill();
          }
        }
      } else if (sp.name === "humpback") {
        // Tubercles
        for (const mk of sp.markings) {
          if (mk.t > 0.14) continue;
          const mpt = lerpSpine(pts, sp.spine, mk.t);
          const mx = mpt.x;
          const my = mpt.y + mpt.r * mk.angle;
          const mr = mk.size * L;
          ctx.beginPath();
          ctx.arc(mx, my, mr, 0, Math.PI * 2);
          ctx.fillStyle = `hsla(${hue},${sat - 15}%,${sp.dorsalLum + 10}%,0.3)`;
          ctx.fill();
          ctx.beginPath();
          ctx.arc(mx - mr * 0.2, my - mr * 0.3, mr * 0.45, 0, Math.PI * 2);
          ctx.fillStyle = `hsla(${hue + 10},${sat}%,${sp.dorsalLum + 28}%,0.18)`;
          ctx.fill();
        }
        // Barnacles
        for (const mk of sp.markings) {
          if (mk.t <= 0.14) continue;
          const mpt = lerpSpine(pts, sp.spine, mk.t);
          const mx = mpt.x;
          const my = mpt.y + mpt.r * mk.angle;
          const mr = mk.size * L;
          for (let c = 0; c < 5; c++) {
            const ox = (rng() - 0.5) * mr;
            const oy = (rng() - 0.5) * mr * 0.7;
            ctx.beginPath();
            ctx.arc(
              mx + ox, my + oy,
              mr * (0.2 + rng() * 0.35),
              0, Math.PI * 2,
            );
            ctx.fillStyle = `hsla(35,25%,68%,${0.18 + rng() * 0.1})`;
            ctx.fill();
          }
        }
      }

      /* ═══ 13 ─ WAKE & BUBBLES ═══ */
      const tail = pts[pts.length - 1];
      ctx.globalAlpha = whale.opacity * 0.45;

      for (let e = 0; e < 3; e++) {
        const ex = tail.x + 12 + e * 14 + Math.sin(time * 3 + e * 2) * 5;
        const ey = tail.y + Math.cos(time * 2.5 + e * 1.7) * 6;
        ctx.beginPath();
        ctx.arc(ex, ey, 3.5 + e * 1.8, 0, Math.PI * 2);
        ctx.strokeStyle = `hsla(${hue},60%,65%,${0.15 - e * 0.04})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }

      for (let b = 0; b < 10; b++) {
        const bx = tail.x + 8 + b * 5 + Math.sin(time * 4 + b * 1.3) * 3;
        const by = tail.y + Math.sin(time * 3 + b * 1.8) * 3.5 - b * 0.6;
        const br = Math.max(0.5, 2.2 - b * 0.18);
        ctx.beginPath();
        ctx.arc(bx, by, br, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${hue},70%,75%,${0.35 - b * 0.03})`;
        ctx.fill();
        if (br > 0.9) {
          ctx.beginPath();
          ctx.arc(bx - br * 0.25, by - br * 0.3, br * 0.3, 0, Math.PI * 2);
          ctx.fillStyle = "rgba(255,255,255,0.2)";
          ctx.fill();
        }
      }

      ctx.restore();
    };

    /* ── Animation loop ─── */
    const animate = () => {
      timeRef.current += 0.012;
      const { w, h } = sizeRef.current;
      ctx.clearRect(0, 0, w, h);

      for (const whale of whalesRef.current) {
        whale.x += whale.vx;
        whale.y += Math.sin(timeRef.current * 0.5 + whale.phase) * 0.15;

        if (whale.dir === 1 && whale.x > w + whale.length * 1.2) {
          whale.x = -whale.length * 1.2;
        } else if (whale.dir === -1 && whale.x < -whale.length * 1.2) {
          whale.x = w + whale.length * 1.2;
        }

        drawWhale(whale, timeRef.current);
      }

      animRef.current = requestAnimationFrame(animate);
    };

    animRef.current = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(animRef.current);
    };
  }, [initWhales]);

  return (
    <canvas
      ref={canvasRef}
      className={`pointer-events-none fixed inset-0 z-0 ${className}`}
      aria-hidden="true"
    />
  );
}
