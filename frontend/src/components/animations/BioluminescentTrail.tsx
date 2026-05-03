"use client";

import { useEffect, useRef, useCallback } from "react";

interface Particle {
  x: number;
  y: number;
  size: number;
  life: number;
  maxLife: number;
  vx: number;
  vy: number;
  hue: number;
}

/**
 * Bioluminescent cursor trail — mouse-following particles that fade like
 * deep-sea bioluminescent plankton disturbed by movement.
 */
export default function BioluminescentTrail({
  className = "",
  maxParticles = 35,
  color = "180, 90%",
}: {
  className?: string;
  maxParticles?: number;
  /** HSL hue + saturation (e.g. "180, 90%" for cyan) */
  color?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particles = useRef<Particle[]>([]);
  const mousePos = useRef({ x: -100, y: -100 });
  const animFrame = useRef<number>(0);
  const lastEmit = useRef(0);

  const emit = useCallback(
    (x: number, y: number) => {
      const now = Date.now();
      if (now - lastEmit.current < 30) return;
      lastEmit.current = now;

      const count = 2 + Math.floor(Math.random() * 2);
      for (let i = 0; i < count; i++) {
        if (particles.current.length >= maxParticles) {
          particles.current.shift();
        }
        particles.current.push({
          x: x + (Math.random() - 0.5) * 12,
          y: y + (Math.random() - 0.5) * 12,
          size: 2 + Math.random() * 4,
          life: 0,
          maxLife: 40 + Math.random() * 30,
          vx: (Math.random() - 0.5) * 0.8,
          vy: (Math.random() - 0.5) * 0.8 - 0.3,
          hue: 175 + Math.random() * 20,
        });
      }
    },
    [maxParticles],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const onMove = (e: MouseEvent) => {
      mousePos.current = { x: e.clientX, y: e.clientY };
      emit(e.clientX, e.clientY);
    };
    window.addEventListener("mousemove", onMove, { passive: true });

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      particles.current = particles.current.filter((p) => {
        p.life++;
        if (p.life > p.maxLife) return false;

        p.x += p.vx;
        p.y += p.vy;
        p.vy -= 0.01; // slight float upward

        const progress = p.life / p.maxLife;
        const alpha = progress < 0.2
          ? progress / 0.2
          : 1 - (progress - 0.2) / 0.8;
        const currentSize = p.size * (1 - progress * 0.5);

        ctx.beginPath();
        ctx.arc(p.x, p.y, currentSize, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${p.hue}, 90%, 70%, ${alpha * 0.6})`;
        ctx.fill();

        // Glow ring
        ctx.beginPath();
        ctx.arc(p.x, p.y, currentSize * 2.5, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${p.hue}, 90%, 70%, ${alpha * 0.1})`;
        ctx.fill();

        return true;
      });

      animFrame.current = requestAnimationFrame(animate);
    };
    animFrame.current = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMove);
      cancelAnimationFrame(animFrame.current);
    };
  }, [emit, color]);

  return (
    <canvas
      ref={canvasRef}
      className={`pointer-events-none fixed inset-0 z-50 ${className}`}
      aria-hidden="true"
    />
  );
}
