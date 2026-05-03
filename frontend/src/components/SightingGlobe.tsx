"use client";

import { useRef, useMemo, useEffect, useState, useCallback } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import * as THREE from "three";
import Image from "next/image";

/* ═══════════════════════════════════════════════════════════════
   SightingGlobe — Celebratory 3-D globe showcasing community
   cetacean sightings with species-colored pins, animated tours,
   particle celebration bursts, and a live species ticker.
   ═══════════════════════════════════════════════════════════════ */

// ── Types ────────────────────────────────────────────────────

export interface GlobeSighting {
  id: string;
  lat: number;
  lon: number;
  species: string;
  submitter_name: string | null;
  created_at: string;
  group_size?: number | null;
  behavior?: string | null;
  calf_present?: boolean | null;
  verification_status?: string;
  risk_category?: string | null;
  has_photo?: boolean;
  has_audio?: boolean;
}

interface TourStop {
  position: THREE.Vector3;
  lookAt: THREE.Vector3;
  camera: THREE.Vector3;
  caption: string;
  species: string;
  color: string;
  isRare: boolean;
  sighting: GlobeSighting;
}

// ── Species color palette (IUCN conservation-status inspired) ─

const SPECIES_COLORS: Record<string, string> = {
  /* Critically Endangered — vivid red */
  right_whale: "#ef4444",
  vaquita: "#ef4444",
  rices_whale: "#ef4444",
  /* Endangered — warm orange */
  blue_whale: "#f97316",
  sei_whale: "#f97316",
  southern_right_whale: "#f97316",
  /* Vulnerable — amber */
  fin_whale: "#eab308",
  sperm_whale: "#eab308",
  hectors_dolphin: "#eab308",
  /* Least Concern — emerald */
  humpback_whale: "#22c55e",
  humpback: "#22c55e",
  minke_whale: "#22c55e",
  gray_whale: "#22c55e",
  bowhead: "#22c55e",
  brydes_whale: "#22c55e",
  /* Dolphins — cyan */
  common_dolphin: "#06b6d4",
  bottlenose_dolphin: "#06b6d4",
  rissos_dolphin: "#06b6d4",
  spotted_dolphin: "#06b6d4",
  striped_dolphin: "#06b6d4",
  whitesided_dolphin: "#06b6d4",
  /* Porpoises — teal */
  harbor_porpoise: "#14b8a6",
  dalls_porpoise: "#14b8a6",
  /* Charismatic — purple / lavender */
  killer_whale: "#a855f7",
  orca: "#a855f7",
  beluga: "#e0e7ff",
  narwhal: "#c4b5fd",
  pilot_whale: "#8b5cf6",
  beaked_whale: "#7c8db5",
};
const DEFAULT_PIN_COLOR = "#64748b";

const RARE_SPECIES = new Set([
  "right_whale",
  "vaquita",
  "rices_whale",
  "blue_whale",
  "sei_whale",
  "southern_right_whale",
]);

/* Smooth silhouette icons in /whale_detailed_smooth_icons/ */
const SMOOTH_ICON_MAP: Record<string, string> = {
  humpback_whale: "humpback_whale.png",
  humpback: "humpback_whale.png",
  right_whale: "right_whale.png",
  blue_whale: "blue_whale.png",
  fin_whale: "fin_whale.png",
  sei_whale: "sei_whale.png",
  minke_whale: "minke_whale.png",
  sperm_whale: "sperm_whale.png",
  killer_whale: "killer_whale_orca.png",
  orca: "killer_whale_orca.png",
};

const SPECIES_LABELS: Record<string, string> = {
  humpback_whale: "Humpback Whale",
  humpback: "Humpback Whale",
  right_whale: "North Atlantic Right Whale",
  southern_right_whale: "Southern Right Whale",
  fin_whale: "Fin Whale",
  blue_whale: "Blue Whale",
  minke_whale: "Minke Whale",
  sei_whale: "Sei Whale",
  bowhead: "Bowhead Whale",
  brydes_whale: "Bryde's Whale",
  rices_whale: "Rice's Whale",
  gray_whale: "Gray Whale",
  sperm_whale: "Sperm Whale",
  killer_whale: "Orca",
  orca: "Orca",
  beaked_whale: "Beaked Whale",
  beluga: "Beluga Whale",
  narwhal: "Narwhal",
  pilot_whale: "Pilot Whale",
  vaquita: "Vaquita",
  bottlenose_dolphin: "Bottlenose Dolphin",
  common_dolphin: "Common Dolphin",
  rissos_dolphin: "Risso's Dolphin",
  spotted_dolphin: "Spotted Dolphin",
  striped_dolphin: "Striped Dolphin",
  whitesided_dolphin: "White-sided Dolphin",
  hectors_dolphin: "Hector's Dolphin",
  harbor_porpoise: "Harbor Porpoise",
  dalls_porpoise: "Dall's Porpoise",
  other_cetacean: "Cetacean",
  unid_cetacean: "Cetacean",
};

const BEHAVIOR_LABELS: Record<string, string> = {
  feeding: "Feeding",
  traveling: "Traveling",
  socializing: "Socializing",
  resting: "Resting",
  breaching: "Breaching",
  diving: "Deep diving",
  spy_hopping: "Spy-hopping",
  logging: "Logging",
  milling: "Milling",
  unknown: "Observed",
};

const RISK_STYLES: Record<
  string,
  { bg: string; text: string; label: string; dot: string }
> = {
  critical: {
    bg: "bg-red-500/15",
    text: "text-red-400",
    label: "Critical Risk Zone",
    dot: "bg-red-500",
  },
  high: {
    bg: "bg-orange-500/15",
    text: "text-orange-400",
    label: "High Risk Zone",
    dot: "bg-orange-500",
  },
  medium: {
    bg: "bg-yellow-500/15",
    text: "text-yellow-400",
    label: "Moderate Risk",
    dot: "bg-yellow-500",
  },
  low: {
    bg: "bg-emerald-500/15",
    text: "text-emerald-400",
    label: "Low Risk",
    dot: "bg-emerald-500",
  },
};

const IUCN_TAG: Record<string, { label: string; cls: string }> = {
  right_whale: { label: "CR", cls: "bg-red-500/20 text-red-400 ring-red-500/30" },
  vaquita: { label: "CR", cls: "bg-red-500/20 text-red-400 ring-red-500/30" },
  rices_whale: { label: "CR", cls: "bg-red-500/20 text-red-400 ring-red-500/30" },
  blue_whale: { label: "EN", cls: "bg-orange-500/20 text-orange-400 ring-orange-500/30" },
  sei_whale: { label: "EN", cls: "bg-orange-500/20 text-orange-400 ring-orange-500/30" },
  southern_right_whale: { label: "EN", cls: "bg-orange-500/20 text-orange-400 ring-orange-500/30" },
  fin_whale: { label: "VU", cls: "bg-yellow-500/20 text-yellow-400 ring-yellow-500/30" },
  sperm_whale: { label: "VU", cls: "bg-yellow-500/20 text-yellow-400 ring-yellow-500/30" },
};

// ── Geometry constants ───────────────────────────────────────

const DEG2RAD = Math.PI / 180;
const GLOBE_RADIUS = 2;
const ATMOSPHERE_RADIUS = 2.12;
const ORBIT_RADIUS = 5.5;
const ZOOM_RADIUS = 3.2;
const IDLE_SPIN_SPEED = 0.06;
const TOUR_DWELL = 5.5;
const TOUR_TRANSITION = 2.5;
const PIN_HEIGHT = 0.2;
const PIN_RADIUS = 0.018;
const PULSE_RADIUS = 0.09;
const BURST_COUNT = 55;

// ── Geographic place labels ──────────────────────────────────

interface PlaceLabel {
  name: string;
  lat: number;
  lon: number;
  kind: "ocean" | "sea" | "place" | "region";
}

const PLACE_LABELS: PlaceLabel[] = [
  /* Major oceans */
  { name: "North Pacific", lat: 30, lon: -160, kind: "ocean" },
  { name: "South Pacific", lat: -25, lon: -140, kind: "ocean" },
  { name: "North Atlantic", lat: 35, lon: -40, kind: "ocean" },
  { name: "South Atlantic", lat: -20, lon: -20, kind: "ocean" },
  { name: "Indian Ocean", lat: -15, lon: 75, kind: "ocean" },
  { name: "Southern Ocean", lat: -62, lon: 0, kind: "ocean" },
  { name: "Arctic Ocean", lat: 80, lon: 0, kind: "ocean" },
  /* Whale-relevant seas & bays */
  { name: "Gulf of Maine", lat: 43.5, lon: -68, kind: "sea" },
  { name: "Bering Sea", lat: 57, lon: -175, kind: "sea" },
  { name: "Gulf of Mexico", lat: 25, lon: -90, kind: "sea" },
  { name: "Caribbean Sea", lat: 15, lon: -75, kind: "sea" },
  { name: "Mediterranean", lat: 36, lon: 18, kind: "sea" },
  { name: "Sea of Cortez", lat: 27, lon: -111, kind: "sea" },
  { name: "Coral Sea", lat: -18, lon: 155, kind: "sea" },
  { name: "Norwegian Sea", lat: 67, lon: 3, kind: "sea" },
  { name: "Tasman Sea", lat: -38, lon: 163, kind: "sea" },
  /* Whale-watching hotspots & landmarks */
  { name: "Monterey Bay", lat: 36.8, lon: -122, kind: "place" },
  { name: "Cape Cod", lat: 41.7, lon: -70, kind: "place" },
  { name: "Stellwagen Bank", lat: 42.35, lon: -70.3, kind: "place" },
  { name: "Hawaii", lat: 20.5, lon: -157, kind: "place" },
  { name: "Azores", lat: 38.7, lon: -27.2, kind: "place" },
  { name: "Iceland", lat: 65, lon: -18, kind: "place" },
  { name: "Tonga", lat: -20, lon: -175, kind: "place" },
  { name: "Sri Lanka", lat: 7, lon: 80.5, kind: "place" },
  { name: "Baja California", lat: 28, lon: -114, kind: "place" },
  { name: "Patagonia", lat: -45, lon: -67, kind: "place" },
  { name: "Antarctica", lat: -75, lon: 0, kind: "region" },
  { name: "Alaska", lat: 63, lon: -152, kind: "region" },
  { name: "Svalbard", lat: 78, lon: 16, kind: "region" },
  { name: "South Georgia", lat: -54.5, lon: -36, kind: "place" },
  { name: "Great Barrier Reef", lat: -17, lon: 147, kind: "place" },
];

// ── Helpers ──────────────────────────────────────────────────

function latLonToVec3(lat: number, lon: number, r: number): THREE.Vector3 {
  const phi = (90 - lat) * DEG2RAD;
  const theta = (lon + 180) * DEG2RAD;
  return new THREE.Vector3(
    -r * Math.sin(phi) * Math.cos(theta),
    r * Math.cos(phi),
    r * Math.sin(phi) * Math.sin(theta),
  );
}

function getSpeciesColor(sp: string): string {
  return SPECIES_COLORS[sp] ?? DEFAULT_PIN_COLOR;
}

function getSpeciesLabel(sp: string): string {
  return (
    SPECIES_LABELS[sp] ??
    sp
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

function getBehaviorLabel(b: string | null | undefined): string | null {
  if (!b) return null;
  return (
    BEHAVIOR_LABELS[b] ??
    b
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  return `${weeks}w ago`;
}

// ══════════════════════════════════════════════════════════════
// ── 3-D Scene Components ─────────────────────────────────────
// ══════════════════════════════════════════════════════════════

// ── Globe (procedural dark-ocean shader) ─────────────────────

function Globe() {
  const material = useMemo(() => {
    return new THREE.ShaderMaterial({
      uniforms: { uTime: { value: 0 } },
      vertexShader: /* glsl */ `
        varying vec3 vNormal;
        varying vec3 vPosition;
        varying vec2 vUv;
        void main() {
          vNormal = normalize(normalMatrix * normal);
          vPosition = (modelViewMatrix * vec4(position, 1.0)).xyz;
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix
                        * vec4(position, 1.0);
        }
      `,
      fragmentShader: /* glsl */ `
        varying vec3 vNormal;
        varying vec3 vPosition;
        varying vec2 vUv;
        uniform float uTime;

        float hash(vec2 p) {
          return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
        }
        float noise(vec2 p) {
          vec2 i = floor(p);
          vec2 f = fract(p);
          f = f * f * (3.0 - 2.0 * f);
          float a = hash(i);
          float b = hash(i + vec2(1.0, 0.0));
          float c = hash(i + vec2(0.0, 1.0));
          float d = hash(i + vec2(1.0, 1.0));
          return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
        }
        float fbm(vec2 p) {
          float v = 0.0; float a = 0.5;
          for (int i = 0; i < 5; i++) {
            v += a * noise(p); p *= 2.0; a *= 0.5;
          }
          return v;
        }
        void main() {
          vec2 ll = vUv * vec2(10.0, 5.0);
          float n = fbm(ll + vec2(0.3, -0.7));

          vec3 deepOcean    = vec3(0.02, 0.06, 0.14);
          vec3 shallowOcean = vec3(0.04, 0.12, 0.22);
          vec3 land          = vec3(0.08, 0.14, 0.08);
          vec3 highland      = vec3(0.12, 0.18, 0.10);

          float lt = 0.52;
          vec3 color;
          if (n < lt - 0.05)
            color = mix(deepOcean, shallowOcean,
                        smoothstep(0.2, 0.47, n));
          else if (n < lt)
            color = mix(shallowOcean, land,
                        smoothstep(lt - 0.05, lt, n));
          else
            color = mix(land, highland,
                        smoothstep(lt, 0.7, n));

          /* subtle grid */
          float gLat = abs(fract(vUv.y * 18.0) - 0.5);
          float gLon = abs(fract(vUv.x * 36.0) - 0.5);
          float grid = smoothstep(0.48, 0.5, gLat)
                     + smoothstep(0.48, 0.5, gLon);
          color += vec3(0.015, 0.03, 0.05) * grid * 0.4;

          /* fresnel edge glow */
          vec3 viewDir = normalize(-vPosition);
          float f = 1.0 - max(dot(viewDir, vNormal), 0.0);
          f = pow(f, 3.0);
          color += vec3(0.05, 0.15, 0.3) * f;

          gl_FragColor = vec4(color, 1.0);
        }
      `,
    });
  }, []);

  const atmosphereMaterial = useMemo(() => {
    return new THREE.ShaderMaterial({
      vertexShader: /* glsl */ `
        varying vec3 vNormal; varying vec3 vPosition;
        void main() {
          vNormal = normalize(normalMatrix * normal);
          vPosition = (modelViewMatrix * vec4(position, 1.0)).xyz;
          gl_Position = projectionMatrix * modelViewMatrix
                        * vec4(position, 1.0);
        }
      `,
      fragmentShader: /* glsl */ `
        varying vec3 vNormal; varying vec3 vPosition;
        void main() {
          vec3 v = normalize(-vPosition);
          float f = 1.0 - max(dot(v, vNormal), 0.0);
          f = pow(f, 3.5);
          gl_FragColor = vec4(vec3(0.15, 0.45, 0.8), f * 0.35);
        }
      `,
      transparent: true,
      side: THREE.BackSide,
      depthWrite: false,
    });
  }, []);

  useFrame((_, dt) => {
    material.uniforms.uTime.value += dt;
  });

  return (
    <>
      <mesh material={material}>
        <sphereGeometry args={[GLOBE_RADIUS, 64, 64]} />
      </mesh>
      <mesh material={atmosphereMaterial}>
        <sphereGeometry args={[ATMOSPHERE_RADIUS, 64, 64]} />
      </mesh>
    </>
  );
}

// ── Star field ───────────────────────────────────────────────

function StarField() {
  const [positions, sizes] = useMemo(() => {
    const count = 900;
    const pos = new Float32Array(count * 3);
    const sz = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 28 + Math.random() * 22;
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      pos[i * 3 + 2] = r * Math.cos(phi);
      sz[i] = 0.4 + Math.random() * 1.6;
    }
    return [pos, sz];
  }, []);

  return (
    <points>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
          count={positions.length / 3}
          itemSize={3}
        />
        <bufferAttribute
          attach="attributes-size"
          args={[sizes, 1]}
          count={sizes.length}
          itemSize={1}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.08}
        color="#a5b4fc"
        transparent
        opacity={0.4}
        sizeAttenuation
      />
    </points>
  );
}

// ── Species-colored sighting pins ────────────────────────────

function SightingPins({
  stops,
  activeIndex,
}: {
  stops: TourStop[];
  activeIndex: number;
}) {
  const clockRef = useRef(0);
  useFrame((_, dt) => {
    clockRef.current += dt;
  });

  return (
    <group>
      {stops.map((stop, i) => {
        const isActive = i === activeIndex;
        const dir = stop.position.clone().normalize();
        const base = stop.position;
        const tip = base
          .clone()
          .add(dir.clone().multiplyScalar(PIN_HEIGHT));

        return (
          <group key={stop.sighting.id}>
            <SpeciesPin
              base={base}
              tip={tip}
              color={stop.color}
              active={isActive}
            />
            {isActive && (
              <GlowBeam position={tip} normal={dir} color={stop.color} />
            )}
            <PulseRing
              position={base}
              normal={dir}
              color={stop.color}
              active={isActive}
              clockRef={clockRef}
            />
          </group>
        );
      })}
    </group>
  );
}

function SpeciesPin({
  base,
  tip,
  color,
  active,
}: {
  base: THREE.Vector3;
  tip: THREE.Vector3;
  color: string;
  active: boolean;
}) {
  const dir = tip.clone().sub(base);
  const mid = base.clone().add(dir.clone().multiplyScalar(0.5));
  const length = dir.length();

  const quaternion = useMemo(() => {
    const q = new THREE.Quaternion();
    q.setFromUnitVectors(
      new THREE.Vector3(0, 1, 0),
      dir.clone().normalize(),
    );
    return q;
  }, [dir]);

  return (
    <group>
      {/* Stem */}
      <mesh position={mid} quaternion={quaternion}>
        <cylinderGeometry
          args={[PIN_RADIUS * 0.4, PIN_RADIUS * 0.9, length, 6]}
        />
        <meshBasicMaterial
          color={active ? color : "#3f4f65"}
          transparent
          opacity={active ? 0.9 : 0.35}
        />
      </mesh>
      {/* Head — species-coloured sphere */}
      <mesh position={tip}>
        <sphereGeometry
          args={[active ? PIN_RADIUS * 3.5 : PIN_RADIUS * 2, 16, 16]}
        />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={active ? 1 : 0.55}
        />
      </mesh>
      {/* Inner glow core (additive) — active only */}
      {active && (
        <mesh position={tip}>
          <sphereGeometry args={[PIN_RADIUS * 5, 16, 16]} />
          <meshBasicMaterial
            color={color}
            transparent
            opacity={0.15}
            depthWrite={false}
            blending={THREE.AdditiveBlending}
          />
        </mesh>
      )}
    </group>
  );
}

function GlowBeam({
  position,
  normal,
  color,
}: {
  position: THREE.Vector3;
  normal: THREE.Vector3;
  color: string;
}) {
  const beamLength = 0.5;
  const beamMid = position
    .clone()
    .add(normal.clone().multiplyScalar(beamLength / 2));

  const quaternion = useMemo(() => {
    const q = new THREE.Quaternion();
    q.setFromUnitVectors(new THREE.Vector3(0, 1, 0), normal);
    return q;
  }, [normal]);

  return (
    <mesh position={beamMid} quaternion={quaternion}>
      <cylinderGeometry
        args={[0.001, PIN_RADIUS * 2.5, beamLength, 8]}
      />
      <meshBasicMaterial
        color={color}
        transparent
        opacity={0.18}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </mesh>
  );
}

function PulseRing({
  position,
  normal,
  color,
  active,
  clockRef,
}: {
  position: THREE.Vector3;
  normal: THREE.Vector3;
  color: string;
  active: boolean;
  clockRef: React.MutableRefObject<number>;
}) {
  const ringRef = useRef<THREE.Mesh>(null);

  const quaternion = useMemo(() => {
    const q = new THREE.Quaternion();
    q.setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal);
    return q;
  }, [normal]);

  useFrame(() => {
    if (!ringRef.current || !active) {
      if (ringRef.current) ringRef.current.visible = false;
      return;
    }
    ringRef.current.visible = true;
    const t = (clockRef.current % 1.8) / 1.8;
    const scale = 1 + t * 4;
    ringRef.current.scale.set(scale, scale, 1);
    (ringRef.current.material as THREE.MeshBasicMaterial).opacity =
      (1 - t) * 0.5;
  });

  return (
    <mesh ref={ringRef} position={position} quaternion={quaternion}>
      <ringGeometry args={[PULSE_RADIUS * 0.8, PULSE_RADIUS, 32]} />
      <meshBasicMaterial
        color={color}
        transparent
        side={THREE.DoubleSide}
        depthWrite={false}
      />
    </mesh>
  );
}

// ── Celebration burst particles ──────────────────────────────

function CelebrationBurst({
  stops,
  activeIndex,
  phase,
}: {
  stops: TourStop[];
  activeIndex: number;
  phase: string;
}) {
  const pointsRef = useRef<THREE.Points>(null);
  const dataRef = useRef({
    positions: new Float32Array(BURST_COUNT * 3),
    velocities: Array.from(
      { length: BURST_COUNT },
      () => new THREE.Vector3(),
    ),
    life: 10,
    lastIndex: -1,
  });

  useFrame((_, dt) => {
    if (!pointsRef.current) return;
    const d = dataRef.current;
    const mat = pointsRef.current.material as THREE.PointsMaterial;

    /* Trigger new burst when dwelling begins at a new stop */
    if (
      phase === "dwelling" &&
      activeIndex !== d.lastIndex &&
      activeIndex >= 0 &&
      stops[activeIndex]
    ) {
      d.lastIndex = activeIndex;
      d.life = 0;
      const pos = stops[activeIndex].position;
      const norm = pos.clone().normalize();

      for (let i = 0; i < BURST_COUNT; i++) {
        d.positions[i * 3] = pos.x;
        d.positions[i * 3 + 1] = pos.y;
        d.positions[i * 3 + 2] = pos.z;

        const v = new THREE.Vector3(
          Math.random() - 0.5,
          Math.random() - 0.5,
          Math.random() - 0.5,
        ).normalize();
        v.add(norm.clone().multiplyScalar(1.8)).normalize();
        v.multiplyScalar(0.1 + Math.random() * 0.28);
        d.velocities[i] = v;
      }
      mat.color.set(stops[activeIndex].color);
    }

    /* Animate particles */
    d.life += dt;
    if (d.life > 3) {
      mat.opacity = 0;
      return;
    }

    const t = Math.min(d.life / 2.5, 1);
    const decel = 1 - t * 0.65;
    for (let i = 0; i < BURST_COUNT; i++) {
      const v = d.velocities[i];
      d.positions[i * 3] += v.x * dt * decel;
      d.positions[i * 3 + 1] += v.y * dt * decel;
      d.positions[i * 3 + 2] += v.z * dt * decel;
    }

    const posAttr = pointsRef.current.geometry.getAttribute("position");
    posAttr.needsUpdate = true;
    mat.opacity = Math.max(0, 1 - t) * 0.85;
    mat.size = 0.035 * (1 + t * 1.8);
  });

  return (
    <points ref={pointsRef} frustumCulled={false}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[dataRef.current.positions, 3]}
          count={BURST_COUNT}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.035}
        color="#22d3ee"
        transparent
        opacity={0}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

// ── Camera controller (automated tour) ───────────────────────

function CameraController({
  stops,
  activeIndex,
  phase,
}: {
  stops: TourStop[];
  activeIndex: number;
  phase: "idle" | "flying" | "dwelling";
}) {
  const { camera } = useThree();
  const targetPos = useRef(new THREE.Vector3(0, 0, ORBIT_RADIUS));
  const targetLookAt = useRef(new THREE.Vector3(0, 0, 0));
  const currentPos = useRef(new THREE.Vector3(0, 0, ORBIT_RADIUS));
  const currentLookAt = useRef(new THREE.Vector3(0, 0, 0));
  const idleAngle = useRef(0);

  useEffect(() => {
    camera.position.set(0, 1.5, ORBIT_RADIUS);
    camera.lookAt(0, 0, 0);
    currentPos.current.copy(camera.position);
  }, [camera]);

  useFrame((_, dt) => {
    if (phase === "idle" || stops.length === 0) {
      idleAngle.current += IDLE_SPIN_SPEED * dt;
      const a = idleAngle.current;
      targetPos.current.set(
        Math.sin(a) * ORBIT_RADIUS,
        1.2 + Math.sin(a * 0.3) * 0.5,
        Math.cos(a) * ORBIT_RADIUS,
      );
      targetLookAt.current.set(0, 0, 0);
    } else {
      const stop = stops[activeIndex];
      if (stop) {
        targetPos.current.copy(stop.camera);
        targetLookAt.current.copy(stop.lookAt);
      }
    }

    const speed =
      phase === "flying" ? 1.2 : phase === "dwelling" ? 2.5 : 1.5;
    currentPos.current.lerp(
      targetPos.current,
      1 - Math.exp(-speed * dt),
    );
    currentLookAt.current.lerp(
      targetLookAt.current,
      1 - Math.exp(-speed * dt),
    );

    camera.position.copy(currentPos.current);
    camera.lookAt(currentLookAt.current);
  });

  return null;
}

// ── Place labels (geographic orientation) ────────────────────

function PlaceLabels() {
  const { camera } = useThree();
  const groupRef = useRef<THREE.Group>(null);

  /* Pre-compute 3D positions for each label */
  const labels = useMemo(
    () =>
      PLACE_LABELS.map((p) => ({
        ...p,
        pos: latLonToVec3(p.lat, p.lon, GLOBE_RADIUS + 0.015),
      })),
    [],
  );

  /* Per-frame: hide labels on the far side of the globe */
  const visRef = useRef<boolean[]>(labels.map(() => true));
  useFrame(() => {
    const camDir = camera.position.clone().normalize();
    labels.forEach((l, i) => {
      const dot = l.pos.clone().normalize().dot(camDir);
      visRef.current[i] = dot > 0.05;
    });
  });

  const sizeClass: Record<string, string> = {
    ocean: "text-[9px] font-semibold tracking-[0.15em] uppercase",
    sea: "text-[8px] font-medium tracking-[0.08em]",
    place: "text-[7px] font-medium",
    region: "text-[8px] font-semibold tracking-[0.1em] uppercase",
  };

  const colorClass: Record<string, string> = {
    ocean: "text-sky-400/30",
    sea: "text-cyan-300/25",
    place: "text-slate-400/30",
    region: "text-indigo-300/25",
  };

  return (
    <group ref={groupRef}>
      {labels.map((l, i) => (
        <group key={l.name} position={l.pos}>
          <Html
            center
            distanceFactor={5}
            style={{
              pointerEvents: "none",
              userSelect: "none",
              transition: "opacity 0.6s ease",
              opacity: visRef.current[i] ? 1 : 0,
              whiteSpace: "nowrap",
            }}
            zIndexRange={[0, 0]}
          >
            <span
              className={`${sizeClass[l.kind]} ${colorClass[l.kind]}`}
              style={{ textShadow: "0 0 6px rgba(0,0,0,0.8)" }}
            >
              {l.name}
            </span>
          </Html>
        </group>
      ))}
    </group>
  );
}

// ── Scene composition ────────────────────────────────────────

function GlobeScene({
  stops,
  activeIndex,
  phase,
}: {
  stops: TourStop[];
  activeIndex: number;
  phase: "idle" | "flying" | "dwelling";
}) {
  return (
    <>
      <ambientLight intensity={0.3} />
      <directionalLight position={[5, 3, 5]} intensity={0.7} />
      <pointLight position={[-3, -2, -5]} intensity={0.3} color="#6366f1" />
      <StarField />
      <Globe />
      <PlaceLabels />
      <SightingPins stops={stops} activeIndex={activeIndex} />
      <CelebrationBurst
        stops={stops}
        activeIndex={activeIndex}
        phase={phase}
      />
      <CameraController
        stops={stops}
        activeIndex={activeIndex}
        phase={phase}
      />
    </>
  );
}

// ══════════════════════════════════════════════════════════════
// ── Main Exported Component ──────────────────────────────────
// ══════════════════════════════════════════════════════════════

export default function SightingGlobe({
  sightings,
  className = "",
}: {
  sightings: GlobeSighting[];
  className?: string;
}) {
  const [activeIndex, setActiveIndex] = useState(-1);
  const [phase, setPhase] = useState<"idle" | "flying" | "dwelling">("idle");
  const [captionVisible, setCaptionVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cycleIndexRef = useRef(0);

  /* ── Tour stops from sightings with valid coords ── */
  const stops = useMemo<TourStop[]>(() => {
    const valid = sightings
      .filter((s) => s.lat != null && s.lon != null)
      .slice(0, 20);

    return valid.map((s) => {
      const pos = latLonToVec3(s.lat, s.lon, GLOBE_RADIUS);
      const dir = pos.clone().normalize();
      const camPos = dir.clone().multiplyScalar(ZOOM_RADIUS);
      const up = new THREE.Vector3(0, 1, 0);
      const right = new THREE.Vector3().crossVectors(up, dir).normalize();
      camPos.add(right.multiplyScalar(0.4));
      camPos.add(up.clone().multiplyScalar(0.3));

      const species = s.species;
      const who = s.submitter_name ?? "Anonymous";
      const speciesLabel = getSpeciesLabel(species);
      const sizeNote =
        s.group_size && s.group_size > 1
          ? `Pod of ${s.group_size}`
          : "";
      const captionText = sizeNote
        ? `${sizeNote} ${speciesLabel}s spotted by ${who}`
        : `${speciesLabel} spotted by ${who}`;

      return {
        position: pos,
        lookAt: pos,
        camera: camPos,
        caption: captionText,
        species,
        color: getSpeciesColor(species),
        isRare: RARE_SPECIES.has(species),
        sighting: s,
      };
    });
  }, [sightings]);

  /* ── Species diversity stats ── */
  const speciesStats = useMemo(() => {
    const counts = new Map<string, number>();
    sightings.forEach((s) => {
      counts.set(s.species, (counts.get(s.species) ?? 0) + 1);
    });
    const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1]);
    const rareCount = sorted.filter(([sp]) => RARE_SPECIES.has(sp)).length;
    return { counts: sorted, uniqueCount: sorted.length, rareCount, total: sightings.length };
  }, [sightings]);

  /* ── Active sighting data for caption ── */
  const activeStop =
    activeIndex >= 0 && activeIndex < stops.length ? stops[activeIndex] : null;
  const activeSighting = activeStop?.sighting ?? null;
  const behaviorLabel = getBehaviorLabel(activeSighting?.behavior);
  const riskStyle = activeSighting?.risk_category
    ? RISK_STYLES[activeSighting.risk_category]
    : null;
  const iucnTag = activeSighting ? IUCN_TAG[activeSighting.species] : null;
  const smoothIcon = activeSighting
    ? SMOOTH_ICON_MAP[activeSighting.species]
    : null;

  /* ── Tour cycle ── */
  const advanceTour = useCallback(() => {
    if (stops.length === 0) return;
    const idx = cycleIndexRef.current % stops.length;
    cycleIndexRef.current++;

    setPhase("flying");
    setActiveIndex(idx);
    setCaptionVisible(false);

    timerRef.current = setTimeout(() => {
      setPhase("dwelling");
      setCaptionVisible(true);

      timerRef.current = setTimeout(() => {
        setCaptionVisible(false);
        setPhase("idle");
        timerRef.current = setTimeout(() => {
          advanceTour();
        }, 1500);
      }, TOUR_DWELL * 1000);
    }, TOUR_TRANSITION * 1000);
  }, [stops]);

  useEffect(() => {
    if (stops.length === 0) return;
    const startTimer = setTimeout(() => advanceTour(), 3000);
    return () => {
      clearTimeout(startTimer);
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [stops, advanceTour]);

  const marqueeSeconds = Math.max(speciesStats.counts.length * 4, 18);

  return (
    <div className={`relative overflow-hidden ${className}`}>
      {/* Marquee keyframes */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
            @keyframes globe-marquee {
              0%   { transform: translateX(0); }
              100% { transform: translateX(-50%); }
            }
          `,
        }}
      />

      {/* ── Three.js Canvas ─────────────────────────────── */}
      <Canvas
        camera={{
          fov: 45,
          near: 0.1,
          far: 100,
          position: [0, 1.5, ORBIT_RADIUS],
        }}
        gl={{ antialias: true, alpha: true }}
        style={{ background: "transparent" }}
        dpr={[1, 1.5]}
      >
        <GlobeScene
          stops={stops}
          activeIndex={activeIndex}
          phase={phase}
        />
      </Canvas>

      {/* ── Rich caption card ───────────────────────────── */}
      <div
        className={`absolute bottom-14 left-1/2 -translate-x-1/2
          z-10 transition-all duration-700 ${
            captionVisible
              ? "opacity-100 translate-y-0"
              : "opacity-0 translate-y-6 pointer-events-none"
          }`}
      >
        {activeSighting && activeStop && (
          <div
            className={`relative w-[340px] rounded-xl border
              backdrop-blur-xl shadow-2xl shadow-black/50 ${
                activeStop.isRare
                  ? "border-red-500/40 bg-gradient-to-br from-red-950/80 via-abyss-900/90 to-abyss-900/90"
                  : "border-ocean-500/30 bg-abyss-900/90"
              }`}
          >
            {/* Glow accent line at top */}
            <div
              className="absolute top-0 left-4 right-4 h-[2px] rounded-full opacity-60"
              style={{ background: activeStop.color }}
            />

            <div className="px-4 pt-3.5 pb-3">
              {/* Header: icon + species + IUCN + verified */}
              <div className="flex items-start gap-3">
                {/* Species silhouette icon */}
                <div className="relative shrink-0">
                  {smoothIcon ? (
                    <Image
                      src={`/whale_detailed_smooth_icons/${smoothIcon}`}
                      alt=""
                      width={36}
                      height={36}
                      className="opacity-80"
                      style={{
                        filter:
                          "invert(1) brightness(1) drop-shadow(0 0 4px " +
                          activeStop.color +
                          ")",
                      }}
                    />
                  ) : (
                    <Image
                      src="/whale_watch_logo.png"
                      alt=""
                      width={36}
                      height={36}
                      className="opacity-60"
                      style={{ filter: "invert(1) brightness(0.8)" }}
                    />
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <div
                      className="h-2.5 w-2.5 shrink-0 rounded-full shadow-lg"
                      style={{
                        background: activeStop.color,
                        boxShadow: `0 0 8px ${activeStop.color}80`,
                      }}
                    />
                    <span className="truncate text-sm font-bold text-white">
                      {getSpeciesLabel(activeSighting.species)}
                    </span>
                    {iucnTag && (
                      <span
                        className={`shrink-0 rounded px-1 py-0.5 text-[9px] font-black tracking-wider ring-1 ${iucnTag.cls}`}
                      >
                        {iucnTag.label}
                      </span>
                    )}
                  </div>

                  {/* Verification badge */}
                  {activeSighting.verification_status === "verified" && (
                    <div className="mt-0.5 flex items-center gap-1 text-[10px] font-semibold text-emerald-400">
                      <svg viewBox="0 0 16 16" fill="currentColor" className="h-3 w-3">
                        <path d="M8 0a8 8 0 1 0 0 16A8 8 0 0 0 8 0Zm3.78 5.28a.75.75 0 0 0-1.06-1.06L7 7.94 5.28 6.22a.75.75 0 0 0-1.06 1.06l2.25 2.25a.75.75 0 0 0 1.06 0l4.25-4.25Z" />
                      </svg>
                      Verified sighting
                    </div>
                  )}
                </div>
              </div>

              {/* Rare species celebration badge */}
              {activeStop.isRare && (
                <div className="mt-2 flex items-center gap-1.5 rounded-md bg-red-500/15 px-2.5 py-1 ring-1 ring-red-500/25">
                  <svg viewBox="0 0 16 16" fill="currentColor" className="h-3 w-3 text-red-400">
                    <path d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l.632 1.185a.75.75 0 0 0 .48.39l1.37.345c1.373.346 1.89 1.968.936 2.942l-.953 1.07a.75.75 0 0 0-.183.545l.086 1.4c.084 1.377-1.282 2.347-2.532 1.8l-1.272-.557a.75.75 0 0 0-.599 0l-1.272.557c-1.25.547-2.616-.423-2.532-1.8l.086-1.4a.75.75 0 0 0-.183-.545l-.953-1.07c-.954-.974-.437-2.596.936-2.942l1.37-.345a.75.75 0 0 0 .48-.39l.632-1.185Z" />
                  </svg>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-red-400">
                    Rare species sighting
                  </span>
                </div>
              )}

              {/* Caption */}
              <p className="mt-2.5 text-xs leading-relaxed text-slate-300">
                {activeStop.caption}
              </p>

              {/* Detail tags row */}
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                {behaviorLabel && (
                  <span className="rounded-full bg-ocean-500/15 px-2 py-0.5 text-[10px] font-medium text-ocean-300">
                    {behaviorLabel}
                  </span>
                )}
                {activeSighting.calf_present && (
                  <span className="rounded-full bg-pink-500/15 px-2 py-0.5 text-[10px] font-medium text-pink-400">
                    With calf
                  </span>
                )}
                {activeSighting.group_size && activeSighting.group_size > 1 && (
                  <span className="rounded-full bg-indigo-500/15 px-2 py-0.5 text-[10px] font-medium text-indigo-300">
                    Group of {activeSighting.group_size}
                  </span>
                )}
                {activeSighting.has_photo && (
                  <span className="rounded-full bg-purple-500/15 px-2 py-0.5 text-[10px] font-medium text-purple-400">
                    <svg viewBox="0 0 16 16" fill="currentColor" className="mr-0.5 inline h-2.5 w-2.5">
                      <path d="M6 2a.75.75 0 0 1 .6.3L7.6 4h4.65A1.75 1.75 0 0 1 14 5.75v5.5A1.75 1.75 0 0 1 12.25 13h-8.5A1.75 1.75 0 0 1 2 11.25v-5.5A1.75 1.75 0 0 1 3.75 4h.65l1-1.7A.75.75 0 0 1 6 2Zm2 4a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5Z" />
                    </svg>
                    Photo
                  </span>
                )}
                {activeSighting.has_audio && (
                  <span className="rounded-full bg-cyan-500/15 px-2 py-0.5 text-[10px] font-medium text-cyan-400">
                    <svg viewBox="0 0 16 16" fill="currentColor" className="mr-0.5 inline h-2.5 w-2.5">
                      <path d="M8 1a3 3 0 0 0-3 3v4a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3ZM5 9.414A4.002 4.002 0 0 0 7.25 13v1.25a.75.75 0 0 0 1.5 0V13A4.002 4.002 0 0 0 11 9.414V8.586A4 4 0 0 1 8 12a4 4 0 0 1-3-3.414v.828Z" />
                    </svg>
                    Audio
                  </span>
                )}
                {riskStyle && (
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${riskStyle.bg} ${riskStyle.text}`}
                  >
                    <span className={`mr-1 inline-block h-1.5 w-1.5 rounded-full ${riskStyle.dot}`} />
                    {riskStyle.label}
                  </span>
                )}
              </div>

              {/* Footer: time */}
              <div className="mt-2.5 flex items-center justify-between border-t border-white/5 pt-2 text-[10px] text-slate-500">
                <span>{timeAgo(activeSighting.created_at)}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Species ticker (scrolling marquee) ──────────── */}
      {speciesStats.counts.length > 0 && (
        <div className="absolute bottom-0 left-0 right-0 z-10">
          <div className="pointer-events-none h-6 bg-gradient-to-t from-abyss-950/90 to-transparent" />
          <div className="overflow-hidden bg-abyss-950/80 backdrop-blur-sm border-t border-ocean-900/30 py-1.5 px-2">
            <div
              className="flex gap-5"
              style={
                speciesStats.counts.length > 3
                  ? {
                      animation: `globe-marquee ${marqueeSeconds}s linear infinite`,
                      width: "max-content",
                    }
                  : { justifyContent: "center" }
              }
            >
              {speciesStats.counts.map(([sp, count]) => (
                <div key={sp} className="flex shrink-0 items-center gap-1.5">
                  <div
                    className="h-2 w-2 rounded-full shadow-sm"
                    style={{
                      background: getSpeciesColor(sp),
                      boxShadow: `0 0 4px ${getSpeciesColor(sp)}60`,
                    }}
                  />
                  <span className="whitespace-nowrap text-[10px] font-medium text-slate-400">
                    {getSpeciesLabel(sp)}
                  </span>
                  <span className="text-[10px] text-slate-600">({count})</span>
                </div>
              ))}
              {/* Duplicate for seamless marquee loop */}
              {speciesStats.counts.length > 3 &&
                speciesStats.counts.map(([sp, count]) => (
                  <div key={`dup-${sp}`} className="flex shrink-0 items-center gap-1.5">
                    <div
                      className="h-2 w-2 rounded-full shadow-sm"
                      style={{
                        background: getSpeciesColor(sp),
                        boxShadow: `0 0 4px ${getSpeciesColor(sp)}60`,
                      }}
                    />
                    <span className="whitespace-nowrap text-[10px] font-medium text-slate-400">
                      {getSpeciesLabel(sp)}
                    </span>
                    <span className="text-[10px] text-slate-600">({count})</span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Top-left: live badge ────────────────────────── */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-2">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-75" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-cyan-500" />
        </span>
        <span className="text-xs font-medium uppercase tracking-wide text-ocean-300/80">
          Community Sightings
        </span>
      </div>

      {/* ── Top-right: species diversity stats ──────────── */}
      <div className="absolute top-4 right-4 z-10 flex items-center gap-2 rounded-full border border-ocean-800/40 bg-abyss-900/70 px-3 py-1.5 backdrop-blur-sm">
        <span className="text-[11px] font-semibold text-ocean-300">
          {speciesStats.uniqueCount}
        </span>
        <span className="text-[11px] text-slate-500">species</span>
        <span className="text-slate-700">·</span>
        <span className="text-[11px] font-semibold text-ocean-300">
          {speciesStats.total}
        </span>
        <span className="text-[11px] text-slate-500">sightings</span>
        {speciesStats.rareCount > 0 && (
          <>
            <span className="text-slate-700">·</span>
            <span className="text-[11px] font-semibold text-red-400">
              {speciesStats.rareCount} rare
            </span>
          </>
        )}
      </div>

      {/* ── Whale tail watermark ────────────────────────── */}
      <div className="pointer-events-none absolute bottom-10 right-4 z-0 opacity-[0.04]">
        <Image
          src="/whale_watch_logo.png"
          alt=""
          width={80}
          height={80}
          style={{ filter: "invert(1)" }}
        />
      </div>
    </div>
  );
}
