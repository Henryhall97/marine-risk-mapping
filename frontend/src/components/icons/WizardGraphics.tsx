/**
 * Inline SVG field-guide diagrams for the species ID wizard.
 *
 * Each component renders a simplified but anatomically informative
 * comparison diagram suitable for dark backgrounds (ocean-950 tones).
 * Keys match the `imgKey` values in STAGE_GUIDANCE from IDHelper.tsx.
 *
 * Design principles:
 * - Silhouettes are simplified but capture diagnostic features
 *   (dorsal fin shape, head profile, relative size, beak presence)
 * - Annotation leader lines + text labels highlight key ID features
 * - Consistent colour coding: teal = baleen, purple = toothed,
 *   indigo = dolphins, orange = porpoises
 */
import { type SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;

/* ── Shared annotation helpers ─────────────────────────── */

/** Leader line from (x1,y1) → (tx,ty) with a text label. */
function Ann({
  x1,
  y1,
  tx,
  ty,
  label,
  color = "#67e8f9",
  anchor = "start",
}: {
  x1: number;
  y1: number;
  tx: number;
  ty: number;
  label: string;
  color?: string;
  anchor?: "start" | "end" | "middle";
}) {
  return (
    <g>
      {/* Circle at feature */}
      <circle cx={x1} cy={y1} r={3} fill="none" stroke={color} strokeWidth={1.2} opacity={0.9} />
      <circle cx={x1} cy={y1} r={1} fill={color} opacity={0.9} />
      {/* Leader line */}
      <line x1={x1} y1={y1} x2={tx} y2={ty} stroke={color} strokeWidth={0.8} opacity={0.6} />
      {/* Text label */}
      <text
        x={tx + (anchor === "end" ? -3 : anchor === "middle" ? 0 : 3)}
        y={ty + 1}
        fill={color}
        fontSize={6.5}
        fontFamily="system-ui, -apple-system, sans-serif"
        textAnchor={anchor}
        dominantBaseline="middle"
        opacity={0.95}
      >
        {label}
      </text>
    </g>
  );
}

/** Dashed separator line */
function Sep({ x, y1, y2, color = "#475569" }: { x: number; y1: number; y2: number; color?: string }) {
  return <line x1={x} y1={y1} x2={x} y2={y2} stroke={color} strokeWidth={0.5} strokeDasharray="2 2" opacity={0.5} />;
}

/** Column label */
function ColLabel({ x, y, text, color = "#e2e8f0" }: { x: number; y: number; text: string; color?: string }) {
  return (
    <text x={x} y={y} fill={color} fontSize={8} fontWeight={600}
      fontFamily="system-ui, -apple-system, sans-serif" textAnchor="middle" opacity={0.9}
    >{text}</text>
  );
}

/** Sub-label */
function SubLabel({ x, y, text, color = "#94a3b8" }: { x: number; y: number; text: string; color?: string }) {
  return (
    <text x={x} y={y} fill={color} fontSize={5.5}
      fontFamily="system-ui, -apple-system, sans-serif" textAnchor="middle" opacity={0.8}
    >{text}</text>
  );
}

/* ─── 1. Start: Whale vs Dolphin vs Porpoise ────────────── */
export function StageStartComparison(props: P) {
  return (
    <svg viewBox="0 0 320 140" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      {/* Whale — LARGE */}
      <g>
        <path
          d="M20 52c3-12 18-24 40-26s36 2 52 8c14 5 28 8 42 6 10-1 16 3 16 10s-5 13-16 16c-16 5-38 5-56 2-18-4-34-2-46 4-12 5-24 6-34 3-8-3-6-12 2-23z"
          fill="#2dd4bf" fillOpacity={0.15} stroke="#2dd4bf" strokeWidth={1}
        />
        <path d="M168 62c4-7 12-12 20-10s6 9 0 14-16 6-20 3z" fill="#2dd4bf" fillOpacity={0.12} stroke="#2dd4bf" strokeWidth={0.8} />
        <path d="M38 26c-2-8 0-16 2-22" stroke="#67e8f9" strokeWidth={0.8} strokeLinecap="round" strokeDasharray="1.5 1.5" />
        <path d="M42 26c2-8 3-16 5-22" stroke="#67e8f9" strokeWidth={0.8} strokeLinecap="round" strokeDasharray="1.5 1.5" />
        <path d="M120 48c2-6 5-8 8-6" stroke="#2dd4bf" strokeWidth={0.8} opacity={0.5} />
      </g>
      {/* Dolphin — medium */}
      <g>
        <path
          d="M220 62c2-5 8-10 16-10s12 2 18 4c5 2 10 3 14 2 3 0 5 1 5 3s-2 4-5 5c-5 2-12 2-18 1-6-2-10-1-14 1-4 2-8 2-12 1-3-1-3-3 0-7z"
          fill="#818cf8" fillOpacity={0.18} stroke="#818cf8" strokeWidth={0.9}
        />
        <path d="M218 64c-3 0-6-1-6-2" stroke="#818cf8" strokeWidth={0.7} />
        <path d="M250 56c1-4 3-7 6-5" stroke="#818cf8" strokeWidth={0.8} />
        <path d="M270 63c2-3 5-5 8-4s2 4 0 5-6 2-8 1z" fill="#818cf8" fillOpacity={0.1} stroke="#818cf8" strokeWidth={0.6} />
      </g>
      {/* Porpoise — small */}
      <g>
        <path
          d="M288 66c1-3 4-6 8-6s6 1 9 2c3 1 5 2 7 1 1 0 2 1 2 2s-1 2-2 3c-3 1-6 1-9 0-3-1-5 0-7 1s-4 1-6 0c-2 0-2-1 0-3z"
          fill="#f97316" fillOpacity={0.18} stroke="#f97316" strokeWidth={0.9}
        />
        <path d="M300 63c0-3 2-4 3-3" stroke="#f97316" strokeWidth={0.7} />
      </g>
      {/* Baselines */}
      <line x1={16} y1={88} x2={190} y2={88} stroke="#2dd4bf" strokeWidth={0.5} opacity={0.3} />
      <line x1={216} y1={88} x2={280} y2={88} stroke="#818cf8" strokeWidth={0.5} opacity={0.3} />
      <line x1={286} y1={88} x2={312} y2={88} stroke="#f97316" strokeWidth={0.5} opacity={0.3} />
      {/* Annotations */}
      <Ann x1={40} y1={28} tx={10} ty={14} label="Visible blow spout" color="#67e8f9" />
      <Ann x1={122} y1={48} tx={140} ty={36} label="Dorsal fin (some species)" color="#2dd4bf" />
      <Ann x1={252} y1={56} tx={248} ty={42} label="Curved dorsal fin" color="#818cf8" anchor="end" />
      <Ann x1={218} y1={64} tx={210} ty={74} label="Beak-like snout" color="#818cf8" anchor="end" />
      <Ann x1={300} y1={63} tx={296} ty={46} label="Small triangular fin" color="#f97316" anchor="end" />
      <Ann x1={294} y1={68} tx={286} ty={78} label="Blunt, no beak" color="#f97316" anchor="end" />
      {/* Labels */}
      <ColLabel x={100} y={100} text="Whale" color="#2dd4bf" />
      <SubLabel x={100} y={108} text="4–30 m" color="#5eead4" />
      <ColLabel x={248} y={100} text="Dolphin" color="#818cf8" />
      <SubLabel x={248} y={108} text="1.5–9 m" color="#a5b4fc" />
      <ColLabel x={300} y={100} text="Porpoise" color="#f97316" />
      <SubLabel x={300} y={108} text="1.2–2.5 m" color="#fb923c" />
      <Sep x={205} y1={30} y2={115} />
      <Sep x={283} y1={45} y2={115} />
    </svg>
  );
}

/* ─── 2. Baleen vs Toothed whale ─────────────────────────── */
export function StageWhaleKindComparison(props: P) {
  return (
    <svg viewBox="0 0 320 130" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      {/* Baleen whale */}
      <g>
        <path
          d="M20 48c3-10 14-18 30-18s26 3 38 8c10 4 20 6 28 4 6-1 8 2 8 7s-3 10-10 13c-10 4-24 4-36 2-14-3-24-1-34 3-10 4-18 5-26 3-6-2-5-10 2-22z"
          fill="#2dd4bf" fillOpacity={0.15} stroke="#2dd4bf" strokeWidth={1}
        />
        <path d="M26 50c-2 2-3 6-2 10" stroke="#2dd4bf" strokeWidth={0.8} />
        <g opacity={0.7}>
          <line x1={26} y1={48} x2={26} y2={56} stroke="#5eead4" strokeWidth={0.5} />
          <line x1={28} y1={47} x2={28} y2={57} stroke="#5eead4" strokeWidth={0.5} />
          <line x1={30} y1={46} x2={30} y2={57} stroke="#5eead4" strokeWidth={0.5} />
          <line x1={32} y1={46} x2={32} y2={56} stroke="#5eead4" strokeWidth={0.5} />
          <line x1={34} y1={46} x2={34} y2={55} stroke="#5eead4" strokeWidth={0.5} />
        </g>
        <path d="M42 30c-2-6-1-12 1-18" stroke="#67e8f9" strokeWidth={0.7} strokeLinecap="round" strokeDasharray="1.5 1.5" />
        <path d="M46 30c2-6 3-12 5-18" stroke="#67e8f9" strokeWidth={0.7} strokeLinecap="round" strokeDasharray="1.5 1.5" />
        <path d="M120 56c3-5 9-8 14-6s4 6 0 10-10 4-14 2z" fill="#2dd4bf" fillOpacity={0.1} stroke="#2dd4bf" strokeWidth={0.7} />
        <g opacity={0.4}>
          <line x1={38} y1={56} x2={58} y2={60} stroke="#2dd4bf" strokeWidth={0.4} />
          <line x1={38} y1={58} x2={58} y2={62} stroke="#2dd4bf" strokeWidth={0.4} />
          <line x1={38} y1={60} x2={58} y2={64} stroke="#2dd4bf" strokeWidth={0.4} />
        </g>
      </g>
      {/* Toothed whale */}
      <g>
        <path
          d="M190 44c4-8 16-14 30-14s20 3 28 6c8 3 16 5 24 4 5-1 8 2 8 6s-3 8-8 10c-8 3-18 3-28 1-10-2-18-1-26 2-8 3-14 4-20 2-5-2-4-7 2-17z"
          fill="#a78bfa" fillOpacity={0.15} stroke="#a78bfa" strokeWidth={1}
        />
        <g opacity={0.7}>
          <circle cx={196} cy={48} r={0.8} fill="#c4b5fd" />
          <circle cx={198} cy={47} r={0.8} fill="#c4b5fd" />
          <circle cx={200} cy={46.5} r={0.8} fill="#c4b5fd" />
          <circle cx={202} cy={46} r={0.8} fill="#c4b5fd" />
          <circle cx={196} cy={50} r={0.8} fill="#c4b5fd" />
          <circle cx={198} cy={50.5} r={0.8} fill="#c4b5fd" />
          <circle cx={200} cy={50} r={0.8} fill="#c4b5fd" />
          <circle cx={202} cy={49.5} r={0.8} fill="#c4b5fd" />
        </g>
        <path d="M212 30c-3-8-5-14-8-20" stroke="#c4b5fd" strokeWidth={0.7} strokeLinecap="round" strokeDasharray="1.5 1.5" />
        <path d="M288 52c3-4 8-6 12-4s3 5 0 8-8 3-12 1z" fill="#a78bfa" fillOpacity={0.1} stroke="#a78bfa" strokeWidth={0.7} />
      </g>
      <Sep x={160} y1={8} y2={120} color="#64748b" />
      <Ann x1={28} y1={50} tx={10} ty={78} label="Baleen plates (filter)" color="#5eead4" />
      <Ann x1={44} y1={30} tx={60} ty={16} label="V-shaped double blow" color="#67e8f9" />
      <Ann x1={46} y1={60} tx={60} ty={78} label="Throat grooves" color="#5eead4" />
      <Ann x1={200} y1={48} tx={180} ty={78} label="Conical teeth" color="#c4b5fd" />
      <Ann x1={212} y1={30} tx={228} ty={16} label="Single blowhole" color="#c4b5fd" />
      <Ann x1={210} y1={38} tx={250} ty={78} label="Rounded / squared head" color="#c4b5fd" />
      <ColLabel x={80} y={100} text="Baleen Whale" color="#2dd4bf" />
      <SubLabel x={80} y={109} text="Filter feeders · 2 blowholes" color="#5eead4" />
      <ColLabel x={240} y={100} text="Toothed Whale" color="#a78bfa" />
      <SubLabel x={240} y={109} text="Active hunters · 1 blowhole" color="#c4b5fd" />
    </svg>
  );
}

/* ─── 3. Baleen species (4) ──────────────────────────────── */
export function StageBaleenSpecies(props: P) {
  return (
    <svg viewBox="0 0 320 130" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      {/* Right Whale */}
      <g>
        <path
          d="M8 48c2-7 8-12 16-12s14 2 20 5c5 2 8 3 10 2 2-1 2 1 2 4s-2 6-6 8c-6 3-14 3-20 1-6-2-12-1-16 2-4 2-8 3-10 1-2-1-1-5 4-11z"
          fill="#2dd4bf" fillOpacity={0.15} stroke="#2dd4bf" strokeWidth={0.9}
        />
        <circle cx={14} cy={42} r={1.5} fill="#e2e8f0" opacity={0.6} />
        <circle cx={16} cy={40} r={1} fill="#e2e8f0" opacity={0.5} />
        <circle cx={12} cy={44} r={1} fill="#e2e8f0" opacity={0.5} />
      </g>
      {/* Humpback */}
      <g>
        <path
          d="M88 46c2-7 8-12 16-12s14 2 20 5c5 2 8 3 10 2 2-1 2 1 2 4s-2 6-6 8c-6 3-14 3-20 1-6-2-12-1-16 2-4 2-8 3-10 1-2-1-1-5 4-11z"
          fill="#2dd4bf" fillOpacity={0.15} stroke="#2dd4bf" strokeWidth={0.9}
        />
        <path d="M102 54c-4 6-10 14-16 18" stroke="#2dd4bf" strokeWidth={0.8} opacity={0.6} />
        <path d="M118 44c1-3 3-4 4-2" stroke="#2dd4bf" strokeWidth={0.8} />
        <circle cx={92} cy={42} r={0.8} fill="#2dd4bf" opacity={0.4} />
        <circle cx={94} cy={41} r={0.8} fill="#2dd4bf" opacity={0.4} />
        <circle cx={93} cy={44} r={0.8} fill="#2dd4bf" opacity={0.4} />
      </g>
      {/* Fin Whale */}
      <g>
        <path
          d="M168 46c2-7 10-12 20-12s16 2 24 5c6 2 10 3 14 2 3-1 4 1 4 4s-2 6-6 8c-8 3-18 3-26 1-8-2-14-1-20 2-6 2-10 3-14 1-3-1-2-5 4-11z"
          fill="#2dd4bf" fillOpacity={0.15} stroke="#2dd4bf" strokeWidth={0.9}
        />
        <path d="M210 42c1-6 4-10 7-7" stroke="#2dd4bf" strokeWidth={0.9} />
        <path d="M172 48c-1 2-1 5 0 6" stroke="#e2e8f0" strokeWidth={0.6} opacity={0.5} />
      </g>
      {/* Blue Whale */}
      <g>
        <path
          d="M248 46c2-7 12-14 24-14s18 2 26 5c7 2 12 3 16 2 3-1 4 1 4 4s-2 6-8 8c-8 3-20 3-28 1-10-2-16-1-22 2-6 2-12 3-16 1-3-1-2-5 4-9z"
          fill="#2dd4bf" fillOpacity={0.15} stroke="#2dd4bf" strokeWidth={0.9}
        />
        <path d="M302 46c0-2 1-3 2-2" stroke="#2dd4bf" strokeWidth={0.7} />
        <g opacity={0.2}>
          <circle cx={270} cy={50} r={2} fill="#2dd4bf" />
          <circle cx={280} cy={48} r={1.5} fill="#2dd4bf" />
          <circle cx={290} cy={52} r={1.8} fill="#2dd4bf" />
          <circle cx={260} cy={52} r={1.2} fill="#2dd4bf" />
        </g>
      </g>
      <Ann x1={14} y1={42} tx={4} ty={28} label="Callosities" color="#67e8f9" />
      <Ann x1={36} y1={42} tx={40} ty={28} label="No dorsal fin" color="#67e8f9" />
      <Ann x1={88} y1={72} tx={76} ty={82} label="Long pectoral fins" color="#67e8f9" />
      <Ann x1={119} y1={43} tx={128} ty={28} label="Dorsal hump" color="#67e8f9" />
      <Ann x1={212} y1={39} tx={222} ty={26} label="Tall sickle dorsal" color="#67e8f9" />
      <Ann x1={172} y1={50} tx={168} ty={74} label="Asymmetric jaw" color="#67e8f9" anchor="end" />
      <Ann x1={303} y1={45} tx={308} ty={30} label="Tiny dorsal" color="#67e8f9" />
      <Ann x1={270} y1={50} tx={268} ty={74} label="Mottled blue-grey" color="#67e8f9" anchor="end" />
      <Sep x={75} y1={25} y2={112} />
      <Sep x={155} y1={25} y2={112} />
      <Sep x={235} y1={25} y2={112} />
      <ColLabel x={38} y={98} text="Right Whale" color="#2dd4bf" />
      <ColLabel x={118} y={98} text="Humpback" color="#2dd4bf" />
      <ColLabel x={198} y={98} text="Fin Whale" color="#2dd4bf" />
      <ColLabel x={280} y={98} text="Blue Whale" color="#2dd4bf" />
    </svg>
  );
}

/* ─── 4. Toothed species (4) ─────────────────────────────── */
export function StageToothedSpecies(props: P) {
  return (
    <svg viewBox="0 0 320 130" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      {/* Sperm Whale */}
      <g>
        <path
          d="M6 44c0-8 8-16 22-16s16 2 20 5c4 2 8 4 12 3 3-1 4 1 4 4s-2 6-6 8c-6 3-14 3-20 1-6-2-10-1-16 3-6 3-12 4-16 2-3-2-2-5 0-10z"
          fill="#a78bfa" fillOpacity={0.15} stroke="#a78bfa" strokeWidth={0.9}
        />
        <path d="M8 32c0-4 2-6 6-6s8 0 10 2" stroke="#a78bfa" strokeWidth={0.6} opacity={0.4} />
        <path d="M16 28c-4-6-7-12-10-18" stroke="#c4b5fd" strokeWidth={0.7} strokeLinecap="round" strokeDasharray="1.5 1.5" />
      </g>
      {/* Beaked Whale */}
      <g>
        <path
          d="M88 46c2-6 8-10 14-10s10 2 14 4c4 2 8 3 10 2 2-1 2 1 2 3s-2 5-5 6c-4 2-10 2-14 1-4-2-8-1-12 1-4 2-8 3-10 1-2-1-1-4 1-8z"
          fill="#a78bfa" fillOpacity={0.15} stroke="#a78bfa" strokeWidth={0.9}
        />
        <path d="M86 48c-3 0-6-1-8-1" stroke="#a78bfa" strokeWidth={0.7} />
        <g opacity={0.3}>
          <line x1={96} y1={44} x2={108} y2={45} stroke="#c4b5fd" strokeWidth={0.4} />
          <line x1={98} y1={48} x2={110} y2={49} stroke="#c4b5fd" strokeWidth={0.4} />
          <line x1={100} y1={46} x2={112} y2={47} stroke="#c4b5fd" strokeWidth={0.4} />
        </g>
      </g>
      {/* Beluga */}
      <g>
        <path
          d="M170 46c2-6 8-10 14-10s10 2 14 4c4 2 8 3 10 2 2-1 2 1 2 3s-2 5-5 6c-4 2-10 2-14 1-4-2-8-1-12 1-4 2-8 3-10 1-2-1-1-4 1-8z"
          fill="#e2e8f0" fillOpacity={0.2} stroke="#e2e8f0" strokeWidth={0.9}
        />
        <path d="M172 40c-2-4 0-8 4-8" stroke="#e2e8f0" strokeWidth={0.7} opacity={0.6} />
      </g>
      {/* Narwhal */}
      <g>
        <path
          d="M252 46c2-6 8-10 14-10s10 2 14 4c4 2 8 3 10 2 2-1 2 1 2 3s-2 5-5 6c-4 2-10 2-14 1-4-2-8-1-12 1-4 2-8 3-10 1-2-1-1-4 1-8z"
          fill="#a78bfa" fillOpacity={0.15} stroke="#a78bfa" strokeWidth={0.9}
        />
        <line x1={250} y1={44} x2={230} y2={40} stroke="#c4b5fd" strokeWidth={1} />
        <g opacity={0.3}>
          <line x1={234} y1={40.5} x2={236} y2={42} stroke="#c4b5fd" strokeWidth={0.4} />
          <line x1={238} y1={41} x2={240} y2={42.5} stroke="#c4b5fd" strokeWidth={0.4} />
          <line x1={242} y1={41.5} x2={244} y2={43} stroke="#c4b5fd" strokeWidth={0.4} />
          <line x1={246} y1={42} x2={248} y2={43.5} stroke="#c4b5fd" strokeWidth={0.4} />
        </g>
        <g opacity={0.2}>
          <circle cx={264} cy={46} r={1.2} fill="#a78bfa" />
          <circle cx={270} cy={44} r={1} fill="#a78bfa" />
          <circle cx={274} cy={48} r={0.8} fill="#a78bfa" />
        </g>
      </g>
      <Ann x1={14} y1={34} tx={4} ty={22} label="Massive squared head" color="#c4b5fd" />
      <Ann x1={16} y1={28} tx={30} ty={12} label="Forward-left blow" color="#c4b5fd" />
      <Ann x1={82} y1={47} tx={72} ty={66} label="Elongated beak" color="#c4b5fd" />
      <Ann x1={104} y1={46} tx={112} ty={66} label="Linear scars" color="#c4b5fd" />
      <Ann x1={174} y1={38} tx={164} ty={24} label="Rounded melon" color="#e2e8f0" />
      <Ann x1={198} y1={44} tx={198} ty={66} label="All white · No dorsal" color="#e2e8f0" anchor="middle" />
      <Ann x1={236} y1={40} tx={224} ty={28} label="Spiral tusk" color="#c4b5fd" anchor="end" />
      <Ann x1={280} y1={44} tx={290} ty={28} label="No dorsal fin" color="#c4b5fd" />
      <Sep x={75} y1={10} y2={112} />
      <Sep x={157} y1={10} y2={112} />
      <Sep x={240} y1={10} y2={112} />
      <ColLabel x={38} y={98} text="Sperm Whale" color="#a78bfa" />
      <ColLabel x={116} y={98} text="Beaked Whale" color="#a78bfa" />
      <ColLabel x={196} y={98} text="Beluga" color="#e2e8f0" />
      <ColLabel x={278} y={98} text="Narwhal" color="#a78bfa" />
    </svg>
  );
}

/* ─── 5. Dolphin species (5) ─────────────────────────────── */
export function StageDolphinSpecies(props: P) {
  return (
    <svg viewBox="0 0 320 130" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      {/* Orca */}
      <g>
        <path
          d="M6 48c1-5 6-10 12-10s10 1 14 3c3 2 6 3 8 2 2-1 2 1 2 3s-1 4-4 6c-4 2-10 2-14 1-4-2-8 0-10 1-2 2-6 2-8 1-2-1-1-3 0-7z"
          fill="#818cf8" fillOpacity={0.15} stroke="#818cf8" strokeWidth={0.9}
        />
        <path d="M28 42c0-8 3-14 5-10" stroke="#818cf8" strokeWidth={0.9} />
        <ellipse cx={12} cy={46} rx={2} ry={1.2} fill="#e2e8f0" opacity={0.5} />
        <path d="M10 52c4 2 12 2 20 0" stroke="#e2e8f0" strokeWidth={0.5} opacity={0.3} />
      </g>
      {/* Bottlenose */}
      <g>
        <path
          d="M68 48c1-5 6-9 10-9s8 1 12 3c3 2 6 3 8 2 1-1 2 1 2 2s-1 4-3 5c-3 2-8 2-12 1-4-2-6 0-8 1-2 2-5 2-7 1-2-1-1-3 0-6z"
          fill="#818cf8" fillOpacity={0.15} stroke="#818cf8" strokeWidth={0.9}
        />
        <path d="M66 50c-2 0-4 0-5 0" stroke="#818cf8" strokeWidth={0.6} />
        <path d="M86 44c1-4 3-6 4-4" stroke="#818cf8" strokeWidth={0.8} />
      </g>
      {/* Common Dolphin */}
      <g>
        <path
          d="M130 48c1-5 6-9 10-9s8 1 12 3c3 2 6 3 8 2 1-1 2 1 2 2s-1 4-3 5c-3 2-8 2-12 1-4-2-6 0-8 1-2 2-5 2-7 1-2-1-1-3 0-6z"
          fill="#818cf8" fillOpacity={0.15} stroke="#818cf8" strokeWidth={0.9}
        />
        <path d="M138 48c4-2 8-3 12-2" stroke="#fbbf24" strokeWidth={0.8} opacity={0.4} />
        <path d="M148 46c4 0 6 2 8 4" stroke="#94a3b8" strokeWidth={0.8} opacity={0.3} />
      </g>
      {/* Pilot Whale */}
      <g>
        <path
          d="M192 46c1-5 6-10 12-10s10 1 14 3c3 2 6 3 8 2 2-1 2 1 2 3s-1 4-4 6c-4 2-10 2-14 1-4-2-8 0-10 1-2 2-6 2-8 1-2-1-1-3 0-7z"
          fill="#818cf8" fillOpacity={0.15} stroke="#818cf8" strokeWidth={0.9}
        />
        <path d="M194 40c-2-3 0-6 3-6" stroke="#818cf8" strokeWidth={0.7} opacity={0.6} />
        <path d="M214 42c0-3 2-4 4-3" stroke="#818cf8" strokeWidth={0.8} />
      </g>
      {/* Risso's */}
      <g>
        <path
          d="M256 48c1-5 6-9 10-9s8 1 12 3c3 2 6 3 8 2 1-1 2 1 2 2s-1 4-3 5c-3 2-8 2-12 1-4-2-6 0-8 1-2 2-5 2-7 1-2-1-1-3 0-6z"
          fill="#818cf8" fillOpacity={0.15} stroke="#818cf8" strokeWidth={0.9}
        />
        <path d="M258 44c-1-2 0-4 2-4" stroke="#818cf8" strokeWidth={0.7} opacity={0.6} />
        <g opacity={0.3}>
          <line x1={264} y1={46} x2={272} y2={46.5} stroke="#e2e8f0" strokeWidth={0.4} />
          <line x1={266} y1={48} x2={274} y2={48.5} stroke="#e2e8f0" strokeWidth={0.4} />
          <line x1={268} y1={50} x2={276} y2={50.5} stroke="#e2e8f0" strokeWidth={0.4} />
        </g>
      </g>
      <Ann x1={29} y1={38} tx={22} ty={20} label="Tall dorsal (1.8 m male)" color="#a5b4fc" />
      <Ann x1={12} y1={46} tx={6} ty={68} label="Eye patch" color="#a5b4fc" />
      <Ann x1={63} y1={50} tx={55} ty={70} label="Short beak" color="#a5b4fc" />
      <Ann x1={87} y1={43} tx={87} ty={26} label="Curved dorsal" color="#a5b4fc" anchor="middle" />
      <Ann x1={142} y1={48} tx={140} ty={70} label="Hourglass pattern" color="#fbbf24" />
      <Ann x1={196} y1={38} tx={186} ty={22} label="Bulbous melon" color="#a5b4fc" anchor="end" />
      <Ann x1={215} y1={41} tx={222} ty={22} label="Low sickle dorsal" color="#a5b4fc" />
      <Ann x1={270} y1={48} tx={278} ty={70} label="Heavily scarred" color="#e2e8f0" />
      <Ann x1={258} y1={44} tx={250} ty={28} label="No beak" color="#e2e8f0" anchor="end" />
      <Sep x={55} y1={15} y2={112} />
      <Sep x={120} y1={15} y2={112} />
      <Sep x={182} y1={15} y2={112} />
      <Sep x={246} y1={15} y2={112} />
      <ColLabel x={28} y={98} text="Orca" color="#818cf8" />
      <ColLabel x={86} y={98} text="Bottlenose" color="#818cf8" />
      <ColLabel x={150} y={98} text="Common" color="#818cf8" />
      <ColLabel x={214} y={98} text="Pilot Whale" color="#818cf8" />
      <ColLabel x={280} y={98} text="Risso's" color="#818cf8" />
    </svg>
  );
}

/* ─── 6. Porpoise species (3) ────────────────────────────── */
export function StagePorpoiseSpecies(props: P) {
  return (
    <svg viewBox="0 0 320 120" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      {/* Harbour Porpoise */}
      <g>
        <path
          d="M18 46c1-5 6-10 12-10s10 2 14 4c4 2 7 3 10 2 2-1 3 1 3 3s-2 5-5 7c-4 2-10 2-16 1-6-2-10 0-14 2-4 2-6 2-8 0-2-1-1-4 4-9z"
          fill="#f97316" fillOpacity={0.15} stroke="#f97316" strokeWidth={0.9}
        />
        <path d="M42 40c0-4 2-6 4-4" stroke="#f97316" strokeWidth={0.9} />
        <path d="M18 42c-1-2 0-4 2-4" stroke="#f97316" strokeWidth={0.6} opacity={0.5} />
      </g>
      {/* Dall's Porpoise */}
      <g>
        <path
          d="M120 46c1-5 6-10 12-10s10 2 14 4c4 2 7 3 10 2 2-1 3 1 3 3s-2 5-5 7c-4 2-10 2-16 1-6-2-10 0-14 2-4 2-6 2-8 0-2-1-1-4 4-9z"
          fill="#f97316" fillOpacity={0.15} stroke="#f97316" strokeWidth={0.9}
        />
        <path d="M134 48c4-1 8-1 12 0" stroke="#e2e8f0" strokeWidth={1.5} opacity={0.3} />
        <g opacity={0.5}>
          <path d="M154 40c2-4 3-8 2-12" stroke="#67e8f9" strokeWidth={0.6} strokeLinecap="round" />
          <path d="M156 42c3-3 5-7 5-11" stroke="#67e8f9" strokeWidth={0.6} strokeLinecap="round" />
          <path d="M158 44c2-2 4-5 4-8" stroke="#67e8f9" strokeWidth={0.4} strokeLinecap="round" />
        </g>
      </g>
      {/* Vaquita */}
      <g>
        <path
          d="M224 46c1-5 6-10 12-10s10 2 14 4c4 2 7 3 10 2 2-1 3 1 3 3s-2 5-5 7c-4 2-10 2-16 1-6-2-10 0-14 2-4 2-6 2-8 0-2-1-1-4 4-9z"
          fill="#f97316" fillOpacity={0.15} stroke="#f97316" strokeWidth={0.9}
        />
        <circle cx={228} cy={42} r={2.5} fill="none" stroke="#1e293b" strokeWidth={1} opacity={0.6} />
        <path d="M224 48c-1 1-1 3 0 4" stroke="#1e293b" strokeWidth={0.8} opacity={0.5} />
      </g>
      <Ann x1={43} y1={39} tx={50} ty={22} label="Triangular dorsal" color="#fb923c" />
      <Ann x1={18} y1={44} tx={10} ty={28} label="Blunt head, no beak" color="#fb923c" />
      <Ann x1={38} y1={52} tx={38} ty={72} label="Small (1.5 m)" color="#fb923c" anchor="middle" />
      <Ann x1={140} y1={48} tx={130} ty={72} label="White flank patches" color="#e2e8f0" />
      <Ann x1={156} y1={36} tx={166} ty={20} label="Rooster-tail spray" color="#67e8f9" />
      <Ann x1={228} y1={42} tx={216} ty={26} label="Dark eye rings" color="#fb923c" anchor="end" />
      <Ann x1={224} y1={50} tx={218} ty={72} label="Dark lip patches" color="#fb923c" />
      <Ann x1={252} y1={50} tx={262} ty={72} label="< 10 remaining" color="#fca5a5" />
      <Sep x={104} y1={15} y2={102} />
      <Sep x={210} y1={15} y2={102} />
      <ColLabel x={45} y={90} text="Harbour Porpoise" color="#f97316" />
      <ColLabel x={152} y={90} text="Dall's Porpoise" color="#f97316" />
      <ColLabel x={260} y={90} text="Vaquita" color="#f97316" />
    </svg>
  );
}

/** Map from imgKey -> React component for use in GuidanceCard. */
export const STAGE_SVG_MAP: Record<string, React.ComponentType<P>> = {
  stage_start_comparison: StageStartComparison,
  stage_whale_kind_comparison: StageWhaleKindComparison,
  stage_baleen_species: StageBaleenSpecies,
  stage_toothed_species: StageToothedSpecies,
  stage_dolphin_species: StageDolphinSpecies,
  stage_porpoise_species: StagePorpoiseSpecies,
};
