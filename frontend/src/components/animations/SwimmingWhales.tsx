"use client";

import { useEffect, useRef, useCallback } from "react";

/* ═══════════════ Helpers ═══════════════ */

function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

const TAU = Math.PI * 2;

function rgba(r: number, g: number, b: number, a: number): string {
  return `rgba(${r},${g},${b},${a})`;
}

/* ═══════════════ Types ═══════════════ */

/**
 * 5 views matching the reference image:
 *  - front:    head-on, approaching the viewer
 *  - top:      dorsal / bird's-eye view
 *  - side:     classic profile from the right
 *  - diag-r:   front-right diagonal (approaching from the right)
 *  - diag-l:   front-left diagonal  (approaching from the left)
 */
type WhaleView = "front" | "top" | "side" | "diag-r" | "diag-l";

interface SwimWhale {
  x: number;
  y: number;
  vx: number;
  vy: number;
  length: number;
  opacity: number;
  depth: number; // 0-1, affects size + layering
  phase: number; // animation offset
  view: WhaleView;
  facingRight: boolean;
  heading: number; // current visual heading (radians)
  targetHeading: number;
  turnTimer: number;
  swimCycle: number; // drives all body animation (0..TAU)
  swimSpeed: number; // radians per frame
}

/* ═══════════════ Drawing: Side View ═══════════════ */

function drawSideWhale(
  ctx: CanvasRenderingContext2D,
  L: number,
  cycle: number,
  alpha: number,
) {
  const H = L * 0.25; // max body half-height

  // Spine deformation — only rear 60% bends (real whale kinematics)
  const spine = (t: number) => {
    if (t < 0.35) return 0;
    const p = (t - 0.35) / 0.65;
    return Math.sin(cycle + p * 2.0) * H * 0.12 * p * p;
  };

  const tailFlap = Math.sin(cycle) * H * 0.38;
  const flukeY = spine(0.96) + tailFlap;

  // ── Body outline ──
  ctx.beginPath();

  // UPPER contour: nose → forehead → back → peduncle
  ctx.moveTo(0, spine(0));
  ctx.bezierCurveTo(
    L * 0.04, -H * 0.25 + spine(0.04),
    L * 0.10, -H * 0.58 + spine(0.10),
    L * 0.18, -H * 0.75 + spine(0.18),
  );
  ctx.bezierCurveTo(
    L * 0.28, -H * 0.92 + spine(0.28),
    L * 0.42, -H * 0.96 + spine(0.42),
    L * 0.55, -H * 0.80 + spine(0.55),
  );
  ctx.bezierCurveTo(
    L * 0.65, -H * 0.60 + spine(0.65),
    L * 0.78, -H * 0.30 + spine(0.78),
    L * 0.88, -H * 0.14 + spine(0.88),
  );
  ctx.bezierCurveTo(
    L * 0.92, -H * 0.08 + spine(0.92),
    L * 0.95, -H * 0.05 + spine(0.95),
    L * 0.965, -H * 0.04 + spine(0.965),
  );

  // Upper fluke
  ctx.bezierCurveTo(
    L * 0.98, -H * 0.18 + flukeY,
    L * 1.06, -H * 0.38 + flukeY,
    L * 1.11, -H * 0.28 + flukeY,
  );
  ctx.bezierCurveTo(
    L * 1.08, -H * 0.12 + flukeY,
    L * 1.01, -H * 0.01 + flukeY,
    L * 0.98, flukeY,
  );
  // Notch
  ctx.lineTo(L * 0.975, flukeY);
  // Lower fluke
  ctx.bezierCurveTo(
    L * 1.01, H * 0.01 + flukeY,
    L * 1.08, H * 0.12 + flukeY,
    L * 1.11, H * 0.28 + flukeY,
  );
  ctx.bezierCurveTo(
    L * 1.06, H * 0.38 + flukeY,
    L * 0.98, H * 0.18 + flukeY,
    L * 0.965, H * 0.04 + spine(0.965),
  );

  // LOWER contour: peduncle → belly → chin
  ctx.bezierCurveTo(
    L * 0.95, H * 0.05 + spine(0.95),
    L * 0.92, H * 0.08 + spine(0.92),
    L * 0.88, H * 0.12 + spine(0.88),
  );
  ctx.bezierCurveTo(
    L * 0.78, H * 0.28 + spine(0.78),
    L * 0.62, H * 0.62 + spine(0.62),
    L * 0.45, H * 0.76 + spine(0.45),
  );
  ctx.bezierCurveTo(
    L * 0.32, H * 0.82 + spine(0.32),
    L * 0.18, H * 0.67 + spine(0.18),
    L * 0.10, H * 0.40 + spine(0.10),
  );
  ctx.bezierCurveTo(
    L * 0.04, H * 0.18 + spine(0.04),
    L * 0.01, H * 0.06 + spine(0.01),
    0, H * 0.03 + spine(0),
  );
  ctx.closePath();

  // Gradient fill — dark dorsal, lighter ventral
  const g = ctx.createLinearGradient(L * 0.3, -H, L * 0.3, H * 0.9);
  g.addColorStop(0, rgba(28, 72, 120, alpha));
  g.addColorStop(0.45, rgba(50, 105, 160, alpha));
  g.addColorStop(1, rgba(85, 148, 200, alpha));
  ctx.fillStyle = g;
  ctx.fill();

  // ── Dorsal fin ──
  const dx = L * 0.62;
  const dy = -H * 0.65 + spine(0.62);
  const dh = H * 0.40;
  ctx.beginPath();
  ctx.moveTo(dx - H * 0.06, dy + H * 0.01);
  ctx.bezierCurveTo(
    dx,
    dy - dh * 0.5,
    dx + H * 0.04,
    dy - dh * 0.88,
    dx + H * 0.06,
    dy - dh,
  );
  ctx.bezierCurveTo(
    dx + H * 0.14,
    dy - dh * 0.55,
    dx + H * 0.22,
    dy - dh * 0.08,
    dx + H * 0.24,
    dy + H * 0.01,
  );
  ctx.closePath();
  ctx.fillStyle = rgba(20, 58, 100, alpha);
  ctx.fill();

  // ── Pectoral fin (sweeping) ──
  const px = L * 0.22;
  const py = H * 0.50 + spine(0.22);
  const fAng = Math.sin(cycle * 0.8 + 0.8) * 0.25 + 0.35;
  const fLen = L * 0.16;
  ctx.save();
  ctx.translate(px, py);
  ctx.rotate(fAng);
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.bezierCurveTo(
    fLen * 0.35,
    -fLen * 0.05,
    fLen * 0.75,
    -fLen * 0.03,
    fLen,
    -fLen * 0.01,
  );
  ctx.bezierCurveTo(
    fLen * 0.9,
    fLen * 0.05,
    fLen * 0.5,
    fLen * 0.12,
    0,
    fLen * 0.06,
  );
  ctx.closePath();
  ctx.fillStyle = rgba(22, 60, 105, alpha);
  ctx.fill();
  ctx.restore();

  // ── Eye ──
  ctx.beginPath();
  ctx.ellipse(
    L * 0.105,
    -H * 0.18 + spine(0.105),
    H * 0.045,
    H * 0.035,
    0,
    0,
    TAU,
  );
  ctx.fillStyle = rgba(8, 18, 32, alpha);
  ctx.fill();
  // Highlight
  ctx.beginPath();
  ctx.arc(L * 0.102, -H * 0.20 + spine(0.102), H * 0.015, 0, TAU);
  ctx.fillStyle = rgba(130, 175, 215, alpha * 0.4);
  ctx.fill();

  // ── Mouth line ──
  ctx.beginPath();
  ctx.moveTo(L * 0.003, H * 0.015 + spine(0));
  ctx.bezierCurveTo(
    L * 0.06,
    H * 0.22 + spine(0.06),
    L * 0.13,
    H * 0.40 + spine(0.13),
    L * 0.22,
    H * 0.44 + spine(0.22),
  );
  ctx.strokeStyle = rgba(30, 65, 105, alpha * 0.35);
  ctx.lineWidth = H * 0.02;
  ctx.lineCap = "round";
  ctx.stroke();

  // ── Ventral grooves (subtle belly detail) ──
  ctx.strokeStyle = rgba(55, 105, 158, alpha * 0.18);
  ctx.lineWidth = H * 0.008;
  for (let i = 0; i < 4; i++) {
    const t0 = 0.14 + i * 0.07;
    const grooveY = H * (0.38 + i * 0.08);
    ctx.beginPath();
    ctx.moveTo(L * t0, grooveY + spine(t0));
    ctx.lineTo(L * (t0 + 0.13), grooveY * 0.96 + spine(t0 + 0.13));
    ctx.stroke();
  }
}

/* ═══════════════ Drawing: Top-Down (Dorsal) View ═══════════════ */

function drawTopWhale(
  ctx: CanvasRenderingContext2D,
  L: number,
  cycle: number,
  alpha: number,
) {
  const W = L * 0.17; // max body half-width from above

  // Subtle lateral shimmy for visual life (real motion is dorso-ventral)
  const shimmy = (t: number) => {
    if (t < 0.4) return 0;
    const p = (t - 0.4) / 0.6;
    return Math.sin(cycle + p * 1.8) * W * 0.08 * p;
  };

  const tailShimmy = shimmy(0.96);

  // ── Body outline ──
  ctx.beginPath();

  // Right contour (nose → tail)
  ctx.moveTo(0, shimmy(0));
  ctx.bezierCurveTo(
    L * 0.05, W * 0.30 + shimmy(0.05),
    L * 0.12, W * 0.65 + shimmy(0.12),
    L * 0.22, W * 0.88 + shimmy(0.22),
  );
  ctx.bezierCurveTo(
    L * 0.32, W * 1.0 + shimmy(0.32),
    L * 0.45, W * 0.92 + shimmy(0.45),
    L * 0.58, W * 0.70 + shimmy(0.58),
  );
  ctx.bezierCurveTo(
    L * 0.70, W * 0.45 + shimmy(0.70),
    L * 0.82, W * 0.22 + shimmy(0.82),
    L * 0.92, W * 0.10 + shimmy(0.92),
  );
  ctx.lineTo(L * 0.96, W * 0.06 + tailShimmy);

  // Right fluke
  const fSpread = W * 1.2;
  ctx.bezierCurveTo(
    L * 0.98, fSpread * 0.30 + tailShimmy,
    L * 1.05, fSpread * 0.72 + tailShimmy,
    L * 1.09, fSpread * 0.56 + tailShimmy,
  );
  ctx.bezierCurveTo(
    L * 1.07, fSpread * 0.30 + tailShimmy,
    L * 1.01, fSpread * 0.05 + tailShimmy,
    L * 0.98, tailShimmy,
  );

  // Left fluke (mirror)
  ctx.bezierCurveTo(
    L * 1.01, -fSpread * 0.05 + tailShimmy,
    L * 1.07, -fSpread * 0.30 + tailShimmy,
    L * 1.09, -fSpread * 0.56 + tailShimmy,
  );
  ctx.bezierCurveTo(
    L * 1.05, -fSpread * 0.72 + tailShimmy,
    L * 0.98, -fSpread * 0.30 + tailShimmy,
    L * 0.96, -W * 0.06 + tailShimmy,
  );

  // Left contour (tail → nose)
  ctx.lineTo(L * 0.92, -W * 0.10 + shimmy(0.92));
  ctx.bezierCurveTo(
    L * 0.82, -W * 0.22 + shimmy(0.82),
    L * 0.70, -W * 0.45 + shimmy(0.70),
    L * 0.58, -W * 0.70 + shimmy(0.58),
  );
  ctx.bezierCurveTo(
    L * 0.45, -W * 0.92 + shimmy(0.45),
    L * 0.32, -W * 1.0 + shimmy(0.32),
    L * 0.22, -W * 0.88 + shimmy(0.22),
  );
  ctx.bezierCurveTo(
    L * 0.12, -W * 0.65 + shimmy(0.12),
    L * 0.05, -W * 0.30 + shimmy(0.05),
    0, shimmy(0),
  );
  ctx.closePath();

  // Gradient (centre lighter, edges darker — lit from above)
  const g = ctx.createLinearGradient(L * 0.3, -W, L * 0.3, W);
  g.addColorStop(0, rgba(22, 60, 105, alpha));
  g.addColorStop(0.35, rgba(40, 90, 140, alpha));
  g.addColorStop(0.5, rgba(58, 118, 172, alpha));
  g.addColorStop(0.65, rgba(40, 90, 140, alpha));
  g.addColorStop(1, rgba(22, 60, 105, alpha));
  ctx.fillStyle = g;
  ctx.fill();

  // ── Pectoral fins (from above, extend to sides) ──
  const pfx = L * 0.25;
  const pfAng = Math.sin(cycle * 0.6 + 0.5) * 0.15 + 0.3;
  const pfLen = L * 0.13;

  // Right pectoral
  ctx.save();
  ctx.translate(pfx, W * 0.72 + shimmy(0.25));
  ctx.rotate(pfAng);
  ctx.beginPath();
  ctx.ellipse(pfLen * 0.5, 0, pfLen * 0.5, pfLen * 0.12, 0, 0, TAU);
  ctx.fillStyle = rgba(18, 52, 92, alpha);
  ctx.fill();
  ctx.restore();

  // Left pectoral
  ctx.save();
  ctx.translate(pfx, -W * 0.72 + shimmy(0.25));
  ctx.rotate(-pfAng);
  ctx.beginPath();
  ctx.ellipse(pfLen * 0.5, 0, pfLen * 0.5, pfLen * 0.12, 0, 0, TAU);
  ctx.fillStyle = rgba(18, 52, 92, alpha);
  ctx.fill();
  ctx.restore();

  // ── Central dorsal ridge ──
  ctx.beginPath();
  ctx.moveTo(L * 0.08, shimmy(0.08));
  ctx.bezierCurveTo(
    L * 0.3, shimmy(0.3),
    L * 0.6, shimmy(0.6),
    L * 0.90, shimmy(0.90),
  );
  ctx.strokeStyle = rgba(30, 70, 115, alpha * 0.3);
  ctx.lineWidth = W * 0.05;
  ctx.lineCap = "round";
  ctx.stroke();

  // ── Blowhole ──
  ctx.beginPath();
  ctx.ellipse(L * 0.12, shimmy(0.12), W * 0.09, W * 0.04, 0, 0, TAU);
  ctx.fillStyle = rgba(18, 48, 82, alpha * 0.45);
  ctx.fill();
}

/* ═══════════════ Drawing: Front View ═══════════════ */

function drawFrontWhale(
  ctx: CanvasRenderingContext2D,
  size: number,
  cycle: number,
  alpha: number,
) {
  // Head-on: rounded wide head, two eyes, mouth, pectoral fins to sides
  const W = size * 0.50;
  const H = size * 0.42;

  // Subtle approaching pulse
  const pulse = 1 + Math.sin(cycle * 0.3) * 0.018;
  ctx.save();
  ctx.scale(pulse, pulse);

  // ── Head ──
  ctx.beginPath();
  ctx.moveTo(-W * 0.1, -H * 0.78);
  ctx.bezierCurveTo(
    -W * 0.5, -H * 0.88,
    -W * 0.92, -H * 0.50,
    -W, -H * 0.08,
  );
  ctx.bezierCurveTo(
    -W * 1.04, H * 0.30,
    -W * 0.85, H * 0.72,
    -W * 0.50, H * 0.92,
  );
  ctx.bezierCurveTo(-W * 0.2, H * 1.02, W * 0.2, H * 1.02, W * 0.50, H * 0.92);
  ctx.bezierCurveTo(
    W * 0.85, H * 0.72,
    W * 1.04, H * 0.30,
    W, -H * 0.08,
  );
  ctx.bezierCurveTo(
    W * 0.92, -H * 0.50,
    W * 0.50, -H * 0.88,
    W * 0.1, -H * 0.78,
  );
  ctx.bezierCurveTo(0, -H * 0.84, -W * 0.05, -H * 0.82, -W * 0.1, -H * 0.78);
  ctx.closePath();

  const g = ctx.createRadialGradient(0, 0, 0, 0, 0, W);
  g.addColorStop(0, rgba(65, 125, 180, alpha));
  g.addColorStop(0.6, rgba(40, 90, 140, alpha));
  g.addColorStop(1, rgba(22, 60, 105, alpha));
  ctx.fillStyle = g;
  ctx.fill();

  // ── Pectoral fins (sweeping) ──
  const finSweep = Math.sin(cycle * 0.8) * 0.18;
  const finLen = W * 0.95;

  ctx.save();
  ctx.translate(-W * 0.88, H * 0.1);
  ctx.rotate(-0.5 + finSweep);
  ctx.beginPath();
  ctx.ellipse(-finLen * 0.4, 0, finLen * 0.42, finLen * 0.09, 0, 0, TAU);
  ctx.fillStyle = rgba(18, 52, 92, alpha);
  ctx.fill();
  ctx.restore();

  ctx.save();
  ctx.translate(W * 0.88, H * 0.1);
  ctx.rotate(0.5 - finSweep);
  ctx.beginPath();
  ctx.ellipse(finLen * 0.4, 0, finLen * 0.42, finLen * 0.09, 0, 0, TAU);
  ctx.fillStyle = rgba(18, 52, 92, alpha);
  ctx.fill();
  ctx.restore();

  // ── Eyes ──
  const eyeY = -H * 0.05;
  ctx.beginPath();
  ctx.ellipse(-W * 0.56, eyeY, W * 0.08, H * 0.065, -0.2, 0, TAU);
  ctx.fillStyle = rgba(8, 18, 32, alpha);
  ctx.fill();
  ctx.beginPath();
  ctx.ellipse(W * 0.56, eyeY, W * 0.08, H * 0.065, 0.2, 0, TAU);
  ctx.fillStyle = rgba(8, 18, 32, alpha);
  ctx.fill();

  // Eye highlights
  ctx.beginPath();
  ctx.arc(-W * 0.58, eyeY - H * 0.025, W * 0.025, 0, TAU);
  ctx.fillStyle = rgba(140, 185, 225, alpha * 0.35);
  ctx.fill();
  ctx.beginPath();
  ctx.arc(W * 0.54, eyeY - H * 0.025, W * 0.025, 0, TAU);
  ctx.fillStyle = rgba(140, 185, 225, alpha * 0.35);
  ctx.fill();

  // ── Mouth ──
  ctx.beginPath();
  ctx.moveTo(-W * 0.58, H * 0.36);
  ctx.bezierCurveTo(-W * 0.2, H * 0.52, W * 0.2, H * 0.52, W * 0.58, H * 0.36);
  ctx.strokeStyle = rgba(28, 60, 100, alpha * 0.3);
  ctx.lineWidth = H * 0.025;
  ctx.lineCap = "round";
  ctx.stroke();

  // ── Ventral grooves ──
  ctx.strokeStyle = rgba(48, 95, 140, alpha * 0.14);
  ctx.lineWidth = H * 0.012;
  for (let i = 0; i < 3; i++) {
    const gy = H * (0.58 + i * 0.10);
    const gw = W * (0.38 - i * 0.08);
    ctx.beginPath();
    ctx.moveTo(-gw, gy);
    ctx.bezierCurveTo(-gw * 0.3, gy + H * 0.04, gw * 0.3, gy + H * 0.04, gw, gy);
    ctx.stroke();
  }

  ctx.restore(); // undo pulse scale
}

/* ═══════════════ Drawing: Diagonal View ═══════════════ */

function drawDiagonalWhale(
  ctx: CanvasRenderingContext2D,
  L: number,
  cycle: number,
  alpha: number,
  fromRight: boolean,
) {
  // Perspective-foreshortened side view: head larger, tail smaller & receding.
  // Achieved by applying a canvas shear + compression transform, then drawing
  // the normal side-view whale.
  ctx.save();

  // Compress length (whale is approaching, not fully broadside)
  ctx.scale(0.72, 1);

  // Skew to give depth — tail tilts away
  const shearY = fromRight ? 0.18 : -0.18;
  ctx.transform(1, shearY, 0, 1, 0, 0);

  // Scale tail end smaller for perspective (approximate with a slight y-scale)
  // This isn't perfect but gives a convincing "approaching at an angle" look
  drawSideWhale(ctx, L, cycle, alpha);
  ctx.restore();
}

/* ═══════════════ Water Particles ═══════════════ */

interface Bubble {
  x: number;
  y: number;
  r: number;
  speed: number;
  wobbleAmp: number;
  wobbleSpeed: number;
  phase: number;
  alpha: number;
}

interface SnowParticle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  alpha: number;
}

function initBubbles(w: number, h: number, count = 60): Bubble[] {
  return Array.from({ length: count }, () => ({
    x: Math.random() * w,
    y: Math.random() * h,
    r: 1.2 + Math.random() * 3.5,
    speed: 0.25 + Math.random() * 0.55,
    wobbleAmp: 1.5 + Math.random() * 3,
    wobbleSpeed: 0.6 + Math.random() * 1.4,
    phase: Math.random() * Math.PI * 2,
    alpha: 0.08 + Math.random() * 0.18,
  }));
}

function initSnow(w: number, h: number, count = 120): SnowParticle[] {
  return Array.from({ length: count }, () => ({
    x: Math.random() * w,
    y: Math.random() * h,
    vx: (Math.random() - 0.5) * 0.12,
    vy: 0.04 + Math.random() * 0.12,
    r: 0.5 + Math.random() * 1.2,
    alpha: 0.06 + Math.random() * 0.14,
  }));
}

function drawWaterBackground(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
) {
  const g = ctx.createLinearGradient(0, 0, 0, h);
  g.addColorStop(0,   "rgba(2,  22,  48, 1)");
  g.addColorStop(0.4, "rgba(3,  18,  38, 1)");
  g.addColorStop(1,   "rgba(1,   8,  20, 1)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
}

function drawCaustics(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  t: number,
) {
  const count = 8;
  for (let i = 0; i < count; i++) {
    // Each ray gently drifts and pulses
    const x = ((i / count) * w + Math.sin(t * 0.18 + i * 1.3) * w * 0.06) % w;
    const width = 80 + Math.sin(t * 0.25 + i * 0.9) * 60;
    const alpha = 0.018 + Math.sin(t * 0.3 + i * 0.7) * 0.012;
    const rayH = h * 0.55;

    const rg = ctx.createLinearGradient(x, 0, x, rayH);
    rg.addColorStop(0, `rgba(80,170,220,${alpha})`);
    rg.addColorStop(0.6, `rgba(40,120,180,${alpha * 0.4})`);
    rg.addColorStop(1, "rgba(0,0,0,0)");

    ctx.save();
    ctx.translate(x, 0);
    ctx.transform(1, 0, -0.18 + 0.06 * Math.sin(t * 0.1 + i), 1, 0, 0);
    ctx.fillStyle = rg;
    ctx.fillRect(-width / 2, 0, width, rayH);
    ctx.restore();
  }
}

function drawSurfaceRipples(
  ctx: CanvasRenderingContext2D,
  w: number,
  t: number,
) {
  ctx.save();
  ctx.globalAlpha = 1;
  for (let i = 0; i < 5; i++) {
    const y = 2 + i * 1.8 + Math.sin(t * 0.5 + i * 1.2) * 1.2;
    const alpha = 0.06 - i * 0.01;
    ctx.beginPath();
    ctx.moveTo(0, y);
    for (let x = 0; x <= w; x += 12) {
      ctx.lineTo(x, y + Math.sin((x / w) * Math.PI * 6 + t * 1.1 + i * 0.8) * 1.5);
    }
    ctx.strokeStyle = `rgba(100,200,240,${alpha})`;
    ctx.lineWidth = 0.8;
    ctx.stroke();
  }
  ctx.restore();
}

function updateAndDrawBubbles(
  ctx: CanvasRenderingContext2D,
  bubbles: Bubble[],
  h: number,
  t: number,
) {
  for (const b of bubbles) {
    b.y -= b.speed;
    if (b.y < -b.r * 2) {
      b.y = h + b.r;
      b.x = Math.random() * ctx.canvas.width / (window.devicePixelRatio || 1);
    }

    const cx = b.x + Math.sin(t * b.wobbleSpeed + b.phase) * b.wobbleAmp;
    const cy = b.y;

    // Bubble body
    ctx.beginPath();
    ctx.arc(cx, cy, b.r, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(120,200,240,${b.alpha})`;
    ctx.lineWidth = 0.7;
    ctx.stroke();

    // Highlight
    ctx.beginPath();
    ctx.arc(cx - b.r * 0.3, cy - b.r * 0.3, b.r * 0.35, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(200,235,255,${b.alpha * 0.6})`;
    ctx.fill();
  }
}

function updateAndDrawSnow(
  ctx: CanvasRenderingContext2D,
  snow: SnowParticle[],
  w: number,
  h: number,
) {
  for (const p of snow) {
    p.x += p.vx;
    p.y += p.vy;
    if (p.y > h + 2) { p.y = -2; p.x = Math.random() * w; }
    if (p.x < 0) p.x = w;
    if (p.x > w) p.x = 0;

    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(140,195,220,${p.alpha})`;
    ctx.fill();
  }
}

/* ═══════════════ Component ═══════════════ */

export default function SwimmingWhales({
  className = "",
  whaleCount = 8,
  baseOpacity = 0.20,
}: {
  className?: string;
  whaleCount?: number;
  baseOpacity?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const whalesRef = useRef<SwimWhale[]>([]);
  const bubblesRef = useRef<Bubble[]>([]);
  const snowRef = useRef<SnowParticle[]>([]);
  const animRef = useRef<number>(0);

  /* ── Initialise particles ── */
  const initParticles = useCallback((w: number, h: number) => {
    bubblesRef.current = initBubbles(w, h);
    snowRef.current = initSnow(w, h);
  }, []);

  /* ── Initialise whale instances ── */
  const initWhales = useCallback(
    (w: number, h: number) => {
      const rng = seededRandom(42);
      const whales: SwimWhale[] = [];

      // View distribution: 3 side, 2 top, 1 front, 1 diag-r, 1 diag-l
      const views: WhaleView[] = [
        "side",
        "side",
        "side",
        "top",
        "top",
        "front",
        "diag-r",
        "diag-l",
      ];

      for (let i = 0; i < whaleCount; i++) {
        const depth = 0.15 + (i / Math.max(whaleCount - 1, 1)) * 0.85;
        const view = views[i % views.length];

        const heading = (rng() - 0.5) * 0.5;
        // Front-view whales drift slowly downward (approaching);
        // all others swim horizontally
        const baseSpeed = 0.35 + depth * 0.55;
        const speed = view === "front" ? baseSpeed * 0.25 : baseSpeed;

        const facingRight = rng() > 0.5;
        const dir = facingRight ? 1 : -1;

        whales.push({
          x: rng() * w,
          y: h * 0.05 + rng() * h * 0.9,
          vx:
            view === "front"
              ? (rng() - 0.5) * 0.15
              : Math.cos(heading) * speed * dir,
          vy:
            view === "front"
              ? speed * 0.6
              : Math.sin(heading) * speed * 0.25,
          length:
            (view === "front" ? 55 : 100) + depth * 130 + rng() * 50,
          opacity: baseOpacity * (0.35 + depth * 0.65),
          depth,
          phase: rng() * TAU,
          view,
          facingRight,
          heading,
          targetHeading: heading,
          turnTimer: 4 + rng() * 10,
          swimCycle: rng() * TAU,
          swimSpeed: 0.025 + rng() * 0.018,
        });
      }

      // Depth-sorted for painter's algorithm
      whales.sort((a, b) => a.depth - b.depth);
      whalesRef.current = whales;
    },
    [whaleCount, baseOpacity],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let w = 0;
    let h = 0;
    let dpr = 1;

    const resize = () => {
      dpr = window.devicePixelRatio || 1;
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      if (whalesRef.current.length === 0) {
          initWhales(w, h);
          initParticles(w, h);
        }
      };
    resize();
    window.addEventListener("resize", resize);

    /* ── Animation loop ── */
    const animate = () => {
      const t = performance.now() * 0.001;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      // ── Water background (replaces clearRect) ──
      drawWaterBackground(ctx, w, h);

      // ── Caustic rays from above ──
      drawCaustics(ctx, w, h, t);

      // ── Surface shimmer at top ──
      drawSurfaceRipples(ctx, w, t);

      // ── Marine snow (behind whales) ──
      updateAndDrawSnow(ctx, snowRef.current, w, h);

      for (const wh of whalesRef.current) {
        // Advance swim cycle
        wh.swimCycle = (wh.swimCycle + wh.swimSpeed) % TAU;

        // ── Direction changes ──
        wh.turnTimer -= 1 / 60;
        if (wh.turnTimer <= 0) {
          wh.targetHeading = (Math.random() - 0.5) * 0.45;
          wh.turnTimer = 5 + Math.random() * 12;
          // Occasionally reverse horizontal direction (not for front-view)
          if (wh.view !== "front" && Math.random() < 0.18) {
            wh.facingRight = !wh.facingRight;
            wh.vx = -wh.vx;
          }
        }

        // Smooth heading interpolation
        wh.heading += (wh.targetHeading - wh.heading) * 0.008;

        // Update velocity toward heading
        const sp = Math.sqrt(wh.vx * wh.vx + wh.vy * wh.vy);
        if (wh.view !== "front") {
          const dir = wh.vx >= 0 ? 1 : -1;
          wh.vx +=
            (Math.cos(wh.heading) * sp * dir - wh.vx) * 0.006;
          wh.vy +=
            (Math.sin(wh.heading) * sp * 0.3 - wh.vy) * 0.01;
        }

        // Gentle vertical bob
        wh.y += Math.sin(wh.swimCycle * 0.35 + wh.phase) * 0.08;

        // Position update
        wh.x += wh.vx;
        wh.y += wh.vy;

        // Soft vertical containment
        if (wh.y < h * 0.02) wh.vy += 0.018;
        if (wh.y > h * 0.97) wh.vy -= 0.018;
        wh.vy = Math.max(-0.5, Math.min(0.5, wh.vy));

        // Screen wrap
        const buf = wh.length * 1.3;
        if (wh.view === "front") {
          // Front-view whales drift down; wrap at bottom
          if (wh.y > h + buf) {
            wh.y = -buf;
            wh.x = w * 0.15 + Math.random() * w * 0.7;
          }
        } else {
          if (wh.vx > 0 && wh.x > w + buf) {
            wh.x = -buf;
            wh.y = h * 0.08 + Math.random() * h * 0.84;
          } else if (wh.vx < 0 && wh.x < -buf) {
            wh.x = w + buf;
            wh.y = h * 0.08 + Math.random() * h * 0.84;
          }
        }

        // ── Render ──
        ctx.save();
        ctx.translate(wh.x, wh.y);

        // Subtle tilt following swim direction
        const tilt = wh.heading * 0.12;
        ctx.rotate(tilt);

        switch (wh.view) {
          case "side":
            if (!wh.facingRight) ctx.scale(-1, 1);
            drawSideWhale(ctx, wh.length, wh.swimCycle, wh.opacity);
            break;

          case "top": {
            // Rotate so the whale points in its travel direction
            const swimDir = Math.atan2(wh.vy, wh.vx);
            ctx.rotate(swimDir);
            drawTopWhale(ctx, wh.length, wh.swimCycle, wh.opacity);
            break;
          }

          case "front":
            drawFrontWhale(
              ctx,
              wh.length,
              wh.swimCycle,
              wh.opacity,
            );
            break;

          case "diag-r":
            if (!wh.facingRight) ctx.scale(-1, 1);
            drawDiagonalWhale(
              ctx,
              wh.length,
              wh.swimCycle,
              wh.opacity,
              true,
            );
            break;

          case "diag-l":
            if (!wh.facingRight) ctx.scale(-1, 1);
            drawDiagonalWhale(
              ctx,
              wh.length,
              wh.swimCycle,
              wh.opacity,
              false,
            );
            break;
        }

        ctx.restore();
      }

      // ── Bubbles (in front of whales) ──
      updateAndDrawBubbles(ctx, bubblesRef.current, h, t);

      animRef.current = requestAnimationFrame(animate);
    };

    animRef.current = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(animRef.current);
    };
  }, [initWhales, initParticles]);

  return (
    <canvas
      ref={canvasRef}
      className={`pointer-events-none fixed inset-0 z-0 ${className}`}
      aria-hidden="true"
    />
  );
}
