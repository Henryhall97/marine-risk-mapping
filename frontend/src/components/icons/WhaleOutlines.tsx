"use client";

/**
 * Minimalist outline silhouettes for 8 whale species.
 * Used as decorative watermarks on species tiles.
 * Each SVG is hand-tuned to capture the species' most recognisable profile.
 */

interface OutlineProps {
  className?: string;
}

/* ── North Atlantic Right Whale ──
   Distinctive: no dorsal fin, broad arched mouth, callosities on head,
   stocky rotund body, V-shaped blow */
export function RightWhaleOutline({ className = "" }: OutlineProps) {
  return (
    <svg viewBox="0 0 200 100" fill="none" className={className}>
      <path
        d="M10 58 C18 56 24 50 34 44 C44 38 52 32 64 30 C76 28 88 28 100 30
           C112 32 124 34 136 32 C148 30 156 28 164 30 C172 32 178 38 184 42
           C188 44 192 48 194 52 C192 54 188 56 182 58
           C176 60 168 62 160 62 C152 62 148 58 144 56
           C140 54 136 56 132 60 C128 64 122 68 116 68
           C110 68 100 66 90 64 C80 62 68 60 56 60
           C44 60 28 62 18 62 C14 62 10 60 10 58 Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Callosity patches on head */}
      <circle cx="30" cy="40" r="2.5" stroke="currentColor" strokeWidth="1" />
      <circle cx="22" cy="46" r="1.5" stroke="currentColor" strokeWidth="1" />
      {/* Eye */}
      <circle cx="42" cy="42" r="1.2" fill="currentColor" opacity="0.6" />
      {/* Pectoral fin */}
      <path
        d="M80 62 C84 70 90 74 96 72 C92 68 86 64 82 62"
        stroke="currentColor"
        strokeWidth="1.2"
      />
      {/* Fluke */}
      <path
        d="M10 58 C6 52 2 46 4 40 M10 58 C6 64 2 70 4 76"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* ── Humpback Whale ──
   Distinctive: extremely long pectoral fins, knobby head (tubercles),
   small dorsal fin with hump, broad fluke with scalloped trailing edge */
export function HumpbackOutline({ className = "" }: OutlineProps) {
  return (
    <svg viewBox="0 0 200 100" fill="none" className={className}>
      <path
        d="M12 54 C20 52 28 48 38 44 C48 40 56 36 68 34 C80 32 92 32 104 34
           C116 36 126 38 138 36 C146 34 152 32 158 34 C164 36 170 40 176 44
           C182 48 186 52 190 54 C186 56 180 58 174 58
           C168 58 164 56 158 58 C154 60 150 58 146 56
           C140 52 136 50 134 52 C132 54 130 56 126 58
           C120 62 110 64 98 64 C86 64 74 62 62 60
           C50 58 36 56 24 56 C18 56 14 56 12 54 Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Tubercles on head */}
      <circle cx="174" cy="42" r="1.2" stroke="currentColor" strokeWidth="0.8" />
      <circle cx="180" cy="46" r="1.2" stroke="currentColor" strokeWidth="0.8" />
      <circle cx="186" cy="50" r="1.2" stroke="currentColor" strokeWidth="0.8" />
      {/* Eye */}
      <circle cx="166" cy="44" r="1.2" fill="currentColor" opacity="0.6" />
      {/* Long pectoral fin */}
      <path
        d="M110 62 C116 72 126 80 140 82 C146 82 148 78 144 74
           C138 70 126 66 116 62"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      {/* Dorsal hump */}
      <path
        d="M130 36 C132 30 136 28 138 30"
        stroke="currentColor"
        strokeWidth="1.2"
      />
      {/* Fluke */}
      <path
        d="M12 54 C8 48 4 42 2 36 M12 54 C8 60 4 66 2 72"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* ── Fin Whale ──
   Distinctive: sleek and streamlined, prominent dorsal fin set far back,
   asymmetric jaw colouring, second-largest animal ever */
export function FinWhaleOutline({ className = "" }: OutlineProps) {
  return (
    <svg viewBox="0 0 200 100" fill="none" className={className}>
      <path
        d="M6 52 C14 50 26 48 40 46 C54 44 70 42 88 40
           C106 38 124 38 140 40 C156 42 168 44 178 46
           C184 48 190 50 196 52
           C190 54 184 56 178 56 C168 56 156 56 140 56
           C124 56 106 56 88 56 C70 56 54 56 40 56
           C26 56 14 54 6 52 Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Eye */}
      <circle cx="182" cy="48" r="1" fill="currentColor" opacity="0.6" />
      {/* Tall dorsal fin (set far back) */}
      <path
        d="M60 42 C62 32 66 28 70 30 C68 34 64 40 62 44"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
      {/* Pectoral fin */}
      <path
        d="M140 56 C144 62 150 66 156 64 C152 60 146 56 142 56"
        stroke="currentColor"
        strokeWidth="1.1"
      />
      {/* Fluke */}
      <path
        d="M6 52 C3 46 1 40 2 34 M6 52 C3 58 1 64 2 70"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      {/* Ventral grooves hint */}
      <path
        d="M120 56 L118 60 M130 56 L128 60 M140 56 L138 60"
        stroke="currentColor"
        strokeWidth="0.6"
        opacity="0.4"
      />
    </svg>
  );
}

/* ── Blue Whale ──
   Distinctive: enormous and elongated, tiny dorsal fin far back,
   mottled blue-grey, U-shaped head, massive size */
export function BlueWhaleOutline({ className = "" }: OutlineProps) {
  return (
    <svg viewBox="0 0 200 100" fill="none" className={className}>
      <path
        d="M4 50 C12 48 24 46 40 44 C56 42 74 40 94 38
           C114 36 132 36 150 38 C164 40 176 42 186 46
           C192 48 196 50 198 52
           C196 54 192 56 186 56 C176 56 164 56 150 56
           C132 56 114 56 94 56 C74 56 56 56 40 56
           C24 56 12 54 4 50 Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Eye */}
      <circle cx="188" cy="48" r="1" fill="currentColor" opacity="0.6" />
      {/* Tiny dorsal fin */}
      <path
        d="M42 40 C43 36 45 34 47 36"
        stroke="currentColor"
        strokeWidth="1.2"
      />
      {/* U-shaped head (top view hint via rostral ridge) */}
      <path
        d="M192 48 C196 46 198 48 198 52"
        stroke="currentColor"
        strokeWidth="1"
        opacity="0.5"
      />
      {/* Pectoral fin */}
      <path
        d="M130 56 C134 64 140 68 146 66 C142 62 136 58 132 56"
        stroke="currentColor"
        strokeWidth="1.1"
      />
      {/* Fluke */}
      <path
        d="M4 50 C2 44 0 38 2 32 M4 50 C2 56 0 62 2 68"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      {/* Mottling pattern hint */}
      <circle cx="100" cy="46" r="3" stroke="currentColor" strokeWidth="0.4" opacity="0.2" />
      <circle cx="120" cy="44" r="2" stroke="currentColor" strokeWidth="0.4" opacity="0.2" />
      <circle cx="80" cy="48" r="2.5" stroke="currentColor" strokeWidth="0.4" opacity="0.2" />
    </svg>
  );
}

/* ── Sei Whale ──
   Distinctive: single prominent rostral ridge, tall sickle dorsal fin,
   uniform dark grey, very fast swimmer */
export function SeiWhaleOutline({ className = "" }: OutlineProps) {
  return (
    <svg viewBox="0 0 200 100" fill="none" className={className}>
      <path
        d="M8 50 C16 48 28 46 44 44 C60 42 78 40 96 38
           C114 36 130 36 146 38 C160 40 172 44 182 46
           C188 48 194 50 196 52
           C194 54 188 56 182 56 C172 56 160 56 146 56
           C130 56 114 56 96 56 C78 56 60 56 44 56
           C28 56 16 54 8 50 Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Eye */}
      <circle cx="184" cy="48" r="1" fill="currentColor" opacity="0.6" />
      {/* Tall sickle dorsal fin */}
      <path
        d="M68 38 C70 28 74 24 78 28 C76 32 72 36 70 40"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
      {/* Single rostral ridge */}
      <path
        d="M186 46 C190 44 194 46 196 50"
        stroke="currentColor"
        strokeWidth="0.8"
        opacity="0.5"
      />
      {/* Pectoral fin (small) */}
      <path
        d="M140 56 C142 62 146 64 150 62 C148 58 144 56 142 56"
        stroke="currentColor"
        strokeWidth="1.1"
      />
      {/* Fluke */}
      <path
        d="M8 50 C5 44 2 38 3 32 M8 50 C5 56 2 62 3 68"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* ── Sperm Whale ──
   Distinctive: massive box-shaped head (1/3 of body), wrinkled skin,
   low dorsal hump (no true fin), angled blow, small lower jaw */
export function SpermWhaleOutline({ className = "" }: OutlineProps) {
  return (
    <svg viewBox="0 0 200 100" fill="none" className={className}>
      {/* Massive box head + tapered body */}
      <path
        d="M8 52 C16 50 28 48 42 46 C56 44 68 44 80 44
           C92 44 102 44 110 44 C118 44 124 42 130 40
           C140 36 152 32 164 32 C172 32 180 36 186 40
           C190 42 192 46 194 50
           C192 52 188 56 182 58 C174 60 166 60 160 58
           C154 56 148 56 140 56 C130 56 118 56 110 56
           C102 56 92 56 80 56 C68 56 56 56 42 56
           C28 56 16 54 8 52 Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Box head shape */}
      <path
        d="M164 32 C168 28 178 26 188 30 C194 34 196 42 194 50"
        stroke="currentColor"
        strokeWidth="1.2"
        opacity="0.5"
      />
      {/* Small lower jaw */}
      <path
        d="M166 58 C172 60 180 60 186 58 C190 56 192 54 194 50"
        stroke="currentColor"
        strokeWidth="1"
        opacity="0.4"
      />
      {/* Eye (set low and far back from head) */}
      <circle cx="162" cy="46" r="1" fill="currentColor" opacity="0.6" />
      {/* Dorsal hump (no real fin) */}
      <path
        d="M60 44 C61 40 63 39 65 41"
        stroke="currentColor"
        strokeWidth="1.1"
      />
      {/* Wrinkle texture hint */}
      <path
        d="M90 44 C92 43 94 44 M100 44 C102 43 104 44 M110 44 C112 43 114 44"
        stroke="currentColor"
        strokeWidth="0.5"
        opacity="0.3"
      />
      {/* Fluke */}
      <path
        d="M8 52 C5 46 2 40 3 34 M8 52 C5 58 2 64 3 70"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* ── Minke Whale ──
   Distinctive: small and sleek, pointed snout, white flipper bands,
   prominent curved dorsal fin, smallest baleen whale */
export function MinkeWhaleOutline({ className = "" }: OutlineProps) {
  return (
    <svg viewBox="0 0 200 100" fill="none" className={className}>
      <path
        d="M10 50 C18 48 30 46 46 44 C62 42 78 40 96 38
           C114 36 130 36 146 38 C160 40 172 42 182 46
           C190 48 196 50 198 52
           C196 54 190 56 182 56 C172 56 160 56 146 56
           C130 56 114 56 96 56 C78 56 62 56 46 56
           C30 56 18 54 10 50 Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Pointed snout */}
      <path
        d="M190 48 C194 48 198 50 198 52"
        stroke="currentColor"
        strokeWidth="1"
      />
      {/* Eye */}
      <circle cx="182" cy="48" r="1" fill="currentColor" opacity="0.6" />
      {/* Prominent curved dorsal fin */}
      <path
        d="M72 38 C74 30 78 26 82 30 C80 34 76 38 74 40"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
      {/* Pectoral fin with white band hint */}
      <path
        d="M140 56 C144 64 150 68 156 66 C152 62 146 58 142 56"
        stroke="currentColor"
        strokeWidth="1.1"
      />
      {/* White flipper band (double stroke) */}
      <path
        d="M144 62 C148 64 152 64 154 62"
        stroke="currentColor"
        strokeWidth="1.8"
        opacity="0.3"
      />
      {/* Fluke */}
      <path
        d="M10 50 C7 44 4 38 5 32 M10 50 C7 56 4 62 5 68"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* ── Killer Whale (Orca) ──
   Distinctive: tall dorsal fin (male), eye patch, saddle patch,
   black and white colouring, robust build */
export function KillerWhaleOutline({ className = "" }: OutlineProps) {
  return (
    <svg viewBox="0 0 200 100" fill="none" className={className}>
      <path
        d="M10 52 C18 50 30 48 44 46 C58 44 72 42 88 40
           C104 38 118 38 132 40 C146 42 158 44 168 46
           C176 48 184 50 190 52
           C186 54 180 56 172 58 C164 60 156 60 148 58
           C138 56 128 56 118 56 C104 56 88 56 72 56
           C58 56 44 56 30 56 C20 56 14 54 10 52 Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Tall dorsal fin (male orca signature) */}
      <path
        d="M100 38 C102 20 106 12 110 14 C108 22 104 32 102 40"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      {/* Eye patch */}
      <ellipse
        cx="174"
        cy="48"
        rx="4"
        ry="2.5"
        stroke="currentColor"
        strokeWidth="1.2"
      />
      <circle cx="175" cy="48" r="0.8" fill="currentColor" opacity="0.6" />
      {/* Saddle patch behind dorsal */}
      <path
        d="M88 42 C84 40 80 42 82 46 C86 44 90 44 88 42"
        stroke="currentColor"
        strokeWidth="0.8"
        opacity="0.4"
      />
      {/* Pectoral fin (large, paddle-shaped) */}
      <path
        d="M132 56 C138 66 146 72 154 70 C150 64 142 58 136 56"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      {/* Fluke */}
      <path
        d="M10 52 C6 46 3 40 4 34 M10 52 C6 58 3 64 4 70"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* ── Lookup map for species tile integration ── */

export const WHALE_OUTLINES: Record<string, React.FC<OutlineProps>> = {
  "North Atlantic Right Whale": RightWhaleOutline,
  "Humpback Whale": HumpbackOutline,
  "Fin Whale": FinWhaleOutline,
  "Blue Whale": BlueWhaleOutline,
  "Sei Whale": SeiWhaleOutline,
  "Sperm Whale": SpermWhaleOutline,
  "Minke Whale": MinkeWhaleOutline,
  "Killer Whale": KillerWhaleOutline,
};
