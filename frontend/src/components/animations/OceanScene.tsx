"use client";

import {
  useRef,
  useMemo,
  useCallback,
  useState,
  useEffect,
} from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Environment } from "@react-three/drei";
import * as THREE from "three";
import * as SkeletonUtils from "three/examples/jsm/utils/SkeletonUtils.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { GLTF } from "three/examples/jsm/loaders/GLTFLoader.js";

/* ═══════════════════════════════════════════════════════════════
   Imperative GLB loader — starts fetching at module level,
   before React even mounts. No Suspense involved.
   ═══════════════════════════════════════════════════════════════ */

const gltfCache: Record<string, GLTF> = {};
const gltfPromises: Record<string, Promise<GLTF>> = {};
const gltfSubscribers: Record<string, Set<() => void>> = {};

function loadGLTF(path: string): Promise<GLTF> {
  if (!gltfPromises[path]) {
    gltfSubscribers[path] = new Set();
    gltfPromises[path] = new Promise((resolve, reject) => {
      new GLTFLoader().load(
        path,
        (gltf) => {
          gltfCache[path] = gltf;
          // Notify all waiting components
          gltfSubscribers[path]?.forEach((cb) => cb());
          resolve(gltf);
        },
        undefined,
        reject,
      );
    });
  }
  return gltfPromises[path];
}

/** Hook that returns the loaded GLTF or null. No Suspense. */
function useImperativeGLTF(path: string): GLTF | null {
  const [gltf, setGltf] = useState<GLTF | null>(
    () => gltfCache[path] ?? null,
  );

  useEffect(() => {
    // Already cached (loaded before component mounted)
    if (gltfCache[path]) {
      setGltf(gltfCache[path]);
      return;
    }
    // Subscribe to load completion
    const cb = () => setGltf(gltfCache[path] ?? null);
    gltfSubscribers[path]?.add(cb);
    // Also ensure loading has started
    loadGLTF(path);
    return () => {
      gltfSubscribers[path]?.delete(cb);
    };
  }, [path]);

  return gltf;
}

/* Start fetching IMMEDIATELY at module load — before React mounts */
loadGLTF("/models/blue_whale.glb");
loadGLTF("/models/humpback_whale.glb");

/* ═══════════════════════════════════════════════════════════════
   Constants — open-ocean palette
   ═══════════════════════════════════════════════════════════════ */

const DEEP_OCEAN = new THREE.Color(0x020c1a);
const FOG_OCEAN = new THREE.Color(0x031525);
const LIGHT_SHAFT_COLOR = new THREE.Color(0x7ee8f8);
const BUBBLE_COLOR = new THREE.Color(0x88ccee);
const SURFACE_Y = 12; // y-position of the water surface plane

/** Shared X/Z registry for soft inter-whale repulsion.
 *  Layout: [x0, z0, x1, z1, …] for up to 5 whales.
 *  Initialised to a large sentinel so unregistered slots never trigger repulsion.
 *  WHALE_SHARED_XZ_PREV is a snapshot of the PREVIOUS frame — all whales read from
 *  prev so every whale sees the same consistent positions regardless of tick order.
 *  WHALE_SHARED_XZ is the write target for this frame; swapped into prev each frame
 *  by the first whale to run (tracked via WHALE_FRAME_TOKEN). */
const WHALE_SHARED_XZ      = new Float32Array(10).fill(1e6);
const WHALE_SHARED_XZ_PREV = new Float32Array(10).fill(1e6);
let   WHALE_FRAME_TOKEN    = -1;   // last frame number that performed the swap
const WHALE_REPULSION_RADIUS    = 22;   // world units
const WHALE_REPULSION_RADIUS_SQ = WHALE_REPULSION_RADIUS * WHALE_REPULSION_RADIUS;
// Max X nudge applied per frame. Whale natural velocity ≈ 0.07 units/frame;
// 0.18 is ~2.5× that — enough to keep separation without snapping.
const WHALE_REPULSION_MAX_NUDGE = 0.18;
/** Y positions of up to 5 whales — written by SwimmingWhale each frame,
 *  read by InteractiveWaterSurface to gate bow-wave impulses. */
const WHALE_SHARED_Y = new Float32Array(5).fill(-999);

/* ══ Breach event bus ─────────────────────────────────────────
   Module-level queues — SwimmingWhale writes, consumers read.
   _pendingSplashes    → SplashSystem (particle burst)
   _pendingBreachImpulses → InteractiveWaterSurface (GPU ring pulse)
   ──────────────────────────────────────────────────────────── */
const _pendingSplashes: Array<{ x: number; z: number }> = [];
const _pendingBreachImpulses: Array<{ x: number; z: number; strength?: number }> = [];
function triggerSplash(x: number, z: number): void {
  _pendingSplashes.push({ x, z });
  _pendingBreachImpulses.push({ x, z });
}

interface LeapArc {
  startTime: number;
  duration: number;
  baseY: number;
  peakY: number;       // always > SURFACE_Y
  breachX: number;     // frozen X position for the whole breach
  breachZ: number;     // frozen Z position for the whole breach
  splashedUp: boolean;
  splashedDown: boolean;
}

interface CameraCharge {
  startTime: number;
  duration: number;
  startX: number;     // X at charge start (returned to on retreat)
  startZ: number;     // Z at charge start
  targetX: number;    // X near screen centre — keeps whale in-frame at close Z
  targetZ: number;    // Z target (close to camera)
  startY: number;     // Y at charge start (returned to on retreat)
  targetY: number;    // Y apex — whale rises toward surface during approach
  startYRot: number;  // yRot at charge start (to return to on retreat)
  targetYRot: number; // 0 = face +Z = directly toward camera
}

/* ═══════════════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════════════ */

interface WhaleInstance {
  modelPath: string;
  position: [number, number, number];
  scale: number;
  swimSpeed: number;
  /** Horizontal swimming range */
  xRange: number;
  /** Vertical bob amplitude */
  bobAmp: number;
  /** Phase offset */
  phase: number;
  /** Initial facing: Y-rotation offset */
  yRot: number;
  /** Depth range — how far the whale oscillates toward/away from camera (Z axis) */
  zRange: number;
  /** Starting animation clip name (multi-anim models only) */
  initialBehaviour?: string;
  /** Assigned by parent — index in whale array, used for inter-whale repulsion */
  whaleIndex?: number;
}

/* ═══════════════════════════════════════════════════════════════
   Scene Setup — open ocean, no box
   ═══════════════════════════════════════════════════════════════ */

function SceneSetup() {
  const { scene } = useThree();

  useEffect(() => {
    scene.background = DEEP_OCEAN;
    // Very gentle fog that fades into darkness — no visible boundary
    scene.fog = new THREE.FogExp2(FOG_OCEAN.getHex(), 0.008);
  }, [scene]);

  return null;
}

/* ═══════════════════════════════════════════════════════════════
   Swimming Whale — loads GLB with full textures + baked anims
   ═══════════════════════════════════════════════════════════════ */

/*
 * Behaviour sequences for multi-animation models (e.g. humpback).
 * Each entry: [clipName, { loop, next }].
 * "next" is picked randomly from the weighted pool after the clip finishes.
 * For single-animation models (blue whale) we just loop the one clip.
 *
 * Humpback animations available:
 *   swim1/2/3, swim_start, swim_end, idle1, leap1/2/3,
 *   swallow1/2, turn_L_start/swim1/swim2/end, turn_R_start/swim1/swim2/end
 */

interface BehaviourDef {
  loop: THREE.AnimationActionLoopStyles;
  repetitions: number;
  /** Weighted next-state options: [clipName, weight][] */
  next: [string, number][];
  /** Cross-fade duration in seconds */
  fadeIn: number;
}

const HUMPBACK_BEHAVIOURS: Record<string, BehaviourDef> = {
  "whale|swim1": {
    loop: THREE.LoopRepeat, repetitions: 2, fadeIn: 1.0,
    next: [
      ["whale|swim2", 2], ["whale|swim3", 2],
      ["whale|idle1", 1], ["whale|leap1", 3],
      ["whale|swallow1", 3],
      ["whale|turn_L_start", 2], ["whale|turn_R_start", 2],
      ["whale|camcharge", 5],
    ],
  },
  "whale|swim2": {
    loop: THREE.LoopRepeat, repetitions: 2, fadeIn: 1.0,
    next: [
      ["whale|swim1", 2], ["whale|swim3", 2],
      ["whale|idle1", 1], ["whale|leap2", 3],
      ["whale|swallow2", 3],
      ["whale|turn_L_start", 2], ["whale|turn_R_start", 2],
      ["whale|camcharge", 5],
    ],
  },
  "whale|swim3": {
    loop: THREE.LoopRepeat, repetitions: 2, fadeIn: 1.0,
    next: [
      ["whale|swim1", 2], ["whale|swim2", 2],
      ["whale|idle1", 1], ["whale|leap3", 3],
      ["whale|swallow1", 3],
      ["whale|turn_L_start", 2], ["whale|turn_R_start", 2],
      ["whale|camcharge", 5],
    ],
  },
  "whale|idle1": {
    loop: THREE.LoopRepeat, repetitions: 2, fadeIn: 1.5,
    next: [
      ["whale|swim1", 2], ["whale|swim2", 2],
      ["whale|leap1", 3], ["whale|leap2", 2],
      ["whale|swallow1", 3], ["whale|swallow2", 2],
      ["whale|camcharge", 5],
    ],
  },
  "whale|leap1": {
    loop: THREE.LoopOnce, repetitions: 1, fadeIn: 0.1,
    next: [
      ["whale|swim1", 3], ["whale|swim2", 2], ["whale|idle1", 1],
      ["whale|leap2", 2], ["whale|swallow1", 2],
    ],
  },
  "whale|leap2": {
    loop: THREE.LoopOnce, repetitions: 1, fadeIn: 0.1,
    next: [
      ["whale|swim2", 3], ["whale|swim3", 2], ["whale|idle1", 1],
      ["whale|leap3", 2], ["whale|swallow2", 2],
    ],
  },
  "whale|leap3": {
    loop: THREE.LoopOnce, repetitions: 1, fadeIn: 0.1,
    next: [
      ["whale|swim1", 3], ["whale|swim3", 2], ["whale|idle1", 1],
      ["whale|leap1", 2], ["whale|swallow1", 2],
    ],
  },
  "whale|swallow1": {
    loop: THREE.LoopOnce, repetitions: 1, fadeIn: 1.0,
    next: [
      ["whale|swim1", 3], ["whale|swim2", 2], ["whale|idle1", 1],
      ["whale|swallow2", 2], ["whale|leap1", 2],
    ],
  },
  "whale|swallow2": {
    loop: THREE.LoopOnce, repetitions: 1, fadeIn: 1.0,
    next: [
      ["whale|swim2", 3], ["whale|swim3", 2], ["whale|idle1", 1],
      ["whale|swallow1", 2], ["whale|leap2", 2],
    ],
  },
  // Camera charge: meta-state. weightedPick() selects this; transitionTo()
  // intercepts it, plays "whale|swallow1" (mouth open), and sets
  // cameraChargeRef to sweep the group toward the camera.
  "whale|camcharge": {
    loop: THREE.LoopOnce, repetitions: 1, fadeIn: 0.8,
    // next is never used (swallow1 fires its own finished event)
    next: [["whale|swim1", 3], ["whale|swim2", 2], ["whale|idle1", 1]],
  },
  "whale|turn_L_start": {
    loop: THREE.LoopOnce, repetitions: 1, fadeIn: 0.8,
    next: [["whale|turn_L_swim1", 5], ["whale|turn_L_swim2", 3]],
  },
  "whale|turn_L_swim1": {
    loop: THREE.LoopRepeat, repetitions: 2, fadeIn: 0.6,
    next: [["whale|turn_L_end", 5], ["whale|turn_L_swim2", 3]],
  },
  "whale|turn_L_swim2": {
    loop: THREE.LoopRepeat, repetitions: 2, fadeIn: 0.6,
    next: [["whale|turn_L_end", 5]],
  },
  "whale|turn_L_end": {
    loop: THREE.LoopOnce, repetitions: 1, fadeIn: 0.8,
    next: [
      ["whale|swim1", 3], ["whale|swim2", 2], ["whale|idle1", 1],
      ["whale|leap1", 2], ["whale|swallow1", 2],
    ],
  },
  "whale|turn_R_start": {
    loop: THREE.LoopOnce, repetitions: 1, fadeIn: 0.8,
    next: [["whale|turn_R_swim1", 5], ["whale|turn_R_swim2", 3]],
  },
  "whale|turn_R_swim1": {
    loop: THREE.LoopRepeat, repetitions: 2, fadeIn: 0.6,
    next: [["whale|turn_R_end", 5], ["whale|turn_R_swim2", 3]],
  },
  "whale|turn_R_swim2": {
    loop: THREE.LoopRepeat, repetitions: 2, fadeIn: 0.6,
    next: [["whale|turn_R_end", 5]],
  },
  "whale|turn_R_end": {
    loop: THREE.LoopOnce, repetitions: 1, fadeIn: 0.8,
    next: [
      ["whale|swim1", 3], ["whale|swim2", 2], ["whale|idle1", 1],
      ["whale|leap2", 2], ["whale|swallow2", 2],
    ],
  },
  // Transition clips
  "whale|swim_start": {
    loop: THREE.LoopOnce, repetitions: 1, fadeIn: 0.5,
    next: [["whale|swim1", 4], ["whale|swim2", 3], ["whale|swim3", 3]],
  },
  "whale|swim_end": {
    loop: THREE.LoopOnce, repetitions: 1, fadeIn: 0.8,
    next: [["whale|idle1", 5], ["whale|swim_start", 3]],
  },
};

/** Pick a random next clip from weighted options */
function weightedPick(options: [string, number][]): string {
  const total = options.reduce((s, [, w]) => s + w, 0);
  let r = Math.random() * total;
  for (const [name, w] of options) {
    r -= w;
    if (r <= 0) return name;
  }
  return options[0][0];
}

function SwimmingWhale({ config }: { config: WhaleInstance }) {
  const groupRef = useRef<THREE.Group>(null);
  const gltf = useImperativeGLTF(config.modelPath);
  const mixer = useRef<THREE.AnimationMixer | null>(null);
  const currentAction = useRef<THREE.AnimationAction | null>(null);
  const clipMap = useRef<Map<string, THREE.AnimationClip>>(new Map());

  // Mount generation counter — increments on every mount so that
  // useMemo produces a fresh clone after StrictMode remount (where
  // R3F disposes the previous clone's geometries/materials).
  const mountGen = useRef(0);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const gen = useMemo(() => ++mountGen.current, []);
  const leapArcRef = useRef<LeapArc | null>(null);
  // Post-override blend — gentle Y ease-in after any override clears.
  const postOverrideRef = useRef<{ time: number; x: number; y: number; z: number }>(
    { time: -999, x: 0, y: -4, z: 0 },
  );
  // Accumulated phase correction. During any positional override (arc, charge)
  // swimT keeps advancing but the whale is frozen. When the override ends we
  // subtract the elapsed time * spd so formulaX/Z at the first free frame
  // equals the frozen position — no drift, no corrective blend needed.
  const swimPhaseAdjRef = useRef(0);
  // Active camera charge: swim toward camera + mouth-open animation
  const cameraChargeRef = useRef<CameraCharge | null>(null);

  const model = gltf?.scene ?? null;
  const animations = gltf?.animations ?? [];
  const isMultiAnim = animations.length > 1;

  // SkeletonUtils.clone properly handles skinned meshes + bone bindings.
  // Depends on `gen` so a fresh clone is created if R3F disposed the old one.
  const clonedScene = useMemo(() => {
    if (!model) return null;
    void gen; // use gen to satisfy exhaustive-deps
    const clone = SkeletonUtils.clone(model);

    // Boost envMapIntensity for underwater visibility
    clone.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        const cloneMat = (m: THREE.Material) => {
          const c = m.clone();
          if (c instanceof THREE.MeshStandardMaterial) {
            c.envMapIntensity = 2.0;
          }
          return c;
        };
        if (Array.isArray(child.material)) {
          child.material = child.material.map(cloneMat);
        } else if (child.material) {
          child.material = cloneMat(child.material);
        }
      }
    });

    return clone;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [model, gen]);

  /** Transition to a named clip with cross-fade */
  const transitionTo = useCallback(
    (clipName: string, fadeIn: number) => {
      if (!mixer.current || !clonedScene) return;

      // Camera charge: meta-behaviour — plays swallow1 with a Z-sweep toward
      // the camera so the whale appears to lunge forward, mouth wide open.
      if (clipName === "whale|camcharge" && groupRef.current) {
        const swallowClip = clipMap.current.get("whale|swallow1");
        if (swallowClip) {
          const g = groupRef.current;
          // Sweep Z to ~35 units from origin — 25 units from camera (FOV 55).
          // Cap avoids the whale overshooting the near plane.
          const targetZ = Math.min(g.position.z + 50, 35);
          // Sweep X toward screen centre. At Z=35 the half-frame-width is only
          // ~14 units — a whale at X=±14 would be at the very edge.
          // Moving to 20% of the starting offset keeps it clearly in-frame
          // while retaining a slight left/right offset for visual variety.
          const targetX = g.position.x * 0.20;
          // Rise toward just below the waterline so the whale appears to climb
          // up as it charges — more visible and more dramatic from the camera.
          // Cap at SURFACE_Y - 3 so the whale doesn't fully breach.
          const targetY = Math.min(g.position.y + 7, SURFACE_Y - 3);
          cameraChargeRef.current = {
            startTime: performance.now() * 0.001,
            duration: swallowClip.duration,
            startX: g.position.x,
            startZ: g.position.z,
            targetX,
            targetZ,
            startY: g.position.y,
            targetY,
            startYRot: g.rotation.y,
            targetYRot: 0,
          };
          transitionTo("whale|swallow1", fadeIn);
        }
        return;
      }

      const clip = clipMap.current.get(clipName);
      if (!clip) return;

      const behaviour = HUMPBACK_BEHAVIOURS[clipName];
      const newAction = mixer.current.clipAction(clip, clonedScene);

      newAction.reset();
      newAction.setLoop(
        behaviour?.loop ?? THREE.LoopRepeat,
        behaviour?.repetitions ?? Infinity,
      );
      newAction.clampWhenFinished = true;
      newAction.fadeIn(fadeIn);

      if (currentAction.current) {
        currentAction.current.fadeOut(fadeIn);
      }

      newAction.play();
      currentAction.current = newAction;

      // ── Leap arc: drive whale up through the water surface ──
      if (clipName.includes("leap") && groupRef.current) {
        const leapClip = clipMap.current.get(clipName);
        // Use the full clip duration so the arc and skeleton stay in sync.
        const arcDuration = leapClip?.duration ?? 3.0;
        // Use the ACTUAL current y — not config.position[1] — so the
        // arc starts exactly where the whale is mid-bob.  Using the
        // config value caused a visible snap (up to ±bobAmp units).
        const baseY = groupRef.current.position.y;
        leapArcRef.current = {
          startTime: performance.now() * 0.001,
          duration: arcDuration,
          baseY,
          // Group rises to the waterline only — the GLB skeleton provides
          // all the visual height above the surface via bone animation.
          peakY: SURFACE_Y,
          breachX: groupRef.current.position.x,
          breachZ: groupRef.current.position.z,
          splashedUp: false,
          splashedDown: false,
        };
      } else if (!clipName.includes("leap")) {
        if (leapArcRef.current && groupRef.current) {
          const g = groupRef.current;
          const now = performance.now() * 0.001;
          // Subtract only the time the arc actually ran (it was cleared early).
          swimPhaseAdjRef.current -= (now - leapArcRef.current.startTime) * config.swimSpeed;
          // Same as the natural-end path: store corrected formula coords so the
          // blend start == blend target → no position travel, just velocity ease-in.
          const corrST = now * config.swimSpeed + config.phase + swimPhaseAdjRef.current;
          postOverrideRef.current = {
            time: now,
            x: config.position[0] + Math.sin(corrST * 0.12) * config.xRange,
            y: g.position.y,
            z: config.position[2] + Math.sin(corrST * 0.07 + config.phase * 2) * config.zRange,
          };
        }
        leapArcRef.current = null;
      }
    },
    [clonedScene],
  );

  // Set up animation system
  useEffect(() => {
    if (animations.length === 0 || !clonedScene) return;

    mixer.current = new THREE.AnimationMixer(clonedScene);

    // Build clip lookup
    animations.forEach((clip) => {
      clipMap.current.set(clip.name, clip);
    });

    if (isMultiAnim) {
      // Multi-animation model (humpback): start with the assigned
      // initial behaviour so each whale enters in a different state.
      const fallbackClips = ["whale|swim1", "whale|swim2", "whale|swim3"];
      const fallbackIdx = Math.floor(config.phase * 3) % 3;
      const startClip =
        config.initialBehaviour && clipMap.current.has(config.initialBehaviour)
          ? config.initialBehaviour
          : fallbackClips[fallbackIdx];

      transitionTo(startClip, 0.5);

      // Offset start time by phase so whales aren't synchronised
      if (currentAction.current) {
        const clip = clipMap.current.get(startClip);
        if (clip) {
          currentAction.current.time =
            (config.phase * clip.duration) % clip.duration;
        }
      }

      const onFinished = (e: { action: THREE.AnimationAction }) => {
        const finishedClipName = e.action.getClip().name;
        const behaviour = HUMPBACK_BEHAVIOURS[finishedClipName];
        if (behaviour && behaviour.next.length > 0) {
          const nextClip = weightedPick(behaviour.next);
          const nextBehaviour = HUMPBACK_BEHAVIOURS[nextClip];
          transitionTo(nextClip, nextBehaviour?.fadeIn ?? 1.0);
        } else {
          // Fallback: go back to swimming
          transitionTo("whale|swim1", 1.0);
        }
      };

      mixer.current.addEventListener("finished", onFinished);

      return () => {
        mixer.current?.removeEventListener("finished", onFinished);
        mixer.current?.stopAllAction();
        mixer.current = null;
        clipMap.current.clear();
      };
    } else {
      // Single-animation model (blue whale): just loop it
      const clip = animations[0];
      const action = mixer.current.clipAction(clip, clonedScene);
      action.play();
      action.setLoop(THREE.LoopRepeat, Infinity);
      action.time = (config.phase * clip.duration) % clip.duration;
      currentAction.current = action;

      return () => {
        mixer.current?.stopAllAction();
        mixer.current = null;
        clipMap.current.clear();
      };
    }
  }, [animations, clonedScene, config.phase, isMultiAnim, transitionTo]);

  useFrame((_, delta) => {
    if (!groupRef.current) return;
    const g = groupRef.current;
    const t = performance.now() * 0.001;
    const p = config.phase;
    const spd = config.swimSpeed;

    // Update animation mixer
    mixer.current?.update(delta);

    // ── Swimming path: slow sinusoidal cruise ──
    // swimPhaseAdjRef subtracts the time the whale spent frozen during arcs/
    // charges so formulaX/Z resume from the exact frozen position.
    const swimT = t * spd + p + swimPhaseAdjRef.current;

    // Horizontal sweep — paused during a breach
    const arc = leapArcRef.current;
    const charge = cameraChargeRef.current;
    if (arc) {
      // Lock X during breach
      g.position.x = arc.breachX;
    } else if (charge) {
      // Sweep X toward screen centre on approach, back on retreat.
      // Matches the Z phase split (0.55) so the path feels coherent.
      const cElapsedX = t - charge.startTime;
      const cPhaseX = Math.min(cElapsedX / charge.duration, 1.0);
      if (cPhaseX < 0.55) {
        const u = cPhaseX / 0.55;
        const eased = 1 - Math.pow(1 - u, 3); // easeOutCubic
        g.position.x =
          charge.startX + (charge.targetX - charge.startX) * eased;
      } else {
        const u = (cPhaseX - 0.55) / 0.45;
        const eased = u * u * u; // easeInCubic
        g.position.x =
          charge.targetX + (charge.startX - charge.targetX) * eased;
      }
    } else {
      const formulaX = config.position[0] + Math.sin(swimT * 0.12) * config.xRange;
      // swimPhaseAdjRef guarantees formulaX == breachX at the moment the override
      // clears, so there is no position snap. The 0.5s ease-in just smooths the
      // velocity transition from stationary to swimming speed.
      const txOver = t - postOverrideRef.current.time;
      if (txOver < 0.5) {
        const blend = (txOver / 0.5) ** 2;
        g.position.x = postOverrideRef.current.x +
          (formulaX - postOverrideRef.current.x) * blend;
      } else {
        g.position.x = formulaX;
      }
      // Soft repulsion: nudge away from any whale within WHALE_REPULSION_RADIUS.
      // All whales read from WHALE_SHARED_XZ_PREV (previous frame snapshot) so
      // tick order never affects the outcome. WHALE_SHARED_XZ_PREV is swapped from
      // the current write buffer once per render frame (first whale to run does it).
      const myIdx = config.whaleIndex ?? 0;
      // Swap buffers once per frame using the R3F frame counter as a token.
      const frameNum = Math.round(t * 60); // ~frame index at 60 fps
      if (frameNum !== WHALE_FRAME_TOKEN) {
        WHALE_FRAME_TOKEN = frameNum;
        WHALE_SHARED_XZ_PREV.set(WHALE_SHARED_XZ);
      }
      // X-only repulsion — Z lane assignments (-30,-24,-14,-5,+8) are only
      // 9-10 units apart, well within the radius, so Z repulsion would
      // constantly fight the lane layout and cause jitter.
      let repX = 0;
      for (let wi = 0; wi < 5; wi++) {
        if (wi === myIdx) continue;
        const ox = WHALE_SHARED_XZ_PREV[wi * 2];
        const oz = WHALE_SHARED_XZ_PREV[wi * 2 + 1];
        const dx = g.position.x - ox;
        const dz = g.position.z - oz;
        const dist2 = dx * dx + dz * dz;
        if (dist2 < WHALE_REPULSION_RADIUS_SQ && dist2 > 0.01) {
          const dist = Math.sqrt(dist2);
          // Quadratic falloff: 0 at radius edge, peaks at centre.
          // Avoids the linear spike that caused snapping at close range.
          const overlap = 1 - dist / WHALE_REPULSION_RADIUS;
          repX += (dx / dist) * overlap * overlap * WHALE_REPULSION_MAX_NUDGE;
        }
      }
      if (repX !== 0) {
        // Cap total nudge so multiple simultaneous neighbours can't compound
        // into a large single-frame jump.
        const clamped = Math.max(-WHALE_REPULSION_MAX_NUDGE, Math.min(WHALE_REPULSION_MAX_NUDGE, repX));
        g.position.x = Math.max(-90, Math.min(90, g.position.x + clamped));
      }
    }

    // ── Vertical: leap arc overrides normal bob ──
    if (arc) {
      const elapsed = t - arc.startTime;
      const phase = Math.min(elapsed / arc.duration, 1.0);
      // Group Y is frozen at swim depth for the entire clip.
      // The GLB skeleton already encodes the full breach arc in its bone
      // animation — adding a separate group arc created two competing
      // movements (artificial snap up, artificial fall down) that made the
      // real skeleton breach happen underground.
      //
      // Splash triggers are phase-based so they track the clip frame
      // directly and are not affected by group position.
      //
      // Rise smoothly from swim depth to SURFACE_Y over the first 18% of the
      // clip (easeOutQuad). The skeleton is swimming upward during this window,
      // so the group rise matches rather than snapping instantly.
      // After that the group holds at SURFACE_Y for the full breach above water.
      //
      // Tuning:
      //   RISE_END          — fraction of clip over which group rises to surface
      //   SPLASH_DOWN_PHASE — fraction at which entry splash fires + descent begins
      const RISE_END          = 0.30;  // 30% of clip = slow, natural float up
      const SPLASH_DOWN_PHASE = 0.45;       // tune if entry splash is early/late

      if (phase < RISE_END) {
        // Ease up from swim depth to waterline over the first 18% of the clip.
        const u = phase / RISE_END;
        g.position.y = arc.baseY + (SURFACE_Y - arc.baseY) * (u * (2 - u));
      } else if (phase < SPLASH_DOWN_PHASE) {
        // Hold at waterline while skeleton is in the air.
        g.position.y = SURFACE_Y;
      } else {
        // Ease back down to swim depth after re-entry (easeInQuad — starts slow,
        // accelerates downward so the whale appears to swim away underneath).
        const u = (phase - SPLASH_DOWN_PHASE) / (1.0 - SPLASH_DOWN_PHASE);
        g.position.y = SURFACE_Y + (arc.baseY - SURFACE_Y) * (u * u);
      }

      if (!arc.splashedDown && phase >= SPLASH_DOWN_PHASE) {
        triggerSplash(arc.breachX, arc.breachZ);
        arc.splashedDown = true;
      }
      if (phase >= 1.0) {
        // Re-sync swim phase so formulaX/Z return to the arc-start formula value.
        swimPhaseAdjRef.current -= arc.duration * spd;
        // Store the corrected formula positions — NOT g.position, which carries a
        // repulsion offset accumulated before the arc fired. Using g.position here
        // meant the 0.5 s blend had to traverse that offset, producing the visible
        // accelerating translation. With corrected formula coords the blend start
        // equals the blend target so no position travel occurs.
        const corrST = t * spd + p + swimPhaseAdjRef.current;
        postOverrideRef.current = {
          time: t,
          x: config.position[0] + Math.sin(corrST * 0.12) * config.xRange,
          y: g.position.y,
          z: config.position[2] + Math.sin(corrST * 0.07 + p * 2) * config.zRange,
        };
        leapArcRef.current = null;
      }

      // Nose-up during first half of clip, nose-down during second half.
      const vertDir = Math.cos(phase * Math.PI);
      g.rotation.x = THREE.MathUtils.lerp(g.rotation.x, vertDir * 0.28, 0.08);
    } else if (charge) {
      // Rise toward targetY on approach, return to startY on retreat.
      // Uses the same 55% apex as X and Z so the entire path is coherent.
      const cElapsedY = t - charge.startTime;
      const cPhaseY = Math.min(cElapsedY / charge.duration, 1.0);
      if (cPhaseY < 0.55) {
        const u = cPhaseY / 0.55;
        const eased = 1 - Math.pow(1 - u, 3); // easeOutCubic
        g.position.y =
          charge.startY + (charge.targetY - charge.startY) * eased;
      } else {
        const u = (cPhaseY - 0.55) / 0.45;
        const eased = u * u * u; // easeInCubic
        g.position.y =
          charge.targetY + (charge.startY - charge.targetY) * eased;
      }
      // Suppress pitch during charge — whale is swimming level
      g.rotation.x = THREE.MathUtils.lerp(g.rotation.x, 0, 0.03);
    } else {
      // Normal bob. swimPhaseAdjRef ensures rawBobY == arc.baseY the frame the
      // arc clears, so there is no vertical snap. The 1.0s blend just eases in
      // the bobbing motion so the whale doesn't instantly start oscillating.
      const rawBobY = config.position[1] + Math.sin(swimT * 0.18 + p) * config.bobAmp;
      const tyOver = t - postOverrideRef.current.time;
      const Y_BLEND_DURATION = 1.0;
      if (tyOver < Y_BLEND_DURATION) {
        const u = tyOver / Y_BLEND_DURATION;
        const blend = u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2;
        g.position.y =
          postOverrideRef.current.y + (rawBobY - postOverrideRef.current.y) * blend;
      } else {
        g.position.y = rawBobY;
      }
      // Pitch follows vertical movement
      const dy =
        Math.cos(swimT * 0.18 + p) * config.bobAmp * spd * 0.18;
      g.rotation.x = THREE.MathUtils.lerp(g.rotation.x, dy * 0.03, 0.02);
    }

    // Z drift — frozen during breach; swept toward camera during charge
    if (arc) {
      g.position.z = arc.breachZ;
    } else if (charge) {
      const cElapsed = t - charge.startTime;
      const cPhase = Math.min(cElapsed / charge.duration, 1.0);
      // Approach: easeOutCubic — fast initial lunge, slows as whale nears camera.
      // Retreat: easeInCubic — gentle push-off, builds back to cruising speed.
      // Apex at 55% so the whale lingers near the camera slightly longer than
      // it spends approaching, which reads as the whale "presenting" itself.
      if (cPhase < 0.55) {
        const u = cPhase / 0.55;
        const eased = 1 - Math.pow(1 - u, 3); // easeOutCubic
        g.position.z =
          charge.startZ + (charge.targetZ - charge.startZ) * eased;
      } else {
        const u = (cPhase - 0.55) / 0.45;
        const eased = u * u * u; // easeInCubic
        g.position.z =
          charge.targetZ + (charge.startZ - charge.targetZ) * eased;
      }
      if (cPhase >= 1.0) {
        // Re-sync swim phase so formulaX/Z return to the charge-start formula value.
        swimPhaseAdjRef.current -= charge.duration * spd;
        const corrST = t * spd + p + swimPhaseAdjRef.current;
        postOverrideRef.current = {
          time: t,
          x: config.position[0] + Math.sin(corrST * 0.12) * config.xRange,
          y: g.position.y,
          z: config.position[2] + Math.sin(corrST * 0.07 + p * 2) * config.zRange,
        };
        cameraChargeRef.current = null;
      }
    } else {
      const formulaZ =
        config.position[2] + Math.sin(swimT * 0.07 + p * 2) * config.zRange;
      const tzOver = t - postOverrideRef.current.time;
      if (tzOver < 0.5) {
        const blend = (tzOver / 0.5) ** 2;
        g.position.z = postOverrideRef.current.z +
          (formulaZ - postOverrideRef.current.z) * blend;
      } else {
        g.position.z = formulaZ;
      }
    }

    // Register position for inter-whale repulsion (read by others next frame).
    // Written after all X/Y/Z updates so includes arc, charge, and blend offsets.
    WHALE_SHARED_XZ[(config.whaleIndex ?? 0) * 2]     = g.position.x;
    WHALE_SHARED_XZ[(config.whaleIndex ?? 0) * 2 + 1] = g.position.z;
    WHALE_SHARED_Y[config.whaleIndex ?? 0]             = g.position.y;

    // ── Rotation: bank into turns (overridden during camera charge) ──
    if (charge) {
      // Three-phase yaw so turning feels like a real animal decision:
      //   0 → 35%  turn toward camera  (easeInOutSine — slow start, accelerates, decelerates)
      //   35 → 65% hold face-on        (whale is closest, mouth fully open)
      //   65 → 100% turn away           (easeInOutSine back to original heading)
      // desiredYaw is fully deterministic so the angle is predictable at every
      // frame. lerp(0.04) only smooths sub-frame jitter, not the turn itself.
      const cElapsed2 = t - charge.startTime;
      const cPhase2 = Math.min(cElapsed2 / charge.duration, 1.0);
      let desiredYaw: number;
      if (cPhase2 < 0.35) {
        const u = cPhase2 / 0.35;
        const eased = 0.5 - Math.cos(u * Math.PI) * 0.5; // easeInOutSine 0→1
        desiredYaw =
          charge.startYRot + (charge.targetYRot - charge.startYRot) * eased;
      } else if (cPhase2 < 0.65) {
        desiredYaw = charge.targetYRot; // hold face-on
      } else {
        const u = (cPhase2 - 0.65) / 0.35;
        const eased = 0.5 - Math.cos(u * Math.PI) * 0.5; // easeInOutSine 0→1
        desiredYaw =
          charge.targetYRot + (charge.startYRot - charge.targetYRot) * eased;
      }
      g.rotation.y = THREE.MathUtils.lerp(g.rotation.y, desiredYaw, 0.04);
      g.rotation.z = THREE.MathUtils.lerp(g.rotation.z, 0, 0.05);
    } else {
      // Patrol direction: cos(swimT * 0.12) is the normalised X velocity
      // (+1 = moving right, -1 = moving left). tanh sharpens it so the whale
      // holds a consistent 3/4 profile while cruising and faces toward the
      // camera only briefly at the off-screen turnarounds — like an animal
      // that spots the viewer while turning around.
      const patrolVel = Math.cos(swimT * 0.12);
      const dirSign = Math.tanh(patrolVel * 4.0); // smooth ±1 with fast transitions
      // π * 0.35 ≈ 63°: strong side profile + slight camera-facing angle
      const PATROL_FACE = Math.PI * 0.35;
      const targetYaw = dirSign * PATROL_FACE;
      g.rotation.y = THREE.MathUtils.lerp(g.rotation.y, targetYaw, 0.012);
      // Gentle lean into the turn (dolphin-like banking)
      g.rotation.z = THREE.MathUtils.lerp(g.rotation.z, -dirSign * 0.06, 0.012);
    }
  });

  // Don't render until the model has loaded
  if (!clonedScene) return null;

  return (
    <group
      ref={groupRef}
      position={config.position}
      rotation={[0, config.yRot, 0]}
      scale={[config.scale, config.scale, config.scale]}
    >
      <primitive object={clonedScene} dispose={null} />
    </group>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Splash System — physics-based water droplets on whale breach
   ═══════════════════════════════════════════════════════════════ */

const SPLASH_POOL = 500;
const SPLASH_PER_BURST = 90;
const SPLASH_LIFETIME = 2.8;
const SPLASH_GRAVITY = -16;

interface SplashParticle {
  x: number; y: number; z: number;
  vx: number; vy: number; vz: number;
  born: number;
  active: boolean;
  size: number;
}

function SplashSystem() {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const freeIdx = useRef(0);
  const particles = useRef<SplashParticle[]>(
    Array.from({ length: SPLASH_POOL }, () => ({
      x: 0, y: 0, z: 0, vx: 0, vy: 0, vz: 0,
      born: -999, active: false, size: 0.1,
    }))
  );

  const spawnBurst = useCallback((x: number, z: number) => {
    // Camera is at Z=60. Whales range from Z≈-30 (far/background) to Z≈35 (close).
    // More negative Z = further from camera = bigger apparent splash from viewer POV.
    // Map: Z=-30 (far background) → 1.0, Z=35 (near camera) → 0.35.
    const Z_FAR = -30, Z_NEAR = 35;
    const depthScale = 1.0 - 0.65 * Math.max(0, Math.min(1,
      (z - Z_FAR) / (Z_NEAR - Z_FAR)
    ));
    const burstCount = Math.round(SPLASH_PER_BURST * depthScale);
    for (let i = 0; i < burstCount; i++) {
      const idx = freeIdx.current % SPLASH_POOL;
      freeIdx.current++;
      const angle = Math.random() * Math.PI * 2;
      const horizSpeed = Math.sqrt(Math.random()) * 14 * depthScale;
      const upSpeed = (16 + Math.random() * 22) * depthScale;
      particles.current[idx] = {
        x: x + (Math.random() - 0.5) * 2.5,
        y: SURFACE_Y,
        z: z + (Math.random() - 0.5) * 2.5,
        vx: Math.cos(angle) * horizSpeed,
        vy: upSpeed,
        vz: Math.sin(angle) * horizSpeed,
        born: performance.now() * 0.001,
        active: true,
        size: (0.25 + Math.random() * 0.55) * depthScale,
      };
    }
  }, []);

  useFrame(() => {
    if (!meshRef.current) return;
    const now = performance.now() * 0.001;
    const dt = 1 / 60;

    // Consume events
    while (_pendingSplashes.length > 0) {
      const ev = _pendingSplashes.pop()!;
      spawnBurst(ev.x, ev.z);
    }

    for (let i = 0; i < SPLASH_POOL; i++) {
      const p = particles.current[i];
      if (!p.active) {
        dummy.scale.setScalar(0);
        dummy.updateMatrix();
        meshRef.current.setMatrixAt(i, dummy.matrix);
        continue;
      }
      const age = now - p.born;
      if (age > SPLASH_LIFETIME || p.y < SURFACE_Y - 2) {
        p.active = false;
        dummy.scale.setScalar(0);
        dummy.updateMatrix();
        meshRef.current.setMatrixAt(i, dummy.matrix);
        continue;
      }
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.z += p.vz * dt;
      p.vy += SPLASH_GRAVITY * dt;
      p.vx *= 0.993;
      p.vz *= 0.993;
      const lifeRatio = age / SPLASH_LIFETIME;
      dummy.position.set(p.x, p.y, p.z);
      dummy.scale.setScalar(p.size * (1 - lifeRatio * 0.6));
      dummy.updateMatrix();
      meshRef.current.setMatrixAt(i, dummy.matrix);
    }
    meshRef.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh
      ref={meshRef}
      args={[undefined, undefined, SPLASH_POOL]}
      frustumCulled={false}
    >
      <sphereGeometry args={[1, 5, 4]} />
      <meshBasicMaterial
        color={0xdff4ff}
        transparent
        opacity={0.88}
        depthWrite={false}
        fog={false}
        blending={THREE.AdditiveBlending}
      />
    </instancedMesh>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Bubbles
   ═══════════════════════════════════════════════════════════════ */

/* ═══════════════════════════════════════════════════════════════
   StarField — twinkling stars above the waterline
   Rendered as a Points cloud on a large hemisphere above SURFACE_Y.
   Each star has a unique phase/speed/size baked into its vertex
   color alpha so twinkling is entirely GPU-side (no JS per frame).
   ═══════════════════════════════════════════════════════════════ */

/* ── CPU-side Milky Way helpers ────────────────────────────────────
   Called once in useMemo — not per-frame.                          */
function mwHash(px: number, py: number): number {
  const n = Math.sin(px * 127.1 + py * 311.7) * 43758.5453;
  return n - Math.floor(n);
}
function mwValueNoise(x: number, y: number): number {
  const ix = Math.floor(x), iy = Math.floor(y);
  const fx = x - ix, fy = y - iy;
  const ux = fx * fx * (3 - 2 * fx), uy = fy * fy * (3 - 2 * fy);
  const a = mwHash(ix,   iy),   b = mwHash(ix+1, iy);
  const c = mwHash(ix,   iy+1), d = mwHash(ix+1, iy+1);
  return a + (b-a)*ux + (c-a)*uy + ((d-c)-(b-a))*ux*uy;
}
/** 3-octave fBm, result ≈ [0, 1]. */
function mwFbm(x: number, y: number): number {
  let v = 0, amp = 0.5, f = 1;
  for (let o = 0; o < 3; o++) {
    v += amp * mwValueNoise(x * f, y * f);
    amp *= 0.5; f *= 2;
  }
  return v / 0.875;
}
/** Dust-lane mask 0–1 (1 = fully dusty). Offset below centreline. */
function mwDust(along: number, cross: number): number {
  const sc       = cross + 0.08;                        /* downward bias */
  const lane     = mwFbm(along * 1.1, sc * 5.0);
  const fracture = mwFbm(along * 7.0, sc * 16.0);
  const raw      = (lane - 0.40) / 0.28;
  return Math.max(0, Math.min(1, raw)) * (0.55 + 0.45 * fracture);
}
/** Minimum angular distance [0, π] between two radian angles. */
function mwAngDist(a: number, b: number): number {
  const d = Math.abs(a - b) % (2 * Math.PI);
  return d > Math.PI ? 2 * Math.PI - d : d;
}
/** Box-Muller normal sample. */
function mwGauss(mean: number, sigma: number): number {
  const u1 = Math.max(Math.random(), 1e-10);
  return (
    mean +
    sigma *
      Math.sqrt(-2 * Math.log(u1)) *
      Math.cos(2 * Math.PI * Math.random())
  );
}

/* Stars: aTwinkle=1 → gentle shimmer; aTwinkle=0 → constant brightness */
const STAR_VERT = /* glsl */`
attribute float aPhase;
attribute float aSpeed;
attribute float aTwinkle;
attribute float aSize;
uniform  float uTime;
varying  float vAlpha;
void main() {
  float t       = uTime * aSpeed;
  float shimmer = (0.5 + 0.5*sin(t + aPhase))
                * (0.5 + 0.5*sin(t*1.618 + aPhase*2.3));
  /* 80% of stars are static (0.80); twinklers oscillate 0.50–0.95 */
  vAlpha        = mix(0.80, 0.50 + 0.45*shimmer, aTwinkle);
  gl_PointSize  = aSize;
  gl_Position   = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const STAR_FRAG = /* glsl */`
precision mediump float;
varying float vAlpha;
void main() {
  float d    = length(gl_PointCoord - 0.5);
  if (d > 0.5) discard;
  float soft = 1.0 - smoothstep(0.20, 0.50, d);
  gl_FragColor = vec4(1.0, 0.97, 0.92, soft * vAlpha);
}`;

/* Haze layers (outer halo / inner disk / core) share one shader pair.
   Per-blob colour and alpha are baked as vertex attributes.          */
const HAZE_VERT = /* glsl */`
attribute float aSize;
attribute vec3  aCol;
attribute float aAlpha;
varying   vec3  vCol;
varying   float vAlpha;
void main() {
  vCol         = aCol;
  vAlpha       = aAlpha;
  gl_PointSize = aSize;
  gl_Position  = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const HAZE_FRAG = /* glsl */`
precision mediump float;
varying vec3  vCol;
varying float vAlpha;
void main() {
  float d    = length(gl_PointCoord - 0.5);
  if (d > 0.5) discard;
  float soft = 1.0 - smoothstep(0.0, 0.5, d);
  gl_FragColor = vec4(vCol, soft * vAlpha);
}`;

function StarField({ count = 1800 }: { count?: number }) {
  const pointsRef = useRef<THREE.Points>(null);

  const {
    geometry, material,
    outerGeo, outerMat,
    innerGeo, innerMat,
    coreGeo,  coreMat,
  } = useMemo(() => {

    /* ── Band plane & great-circle basis ─────────────────────────────
       Band normal n=(0.42, 0.60, 0.68) places the arc diagonally across
       the upper sky from lower-left to upper-right — well away from the
       GodRays spotlight (which is near the logo at z≈28, centre-screen).
       The galaxy arc crosses the zenith region and extends far left and
       right of centre so it spans most of the visible sky width.        */
    const nx = 0.42, ny = 0.60, nz = 0.68;
    const e1rawX = nz, e1rawZ = -nx;
    const e1len  = Math.sqrt(e1rawX*e1rawX + e1rawZ*e1rawZ);
    const ue1x = e1rawX/e1len, ue1y = 0.0, ue1z = e1rawZ/e1len;
    const ue2x =  ny*ue1z;
    const ue2y =  nz*ue1x - nx*ue1z;
    const ue2z = -ny*ue1x;

    /* GC sits at along=1.0 → upper-right quadrant of the arc, away from
       the logo spotlight which lives near screen-centre / Z-forward.    */
    const GC_ALONG = 1.0;
    const DOME_R   = 290;

    const arcToWorld = (
      along: number, cr: number, r: number,
    ): [number, number, number] => {
      const cx = Math.cos(along)*ue1x + Math.sin(along)*ue2x;
      const cy = Math.cos(along)*ue1y + Math.sin(along)*ue2y;
      const cz = Math.cos(along)*ue1z + Math.sin(along)*ue2z;
      const px = Math.cos(cr)*cx + Math.sin(cr)*nx;
      const py = Math.cos(cr)*cy + Math.sin(cr)*ny;
      const pz = Math.cos(cr)*cz + Math.sin(cr)*nz;
      return [px*r, SURFACE_Y + py*r, pz*r - 30];
    };

    const bandDirY = (along: number, cr: number): number => {
      const cy = Math.cos(along)*ue1y + Math.sin(along)*ue2y;
      return Math.cos(cr)*cy + Math.sin(cr)*ny;
    };

    const mkHazeGeo = (
      pos: Float32Array, sz: Float32Array,
      col: Float32Array, alp: Float32Array,
    ): THREE.BufferGeometry => {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      g.setAttribute('aSize',    new THREE.BufferAttribute(sz,  1));
      g.setAttribute('aCol',     new THREE.BufferAttribute(col, 3));
      g.setAttribute('aAlpha',   new THREE.BufferAttribute(alp, 1));
      return g;
    };
    const mkHazeMat = (blending: number): THREE.ShaderMaterial =>
      new THREE.ShaderMaterial({
        vertexShader: HAZE_VERT, fragmentShader: HAZE_FRAG,
        transparent: true, depthWrite: false,
        blending: blending as THREE.Blending, fog: false,
      });

    /* ════════════════════════════════════════════════════════════════
       LAYER 0 — Background stars (uniform hemisphere, faint)
       LAYER 1 — Galaxy stars (band-concentrated, dust-suppressed)
       ════════════════════════════════════════════════════════════════ */
    const BG_COUNT  = count;
    const GAL_COUNT = 9000;
    const STAR_TOT  = BG_COUNT + GAL_COUNT;
    const sPos = new Float32Array(STAR_TOT * 3);
    const sPha = new Float32Array(STAR_TOT);
    const sSpd = new Float32Array(STAR_TOT);
    const sSz  = new Float32Array(STAR_TOT);
    const sTwi = new Float32Array(STAR_TOT);

    for (let i = 0; i < BG_COUNT; i++) {
      const az = Math.random() * Math.PI * 2;
      const el = (8 + Math.random() * 82) * (Math.PI / 180);
      const r  = 280 + Math.random() * 40;
      sPos[i*3]   = r * Math.cos(el) * Math.cos(az);
      sPos[i*3+1] = SURFACE_Y + r * Math.sin(el);
      sPos[i*3+2] = r * Math.cos(el) * Math.sin(az) - 30;
      sPha[i] = Math.random() * Math.PI * 2;
      sSpd[i] = 0.3 + Math.random() * 1.0;
      sSz[i]  = 0.8 + Math.random() * 1.0;      /* 0.8–1.8 px — small */
      sTwi[i] = Math.random() < 0.15 ? 1 : 0;
    }

    /* Galaxy-linked stars: wide arc extent (σ=2.2 rad covers ~126°),
       Gaussian cross-band, dust suppression.                           */
    for (let i = 0; i < GAL_COUNT; i++) {
      const si    = BG_COUNT + i;
      const along = Math.random() * Math.PI * 2;
      const gd    = mwAngDist(along, GC_ALONG);
      /* σ=2.2 rad ≈ 126° half-width → galaxy spans almost half the circle */
      const gcW   = Math.exp(-gd * gd / (2.2 * 2.2));
      if (gcW < 0.10 && Math.random() > gcW * 6) { sSz[si] = 0; continue; }
      /* Gaussian cross-band, width grows near GC: 3°–14° */
      const crossRad = mwGauss(0, (3.0 + 11.0 * gcW) * (Math.PI / 180));
      if (bandDirY(along, crossRad) < 0.07) { sSz[si] = 0; continue; }
      const dust = mwDust(along, crossRad);
      if (dust > 0.55) { sSz[si] = 0; continue; }
      const [wx, wy, wz] = arcToWorld(along, crossRad, 280 + Math.random()*30);
      sPos[si*3] = wx; sPos[si*3+1] = wy; sPos[si*3+2] = wz;
      sPha[si] = Math.random() * Math.PI * 2;
      sSpd[si] = 0.2 + Math.random() * 0.7;
      const dustDim = 1 - dust * 0.65;
      sSz[si]  = ((0.8 + 1.6*gcW) + Math.random()*(0.4+gcW)) * dustDim;
      sTwi[si] = Math.random() < 0.10 ? 1 : 0;
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(sPos, 3));
    geo.setAttribute('aPhase',   new THREE.BufferAttribute(sPha, 1));
    geo.setAttribute('aSpeed',   new THREE.BufferAttribute(sSpd, 1));
    geo.setAttribute('aSize',    new THREE.BufferAttribute(sSz,  1));
    geo.setAttribute('aTwinkle', new THREE.BufferAttribute(sTwi, 1));
    const mat = new THREE.ShaderMaterial({
      vertexShader: STAR_VERT, fragmentShader: STAR_FRAG,
      uniforms: { uTime: { value: 0 } },
      transparent: true, depthWrite: false,
      blending: THREE.AdditiveBlending, fog: false,
    });

    /* ════════════════════════════════════════════════════════════════
       LAYER 2 — Outer halo
       Very many tiny soft blobs. Small size (4–9 px) and low per-blob
       alpha (0.008–0.018) so they accumulate into smooth continuous
       luminosity rather than visible circular sprites.
       Spans the full galaxy width (σ=2.0 rad), cross-band σ=14–22°.
       Colour: blue/cyan outer → soft teal near GC.
       NormalBlending preserves dark dust gaps.
       ════════════════════════════════════════════════════════════════ */
    const N_OUTER = 12000;
    const oPos = new Float32Array(N_OUTER * 3);
    const oSz  = new Float32Array(N_OUTER);
    const oCol = new Float32Array(N_OUTER * 3);
    const oAlp = new Float32Array(N_OUTER);

    for (let h = 0; h < N_OUTER; h++) {
      const along   = Math.random() * Math.PI * 2;
      const gd      = mwAngDist(along, GC_ALONG);
      const armFade = Math.exp(-gd * gd / (2.0 * 2.0));
      if (armFade < 0.04) { oSz[h] = 0; continue; }
      const crossRad = mwGauss(0, (14 + 8*armFade) * (Math.PI / 180));
      if (bandDirY(along, crossRad) < 0.07) { oSz[h] = 0; continue; }
      const dust = mwDust(along, crossRad);
      if (dust > 0.52) { oSz[h] = 0; continue; }
      const [wx, wy, wz] = arcToWorld(along, crossRad, DOME_R);
      oPos[h*3] = wx; oPos[h*3+1] = wy; oPos[h*3+2] = wz;
      /* Small blobs — accumulation creates smooth band, not FX spheres */
      oSz[h] = 4 + Math.random() * 5;
      const dm = 1 - dust * 0.70;
      /* Blue outer → teal near centre */
      oCol[h*3]   = (0.28 + 0.20*armFade) * dm;
      oCol[h*3+1] = (0.52 + 0.14*armFade) * dm;
      oCol[h*3+2] = (0.95 - 0.18*armFade) * dm;
      oAlp[h] = (0.008 + 0.012*armFade) * (0.5 + Math.random()*0.5)
                * (1 - dust * 0.85);
    }
    const outerGeo = mkHazeGeo(oPos, oSz, oCol, oAlp);
    const outerMat = mkHazeMat(THREE.NormalBlending);

    /* ════════════════════════════════════════════════════════════════
       LAYER 3 — Inner disk
       Concentrated within σ=1.3 rad of GC. Many small blobs (5–12 px),
       very low per-blob alpha so 5000 blobs produce a continuous band.
       Asymmetric: lower side 1.8× wider for ragged dust edge.
       Upper side 25% brighter.
       Colour: lavender/mauve → warm rose near GC centre.
       ════════════════════════════════════════════════════════════════ */
    const N_INNER = 8000;
    const iPos = new Float32Array(N_INNER * 3);
    const iSz  = new Float32Array(N_INNER);
    const iCol = new Float32Array(N_INNER * 3);
    const iAlp = new Float32Array(N_INNER);

    for (let h = 0; h < N_INNER; h++) {
      const along   = Math.random() * Math.PI * 2;
      const gd      = mwAngDist(along, GC_ALONG);
      const gcW     = Math.exp(-gd * gd / (1.3 * 1.3));
      if (gcW < 0.06) { iSz[h] = 0; continue; }
      const rawCross = mwGauss(0, (3.5 + 9.0 * gcW) * (Math.PI / 180));
      /* Lower side extends 1.8× further — asymmetric dust-heavy lower edge */
      const crossRad = rawCross < 0 ? rawCross * 1.8 : rawCross;
      if (bandDirY(along, crossRad) < 0.07) { iSz[h] = 0; continue; }
      const dust = mwDust(along, crossRad);
      if (dust > 0.45) { iSz[h] = 0; continue; }
      const [wx, wy, wz] = arcToWorld(along, crossRad, DOME_R - 3);
      iPos[h*3] = wx; iPos[h*3+1] = wy; iPos[h*3+2] = wz;
      iSz[h] = 5 + Math.random() * 7;           /* 5–12 px */
      const dm = 1 - dust * 0.72;
      /* Mauve/lavender outer → soft rose nearer GC */
      iCol[h*3]   = (0.68 + 0.26*gcW) * dm;
      iCol[h*3+1] = (0.36 + 0.36*gcW) * dm;
      iCol[h*3+2] = (0.78 - 0.22*gcW) * dm;
      const upBias = crossRad > 0 ? 1.25 : 0.78;
      iAlp[h] = (0.018 + 0.040*gcW) * (0.4 + Math.random()*0.6)
                * (1 - dust * 0.92) * upBias;
    }
    const innerGeo = mkHazeGeo(iPos, iSz, iCol, iAlp);
    const innerMat = mkHazeMat(THREE.NormalBlending);

    /* ════════════════════════════════════════════════════════════════
       LAYER 4 — Galactic core
       Two sub-layers: broad pink bloom + compact white/yellow hot centre.
       The bloom is σ=32°×12° (elliptical spindle cross-section visible
       to the eye at dome radius 290). Hot centre is σ=12°×4°.
       Many small blobs (4–10 px), very high per-blob count so they
       fuse into one coherent luminous structure, not a particle cluster.
       AdditiveBlending: blooms on top of disk, creating overexposed core.
       ════════════════════════════════════════════════════════════════ */
    const N_CORE = 3200;
    const cPos = new Float32Array(N_CORE * 3);
    const cSz  = new Float32Array(N_CORE);
    const cCol = new Float32Array(N_CORE * 3);
    const cAlp = new Float32Array(N_CORE);

    /* Bloom layer (outer 2/3 of blobs): σA=32°, σC=12°, pink/lavender */
    const SA_B = 32 * Math.PI / 180;
    const SC_B = 12 * Math.PI / 180;
    /* Hot centre (inner 1/3): σA=12°, σC=4°, white/yellow */
    const SA_H = 12 * Math.PI / 180;
    const SC_H =  4 * Math.PI / 180;
    const CO   =  2.0 * Math.PI / 180;  /* centroid offset above centreline */

    for (let h = 0; h < N_CORE; h++) {
      const isHot    = h < N_CORE / 3;
      const sA = isHot ? SA_H : SA_B;
      const sC = isHot ? SC_H : SC_B;
      const along    = GC_ALONG + mwGauss(0, sA);
      const crossRad = mwGauss(CO, sC);
      if (bandDirY(along, crossRad) < 0.07) { cSz[h] = 0; continue; }
      const dA    = mwAngDist(along, GC_ALONG);
      const dC    = Math.abs(crossRad - CO);
      /* Normalised distance in ellipse coordinates */
      const coreW = Math.exp(-(dA*dA)/(2*sA*sA) - (dC*dC)/(2*sC*sC));
      const [wx, wy, wz] = arcToWorld(along, crossRad, DOME_R - 4);
      cPos[h*3] = wx; cPos[h*3+1] = wy; cPos[h*3+2] = wz;
      if (isHot) {
        cSz[h] = 4 + Math.random() * 6;           /* 4–10 px hot centre */
        /* White → warm yellow, full brightness */
        cCol[h*3]   = 1.0;
        cCol[h*3+1] = 0.88 + 0.12 * coreW;
        cCol[h*3+2] = 0.55 + 0.35 * coreW;
        cAlp[h] = (0.12 + 0.22 * coreW) * (0.5 + Math.random()*0.5);
      } else {
        cSz[h] = 5 + Math.random() * 9;           /* 5–14 px bloom */
        /* Pink/lavender bloom around core */
        cCol[h*3]   = 0.90 + 0.10 * coreW;
        cCol[h*3+1] = 0.42 + 0.32 * coreW;
        cCol[h*3+2] = 0.72 - 0.12 * coreW;
        cAlp[h] = (0.040 + 0.080 * coreW) * (0.4 + Math.random()*0.6);
      }
    }
    const coreGeo = mkHazeGeo(cPos, cSz, cCol, cAlp);
    const coreMat = mkHazeMat(THREE.AdditiveBlending);

    return {
      geometry: geo, material: mat,
      outerGeo, outerMat,
      innerGeo, innerMat,
      coreGeo,  coreMat,
    };
  }, [count]);

  useEffect(() => () => {
    geometry.dispose(); material.dispose();
    outerGeo.dispose(); outerMat.dispose();
    innerGeo.dispose(); innerMat.dispose();
    coreGeo.dispose();  coreMat.dispose();
  }, [geometry, material, outerGeo, outerMat, innerGeo, innerMat,
      coreGeo, coreMat]);

  useFrame(() => {
    const m = pointsRef.current?.material as THREE.ShaderMaterial | undefined;
    if (m) m.uniforms.uTime.value = performance.now() * 0.001;
  });

  /* Render back → front: outer halo → inner disk → core bloom → stars */
  return (
    <>
      <points geometry={outerGeo} material={outerMat} />
      <points geometry={innerGeo} material={innerMat} />
      <points geometry={coreGeo}  material={coreMat}  />
      <points ref={pointsRef} geometry={geometry} material={material} />
    </>
  );
}

/* ═══════════════════════════════════════════════════════════════
   ShootingStars — streaks that fire randomly across the sky
   Pool of MAX_STREAKS Line2-style quads; each lives ~0.8 s.
   ═══════════════════════════════════════════════════════════════ */

const SHOOT_VERT = /* glsl */`
attribute float aT;        /* 0=tail, 1=head along streak */
uniform float uProgress;   /* 0→1 over streak lifetime   */
uniform vec3  uStart;
uniform vec3  uEnd;
uniform float uFade;
varying float vAlpha;
void main() {
  /* Head leads, tail lags — creates the classic fading comet look */
  float headT = uProgress;
  float tailT = max(0.0, uProgress - 0.45);
  vec3  pos   = mix(uStart, uEnd, mix(tailT, headT, aT));
  /* Brightest at head (aT=1), transparent at tail (aT=0) */
  vAlpha = aT * uFade * smoothstep(0.0, 0.12, uProgress)
                      * (1.0 - smoothstep(0.75, 1.0, uProgress));
  gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
}`;

const SHOOT_FRAG = /* glsl */`
precision mediump float;
varying float vAlpha;
void main() {
  gl_FragColor = vec4(0.95, 0.97, 1.0, vAlpha);
}`;

const MAX_STREAKS = 6;

interface Streak {
  start: THREE.Vector3;
  end:   THREE.Vector3;
  age:   number;         /* seconds since spawn */
  dur:   number;         /* total duration      */
  fade:  number;         /* brightness scale    */
  active: boolean;
}

function ShootingStars() {
  const streaks = useRef<Streak[]>(
    Array.from({ length: MAX_STREAKS }, () => ({
      start: new THREE.Vector3(), end: new THREE.Vector3(),
      age: 0, dur: 1, fade: 1, active: false,
    }))
  );
  const nextFire = useRef(1 + Math.random() * 2); /* first star in 1–3 s */
  const elapsed  = useRef(0);

  /* One geometry + material per slot — cheap, MAX_STREAKS is tiny */
  const slots = useMemo(() => {
    return Array.from({ length: MAX_STREAKS }, () => {
      /* Two vertices: tail (aT=0) and head (aT=1) */
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(6), 3));
      geo.setAttribute("aT",       new THREE.BufferAttribute(new Float32Array([0, 1]), 1));
      const mat = new THREE.ShaderMaterial({
        vertexShader:   SHOOT_VERT,
        fragmentShader: SHOOT_FRAG,
        uniforms: {
          uProgress: { value: 0 },
          uStart:    { value: new THREE.Vector3() },
          uEnd:      { value: new THREE.Vector3() },
          uFade:     { value: 1 },
        },
        transparent: true,
        depthWrite:  false,
        blending:    THREE.AdditiveBlending,
        fog:         false,
      });
      return { geo, mat };
    });
  }, []);

  /* Pre-create THREE.Line objects so we can render via <primitive> */
  const lineObjects = useMemo(
    () => slots.map(({ geo, mat }) => new THREE.Line(geo, mat)),
    [slots],
  );

  useEffect(
    () => () => {
      slots.forEach(({ geo, mat }) => { geo.dispose(); mat.dispose(); });
      lineObjects.forEach(l => l.geometry.dispose());
    },
    [slots, lineObjects],
  );

  function spawnStreak(slot: number) {
    const az1  = Math.random() * Math.PI * 2;
    const el1  = (25 + Math.random() * 55) * (Math.PI / 180);
    const r    = 270;
    const sx   = r * Math.cos(el1) * Math.cos(az1);
    const sy   = SURFACE_Y + r * Math.sin(el1);
    const sz   = r * Math.cos(el1) * Math.sin(az1) - 30;
    const len  = 50 + Math.random() * 40;
    const dx   = (Math.random() - 0.5) * 0.6;
    const dy   = -(0.3 + Math.random() * 0.5);
    const dz   = (Math.random() - 0.5) * 0.4;
    const dn   = Math.sqrt(dx * dx + dy * dy + dz * dz);
    const s    = streaks.current[slot];
    s.start.set(sx, sy, sz);
    s.end.set(sx + (dx / dn) * len, sy + (dy / dn) * len, sz + (dz / dn) * len);
    s.age    = 0;
    s.dur    = 0.55 + Math.random() * 0.4;
    s.fade   = 0.6 + Math.random() * 0.4;
    s.active = true;
  }

  useFrame((_, delta) => {
    elapsed.current += delta;
    if (elapsed.current >= nextFire.current) {
      const free = streaks.current.findIndex(s => !s.active);
      if (free >= 0) spawnStreak(free);
      elapsed.current  = 0;
      nextFire.current = 1.5 + Math.random() * 3;
    }
    for (let i = 0; i < MAX_STREAKS; i++) {
      const s   = streaks.current[i];
      const mat = slots[i].mat;
      if (!s.active) { mat.uniforms.uFade.value = 0; continue; }
      s.age += delta;
      if (s.age >= s.dur) { s.active = false; mat.uniforms.uFade.value = 0; continue; }
      mat.uniforms.uProgress.value = s.age / s.dur;
      mat.uniforms.uStart.value.copy(s.start);
      mat.uniforms.uEnd.value.copy(s.end);
      mat.uniforms.uFade.value     = s.fade;
    }
  });

  return (
    <>
      {lineObjects.map((lineObj, i) => (
        <primitive key={i} object={lineObj} />
      ))}
    </>
  );
}

function Bubbles({ count = 80 }: { count?: number }) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);

  const bubbles = useMemo(() => {
    return Array.from({ length: count }, () => ({
      x: (Math.random() - 0.5) * 140,
      // Spawn anywhere from seabed up to just below the waterline
      y: -30 + Math.random() * (SURFACE_Y + 28),
      z: -10 - Math.random() * 60,
      speed: 0.2 + Math.random() * 0.6,
      size: 0.04 + Math.random() * 0.14,
      wobbleSpeed: 0.5 + Math.random() * 1.5,
      wobbleAmp: 0.3 + Math.random() * 0.8,
      phase: Math.random() * Math.PI * 2,
    }));
  }, [count]);

  useFrame(() => {
    if (!meshRef.current) return;
    const t = performance.now() * 0.001;

    bubbles.forEach((b, i) => {
      b.y += b.speed * 0.016;
      if (b.y > SURFACE_Y) {
        b.y = -30;
        b.x = (Math.random() - 0.5) * 140;
        b.z = -10 - Math.random() * 60;
      }

      dummy.position.set(
        b.x + Math.sin(t * b.wobbleSpeed + b.phase) * b.wobbleAmp,
        b.y,
        b.z +
          Math.cos(t * b.wobbleSpeed + b.phase + 1) * b.wobbleAmp * 0.4,
      );
      dummy.scale.setScalar(b.size);
      dummy.updateMatrix();
      meshRef.current!.setMatrixAt(i, dummy.matrix);
    });

    meshRef.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, count]}>
      <sphereGeometry args={[1, 6, 4]} />
      <meshBasicMaterial
        color={BUBBLE_COLOR}
        transparent
        opacity={0.18}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </instancedMesh>
  );
}

/* ═══════════════════════════════════════════════════════════════
   WhaleBubbleTrails — micro-bubbles that stream from whale bodies
   Reads WHALE_SHARED_XZ / WHALE_SHARED_Y written each frame by
   SwimmingWhale. 30 bubbles per whale slot, sin(life·π) scale
   curve so each bubble swells from nothing, peaks, then pops.
   ═══════════════════════════════════════════════════════════════ */
const TRAIL_PER_WHALE = 30;
const N_TRAIL_WHALES  = 5;
const TRAIL_TOTAL     = TRAIL_PER_WHALE * N_TRAIL_WHALES;

function WhaleBubbleTrails() {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const dummy   = useMemo(() => new THREE.Object3D(), []);

  /* Flat typed arrays — zero GC pressure per frame */
  const bSX  = useRef(new Float32Array(TRAIL_TOTAL));
  const bSY  = useRef(new Float32Array(TRAIL_TOTAL));
  const bSZ  = useRef(new Float32Array(TRAIL_TOTAL));
  const bST  = useRef(new Float32Array(TRAIL_TOTAL).fill(-1)); // spawn time; -1 = dead
  const bLS  = useRef(new Float32Array(TRAIL_TOTAL));          // lifespan
  const bRS  = useRef(new Float32Array(TRAIL_TOTAL));          // rise speed
  const bWP  = useRef(new Float32Array(TRAIL_TOTAL));          // wobble phase
  const bWA  = useRef(new Float32Array(TRAIL_TOTAL));          // wobble amp
  const bSZ2 = useRef(new Float32Array(TRAIL_TOTAL));          // base sphere radius

  const ptr   = useRef(new Uint8Array(N_TRAIL_WHALES).fill(0));
  const lastT = useRef(new Float32Array(N_TRAIL_WHALES).fill(-1));

  useFrame(() => {
    if (!meshRef.current) return;
    const now = performance.now() * 0.001;

    /* Spawn ~12 bubbles/s per active whale */
    for (let w = 0; w < N_TRAIL_WHALES; w++) {
      const wy = WHALE_SHARED_Y[w];
      if (wy < -900) continue;                            // whale not yet loaded
      if (now - lastT.current[w] < 0.082) continue;      // ~12 Hz
      lastT.current[w] = now;

      const slot = w * TRAIL_PER_WHALE + ptr.current[w];
      ptr.current[w] = (ptr.current[w] + 1) % TRAIL_PER_WHALE;

      const wx = WHALE_SHARED_XZ[w * 2];
      const wz = WHALE_SHARED_XZ[w * 2 + 1];

      /* Scatter around whale body — slight downward bias simulates tail wake */
      bSX.current[slot] = wx + (Math.random() - 0.5) * 5;
      bSY.current[slot] = wy - 1.0 + (Math.random() - 0.5) * 3;
      bSZ.current[slot] = wz + (Math.random() - 0.5) * 5;
      bST.current[slot] = now;
      bLS.current[slot] = 1.2 + Math.random() * 1.4;     // 1.2–2.6 s lifetime
      bRS.current[slot] = 2.0 + Math.random() * 2.5;     // 2–4.5 units/s rise
      bWP.current[slot] = Math.random() * Math.PI * 2;
      bWA.current[slot] = 0.15 + Math.random() * 0.45;
      bSZ2.current[slot] = 0.03 + Math.random() * 0.06;  // 0.03–0.09 radius
    }

    /* Animate all bubble slots */
    for (let i = 0; i < TRAIL_TOTAL; i++) {
      const spawnT = bST.current[i];
      if (spawnT < 0) {
        dummy.scale.setScalar(0);
        dummy.updateMatrix();
        meshRef.current!.setMatrixAt(i, dummy.matrix);
        continue;
      }

      const elapsed = now - spawnT;
      const life    = elapsed / bLS.current[i]; // 0 → 1

      if (life >= 1.0) {
        bST.current[i] = -1;
        dummy.scale.setScalar(0);
        dummy.updateMatrix();
        meshRef.current!.setMatrixAt(i, dummy.matrix);
        continue;
      }

      /* Corkscrew wobble as bubble rises */
      const bx = bSX.current[i]
        + Math.sin(now * 1.3 + bWP.current[i]) * bWA.current[i];
      const by = bSY.current[i] + elapsed * bRS.current[i];
      const bz = bSZ.current[i]
        + Math.cos(now * 0.9 + bWP.current[i]) * bWA.current[i] * 0.5;

      /* sin(life·π): 0 at birth, peak at mid-life, 0 at death → natural "pop" */
      const scale = bSZ2.current[i] * Math.sin(life * Math.PI);

      dummy.position.set(bx, by, bz);
      dummy.scale.setScalar(Math.max(0, scale));
      dummy.updateMatrix();
      meshRef.current!.setMatrixAt(i, dummy.matrix);
    }

    meshRef.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, TRAIL_TOTAL]}>
      <sphereGeometry args={[1, 6, 4]} />
      <meshBasicMaterial
        color={BUBBLE_COLOR}
        transparent
        opacity={0.32}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </instancedMesh>
  );
}

/* ═══════════════════════════════════════════════════════════════
   God Rays — light shafts from above
   ═══════════════════════════════════════════════════════════════ */

function GodRays({ count = 24 }: { count?: number }) {
  /* ── Sun entry point on the water surface ─────────────────────
     Camera is at [0, 2, 60] FOV-55.  A point at [0, 12, 20] lies
     ~14° above the camera forward-axis — near vertical screen-centre.
     All shafts originate from this single pivot so they visually
     fan outward from one bright spot. */
  const SUN_X = 1, SUN_Z = 28;

  /* Every shaft shares the same downward lean (parallel = sun at infinity).
     Perspective then makes them converge back toward the entry point. */
  const DOWN_TILT = -0.85;   /* ≈ 49° from vertical — steep enough to read as downward shafts */

  /* ── Per-pixel shaft texture ─────────────────────────────────
     Horizontal: bell-curve (zero at edges)
     Vertical:   slow-fade exponent 0.6 — stays bright most of its length */
  const rayTexture = useMemo(() => {
    const W = 64, H = 512;
    const canvas = document.createElement("canvas");
    canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext("2d")!;
    const imageData = ctx.createImageData(W, H);
    const data = imageData.data;
    for (let row = 0; row < H; row++) {
      const v      = row / (H - 1);
      const alphaV = Math.pow(1 - v, 0.6);
      for (let col = 0; col < W; col++) {
        const u      = col / (W - 1);
        const bell   = (1 - Math.cos(Math.PI * u)) / 2;
        const alphaH = Math.sqrt(bell);
        const idx    = (row * W + col) * 4;
        data[idx]     = 255;
        data[idx + 1] = 255;
        data[idx + 2] = 255;
        data[idx + 3] = Math.round(alphaH * alphaV * 255);
      }
    }
    ctx.putImageData(imageData, 0, 0);
    const tex = new THREE.CanvasTexture(canvas);
    tex.flipY = false;
    return tex;
  }, []);

  const rays = useMemo(() => {
    let seed = 31337;
    const rand = () => {
      seed = (seed * 16807) % 2147483647;
      return (seed - 1) / 2147483646;
    };
    return Array.from({ length: count }, (_, i) => ({
      /* Evenly distribute around the full 360° circle so rays spread
         outward in every direction — the sunburst / fan-from-centre look. */
      azimuth:     (i / count) * Math.PI * 2,
      deltaTilt:   (rand() - 0.5) * 0.10,   /* ±0.05 rad organic variation */
      height:      180 + rand() * 50,        /* 180–230 world units deep    */
      width:        7  + rand() * 4,         /* 7–11  world units wide      */
      opacityBase: 0.11 + rand() * 0.06,     /* 0.11–0.17                   */
      f1:    0.09 + rand() * 0.13,
      f2:    0.25 + rand() * 0.35,
      f3:    0.67 + rand() * 0.78,
      phase:  (i / count) * Math.PI * 2,
      phase2: rand() * Math.PI * 2,
      phase3: rand() * Math.PI * 2,
    }));
  }, [count]);

  const innerRefs = useRef<Array<THREE.Group | null>>([]);

  useFrame(() => {
    const t = performance.now() * 0.001;
    innerRefs.current.forEach((grp, i) => {
      if (!grp) return;
      const ray  = rays[i];
      const mesh = grp.children[0] as THREE.Mesh;
      if (!mesh) return;
      const mat  = mesh.material as THREE.MeshBasicMaterial;

      /* Aperiodic 3-frequency shimmer */
      const shimmer =
        0.50 * Math.sin(t * ray.f1 + ray.phase)  +
        0.30 * Math.sin(t * ray.f2 + ray.phase2) +
        0.20 * Math.sin(t * ray.f3 + ray.phase3);
      mat.opacity = ray.opacityBase * (0.45 + 0.55 * shimmer);

      /* Each ray sways slightly around its azimuth — surface refraction */
      grp.rotation.y =
        ray.azimuth +
        Math.sin(t * 0.031 + ray.phase)  * 0.035 +
        Math.sin(t * 0.068 + ray.phase2) * 0.018;

      /* Width breath */
      mesh.scale.x = 1.0 + 0.12 * Math.sin(t * ray.f2 * 0.5 + ray.phase3);
    });
  });

  return (
    <group position={[SUN_X, SURFACE_Y + 1, SUN_Z]}>
      {rays.map((ray, i) => (
        <group
          key={i}
          ref={el => { innerRefs.current[i] = el; }}
          rotation={[DOWN_TILT + ray.deltaTilt, ray.azimuth, 0]}
        >
          {/* Top of mesh sits at the group pivot (the surface entry point) */}
          <mesh position={[0, -ray.height / 2, 0]}>
            <planeGeometry args={[ray.width, ray.height]} />
            <meshBasicMaterial
              color={LIGHT_SHAFT_COLOR}
              map={rayTexture}
              transparent
              opacity={ray.opacityBase}
              side={THREE.DoubleSide}
              depthWrite={false}
              blending={THREE.AdditiveBlending}
            />
          </mesh>
        </group>
      ))}
    </group>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Floating Particles (marine snow / plankton)
   ═══════════════════════════════════════════════════════════════ */

function FloatingParticles({ count = 200 }: { count?: number }) {
  const pointsRef = useRef<THREE.Points>(null);

  const [positions, velocities] = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const vel = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 150;
      pos[i * 3 + 1] = -30 + Math.random() * 70;
      pos[i * 3 + 2] = -10 - Math.random() * 70;
      vel[i * 3] = (Math.random() - 0.5) * 0.008;
      vel[i * 3 + 1] = 0.001 + Math.random() * 0.006;
      vel[i * 3 + 2] = (Math.random() - 0.5) * 0.008;
    }
    return [pos, vel];
  }, [count]);

  useFrame(() => {
    if (!pointsRef.current) return;
    const posAttr = pointsRef.current.geometry.getAttribute(
      "position",
    ) as THREE.BufferAttribute;
    const arr = posAttr.array as Float32Array;

    for (let i = 0; i < count; i++) {
      arr[i * 3] += velocities[i * 3];
      arr[i * 3 + 1] += velocities[i * 3 + 1];
      arr[i * 3 + 2] += velocities[i * 3 + 2];
      if (arr[i * 3 + 1] > 40) {
        arr[i * 3 + 1] = -30;
        arr[i * 3] = (Math.random() - 0.5) * 150;
        arr[i * 3 + 2] = -10 - Math.random() * 70;
      }
    }
    posAttr.needsUpdate = true;
  });

  const posAttrRef = useRef<THREE.BufferAttribute>(null);

  useEffect(() => {
    if (posAttrRef.current) {
      posAttrRef.current.array = positions;
      posAttrRef.current.needsUpdate = true;
    }
  }, [positions]);

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          ref={posAttrRef}
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.12}
        color={0x5599bb}
        transparent
        opacity={0.22}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

/* ═══════════════════════════════════════════════════════════════
   InteractiveWaterSurface — GPU ping-pong wave simulation
   ─────────────────────────────────────────────────────────────
   Architecture:
   • Two WebGLRenderTargets (SIM_WIDTH × SIM_HEIGHT, HalfFloat)
     ping-pong each frame via a simulation shader that runs the
     2-D wave equation:  h_next = 2·h_curr − h_prev + c²·∇²h_curr
   • Whale Y positions (WHALE_SHARED_Y) gate continuous bow-wave
     impulses when a whale is within 4 units of SURFACE_Y.
   • Breach events (_pendingBreachImpulses) inject a single large
     Gaussian impulse that spreads as an expanding ring.
   • High-res display mesh (256×128 segments) displaces vertices
     entirely on the GPU via a vertex shader sampling the height
     texture — no CPU readback, no geometry updates per frame.
   ─────────────────────────────────────────────────────────────
   World extents of the water plane (PlaneGeometry 240×90,
   center [0, SURFACE_Y, -35], rotation [-PI/2, 0, 0]):
     World X : [-120, +120]  →  UV u = (wx + 120) / 240
     World Z : [-80,  +10]   →  UV v = (-wz + 10) / 90
   (v is inverted because -PI/2 X-rotation maps local +Y → world -Z)
   ═══════════════════════════════════════════════════════════════ */

const SIM_WIDTH  = 256;
const SIM_HEIGHT = 128;

function worldToWaterUV(wx: number, wz: number): [number, number] {
  return [(wx + 120.0) / 240.0, (-wz + 10.0) / 90.0];
}

/* ── Simulation shader ─────────────────────────────────────── */
const WAVE_SIM_VERT = /* glsl */`
void main() {
  gl_Position = vec4(position.xy, 0.0, 1.0);
}`;

const WAVE_SIM_FRAG = /* glsl */`
precision highp float;
uniform sampler2D uCurrent;
uniform sampler2D uPrevious;
uniform vec2  uTexelSize;
uniform float uSpeed;
uniform float uDamping;
uniform vec2  uWhaleUV[5];
uniform float uWhaleStrength[5];
uniform vec2  uBreachUV[4];
uniform float uBreachStrength[4];

void main() {
  vec2 uv   = gl_FragCoord.xy * uTexelSize;
  float curr = texture2D(uCurrent,  uv).r;
  float prev = texture2D(uPrevious, uv).r;

  /* 5-point Laplacian */
  float n = texture2D(uCurrent, uv + vec2(0.0,          uTexelSize.y)).r;
  float s = texture2D(uCurrent, uv - vec2(0.0,          uTexelSize.y)).r;
  float e = texture2D(uCurrent, uv + vec2(uTexelSize.x, 0.0         )).r;
  float w = texture2D(uCurrent, uv - vec2(uTexelSize.x, 0.0         )).r;
  float lap = n + s + e + w - 4.0 * curr;

  float next = (2.0 * curr - prev + uSpeed * lap) * uDamping;

  /* Continuous bow-wave from nearby whales */
  for (int i = 0; i < 5; i++) {
    float str = uWhaleStrength[i];
    if (str > 0.00005) {
      vec2 d = uv - uWhaleUV[i];
      next += str * exp(-dot(d, d) * 1000.0);  /* wider → visible ripple */
    }
  }

  /* One-shot breach ring impulses */
  for (int i = 0; i < 4; i++) {
    float str = uBreachStrength[i];
    if (str > 0.0001) {
      vec2 d = uv - uBreachUV[i];
      next += str * exp(-dot(d, d) * 280.0);   /* wider → bigger splash */
    }
  }

  gl_FragColor = vec4(clamp(next, -6.0, 6.0), 0.0, 0.0, 1.0);
}`;

/* ── Display shader ────────────────────────────────────────── */
const WATER_DISP_VERT = /* glsl */`
uniform sampler2D uHeightmap;
uniform float     uDisplacementScale;
uniform float     uTime;
varying float     vTotalHeight;
varying float     vHeightField;
varying vec3      vNormal;      /* approximate world-space normal for specular */
varying vec2      vUv;

void main() {
  vUv = uv;

  /* ─ Long ocean swells (primary energy) ────────────────────── */
  float swell =
    sin(position.x * 0.050 + uTime * 0.80)                            * 4.0 +
    sin(position.y * 0.070 + uTime * 0.65 + 1.20)                     * 2.8 +
    sin((position.x - position.y * 0.5) * 0.040 + uTime * 0.50)       * 1.8 +
    sin(position.x * 0.180 + position.y * 0.120 + uTime * 1.20 + 2.0) * 0.9 +
    sin(position.x * 0.280 - position.y * 0.200 + uTime * 1.60)       * 0.45;

  /* ─ Choppy cross-chop (secondary detail) ─────────────────── */
  float chop =
    sin(position.x * 0.42  + position.y * 0.31  + uTime * 2.10) * 0.28 +
    sin(position.x * 0.63  - position.y * 0.51  + uTime * 2.80) * 0.18 +
    sin(position.x * 0.95  + position.y * 0.78  + uTime * 3.40) * 0.10 +
    sin(position.x * 1.40  - position.y * 1.10  + uTime * 4.20) * 0.06;

  float hf    = texture2D(uHeightmap, uv).r;
  vHeightField = hf;
  float bg    = swell + chop;
  vTotalHeight = bg + hf * uDisplacementScale;

  /* ─ Finite-difference surface normal (for specular) ───────── */
  float eps = 1.5;
  float hL = sin((position.x-eps)*0.050+uTime*0.80)*3.0 + sin((position.x-eps)*0.180+position.y*0.120+uTime*1.20+2.0)*0.7
           + sin((position.x-eps)*0.42+position.y*0.31+uTime*2.10)*0.28;
  float hR = sin((position.x+eps)*0.050+uTime*0.80)*3.0 + sin((position.x+eps)*0.180+position.y*0.120+uTime*1.20+2.0)*0.7
           + sin((position.x+eps)*0.42+position.y*0.31+uTime*2.10)*0.28;
  float hD = sin(position.x*0.050+uTime*0.80)*3.0 + sin((position.y-eps)*0.070+uTime*0.65+1.20)*2.0
           + sin(position.x*0.42+(position.y-eps)*0.31+uTime*2.10)*0.28;
  float hU = sin(position.x*0.050+uTime*0.80)*3.0 + sin((position.y+eps)*0.070+uTime*0.65+1.20)*2.0
           + sin(position.x*0.42+(position.y+eps)*0.31+uTime*2.10)*0.28;
  /* After -PI/2 X-rotation the plane normal is world-Y.
     dX and dZ give the slope, so normal ≈ normalize(-dX, 1, -dZ). */
  vNormal = normalize(vec3(-(hR-hL)/(2.0*eps), 1.0, -(hU-hD)/(2.0*eps)));

  vec3 disp = position;
  disp.z   += vTotalHeight;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(disp, 1.0);
}`;

const WATER_DISP_FRAG = /* glsl */`
precision mediump float;
varying float vTotalHeight;
varying float vHeightField;
varying vec3  vNormal;
varying vec2  vUv;

uniform vec2  uRingUV[8];   /* UV centre of each ring                  */
uniform float uRingAge[8];  /* age in seconds; -1.0 = inactive slot    */

/* ── Cheap hash-based value noise used for ring perturbation ── */
float hash(vec2 p) {
  p = fract(p * vec2(127.1, 311.7));
  p += dot(p, p + 19.19);
  return fract(p.x * p.y);
}
/* 1-D noise along an angle θ: smoothly blends 4 hash samples */
float angleNoise(float theta, float seed) {
  float s   = theta * 3.0 + seed;          /* wrap to ~[0, 6π] range    */
  float i0  = floor(s);
  float f   = smoothstep(0.0, 1.0, fract(s));
  float a   = hash(vec2(i0,        seed));
  float b   = hash(vec2(i0 + 1.0, seed));
  float c   = hash(vec2(i0 + 2.0, seed));
  float d   = hash(vec2(i0 + 3.0, seed));
  return mix(mix(a, b, f), mix(c, d, f), f);
}

void main() {
  /* Camera is BELOW the surface (Y=2 < SURFACE_Y=12).
     gl_FrontFacing=false on the underside — flip normal so lighting
     calculations work correctly for the face the camera actually sees. */
  vec3 n = gl_FrontFacing ? vNormal : -vNormal;

  /* ─ Height remapping ─────────────────────────────────────── */
  float h = vTotalHeight * 0.10;
  float t = clamp(h * 0.5 + 0.5, 0.0, 1.0);  /* 0=trough, 1=crest */

  /* ─ Base water colour ────────────────────────────────────── */
  vec3 deep  = vec3(0.005, 0.055, 0.130);
  vec3 mid   = vec3(0.020, 0.160, 0.340);
  vec3 crest = vec3(0.060, 0.340, 0.520);
  vec3 foam  = vec3(0.820, 0.930, 1.000);  /* bright white-blue whitecaps */

  vec3 col = mix(deep,  mid,   smoothstep(0.10, 0.45, t));
       col = mix(col,   crest, smoothstep(0.45, 0.72, t));
  /* Whitecaps: fire only near true crests — subtle, not dominant */
  float whitecap = smoothstep(0.70, 0.90, t);
  col = mix(col, foam, whitecap * 0.55);

  /* ─ Specular sun glint (uses face-corrected normal) ──────────── */
  vec3  sunDir  = normalize(vec3(0.05, 0.85, 0.52));
  /* View direction from below: camera is beneath, looking upward */
  vec3  viewDir = normalize(vec3(0.0, -0.90, 0.44));
  vec3  halfV   = normalize(sunDir + viewDir);
  float spec    = pow(max(dot(n, halfV), 0.0), 120.0);
  float spec2   = pow(max(dot(n, halfV), 0.0),  14.0) * 0.07;
  col += vec3(1.0, 0.97, 0.88) * spec  * 0.85;
  col += vec3(0.55, 0.78, 1.0) * spec2;

  /* ─ Expanding bioluminescent ring ripples ───────────────────── */
  /* A ring fires each time a whale crosses SURFACE_Y (breach or re-entry).
     Radius expands at 14 world-units/sec.  Perturbed with angle-varying
     noise so it looks like a real disturbed water ring, not a compass arc. */
  float ringGlow = 0.0;
  for (int i = 0; i < 8; i++) {
    if (uRingAge[i] >= 0.0) {
      vec2 d      = vUv - uRingUV[i];
      vec2 dWorld = vec2(d.x * 240.0, d.y * 90.0);
      float dist   = length(dWorld);
      float theta  = atan(dWorld.y, dWorld.x);  /* angle around ring centre */

      /* ① Radial wobble: ±3 world units, 5 bumps around the ring,
            strength grows with radius so early ring is smooth, later ragged */
      float seed    = float(i) * 7.53;
      float wobble  = (angleNoise(theta, seed) * 2.0 - 1.0)
                      * 3.0 * smoothstep(0.0, 1.2, uRingAge[i]);

      /* ② Slow temporal drift so the shape evolves as it expands */
      float drift   = (angleNoise(theta + uRingAge[i] * 0.4, seed + 1.3) * 2.0 - 1.0)
                      * 1.5 * smoothstep(0.3, 1.5, uRingAge[i]);

      float radius  = uRingAge[i] * 14.0 + wobble + drift;

      /* ③ Brightness modulation: 3–5 bright blobs unevenly spaced */
      float bright  = 0.55 + 0.45 * angleNoise(theta * 0.7 + seed, seed + 2.7);

      /* ④ Ring width widens slightly as energy disperses */
      float width   = 2.5 + uRingAge[i] * 0.8;

      float fade    = 1.0 - smoothstep(0.0, 2.5, uRingAge[i]);
      float ring    = smoothstep(width, 0.0, abs(dist - radius));
      ringGlow = max(ringGlow, ring * fade * bright);
    }
  }
  col  = mix(col, vec3(0.04, 0.96, 0.82), ringGlow * 0.92);
  col += vec3(0.15, 0.85, 1.00) * ringGlow * ringGlow * 2.00;

  /* ─ Fresnel-style opacity ───────────────────────────────── */
  float alpha = clamp(0.68 - t * 0.18 + whitecap * 0.12 + ringGlow * 0.35 + spec * 0.25, 0.38, 0.98);

  gl_FragColor = vec4(col, alpha);
}`;

function InteractiveWaterSurface() {
  /* ── Ping-pong render targets ─────────────────────────── */
  const targets = useMemo(() => {
    const makeRT = () => new THREE.WebGLRenderTarget(SIM_WIDTH, SIM_HEIGHT, {
      minFilter: THREE.NearestFilter,
      magFilter: THREE.NearestFilter,
      format:    THREE.RGBAFormat,
      type:      THREE.HalfFloatType,
      stencilBuffer: false,
      depthBuffer:   false,
    });
    return [makeRT(), makeRT()];
  }, []);

  useEffect(() => () => { targets[0].dispose(); targets[1].dispose(); }, [targets]);

  /* ── Orthographic camera for fullscreen simulation quad ── */
  const orthoCamera = useMemo(
    () => new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1),
    [],
  );

  /* ── Simulation pass ──────────────────────────────────── */
  const { simScene, simMat } = useMemo(() => {
    const mat = new THREE.ShaderMaterial({
      vertexShader:   WAVE_SIM_VERT,
      fragmentShader: WAVE_SIM_FRAG,
      uniforms: {
        uCurrent:       { value: null },
        uPrevious:      { value: null },
        uTexelSize:     { value: new THREE.Vector2(1 / SIM_WIDTH, 1 / SIM_HEIGHT) },
        uSpeed:         { value: 0.40 },   /* c² — Courant 0.40 < 0.5 stable; faster ring propagation */
        uDamping:       { value: 0.992 },  /* longer ring travel before dissipation */
        uWhaleUV:       { value: Array.from({ length: 5 }, () => new THREE.Vector2(0.5, 0.5)) },
        uWhaleStrength: { value: new Float32Array(5) },
        uBreachUV:      { value: Array.from({ length: 4 }, () => new THREE.Vector2(0.5, 0.5)) },
        uBreachStrength:{ value: new Float32Array(4) },
      },
      depthTest:  false,
      depthWrite: false,
    });
    const scene = new THREE.Scene();
    scene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat));
    return { simScene: scene, simMat: mat };
  }, []);

  /* ── Display material ─────────────────────────────────── */
  const displayMat = useMemo(() => new THREE.ShaderMaterial({
    vertexShader:   WATER_DISP_VERT,
    fragmentShader: WATER_DISP_FRAG,
    uniforms: {
      uHeightmap:         { value: null },
      uDisplacementScale: { value: 9.0 },
      uTime:              { value: 0.0 },
      uRingUV:            { value: Array.from({ length: 8 }, () => new THREE.Vector2(0, 0)) },
      uRingAge:           { value: new Float32Array(8).fill(-1) },
    },
    transparent: true,
    side:        THREE.DoubleSide,
    depthWrite:  false,
  }), []);

  const pingPong   = useRef(0);
  const frameCount  = useRef(0);

  /* Ring ripple state — up to 8 simultaneous expanding rings */
  const RING_COUNT  = 8;
  const ringUVs     = useRef(Array.from({ length: 8 }, () => new THREE.Vector2(0, 0)));
  const ringAges    = useRef(new Float32Array(8).fill(-1));
  const ringHead    = useRef(0);            /* next slot to overwrite */
  const prevWhaleY  = useRef(new Float32Array(5).fill(-999)); /* for crossing detection */

  useFrame(({ gl }, delta) => {
    const curr = pingPong.current;
    const prev = 1 - curr;

    /* ── Continuous bow-wave impulses ─────────────────── */
    const wakeUVs = simMat.uniforms.uWhaleUV.value      as THREE.Vector2[];
    const wakeStr = simMat.uniforms.uWhaleStrength.value as Float32Array;
    for (let i = 0; i < 5; i++) {
      const wx = WHALE_SHARED_XZ[i * 2];
      const wz = WHALE_SHARED_XZ[i * 2 + 1];
      if (wx < 1e5) {
        /* Flat strength — every swimming whale disturbs the surface
           regardless of depth.  Whales push water; that propagates up. */
        wakeStr[i] = 0.22;
        const [u, v] = worldToWaterUV(wx, wz);
        wakeUVs[i].set(u, v);

        /* Periodic ring pulse every 30 frames (staggered per whale).
           These create the expanding concentric rings that are clearly
           visible at a grazing camera angle. */
        if ((frameCount.current + i * 6) % 30 === 0) {
          _pendingBreachImpulses.push({ x: wx, z: wz, strength: 1.8 });
        }
      } else {
        wakeStr[i] = 0;
      }
    }

    /* ── Autonomous seeding: periodic random impulses ─── */
    /* Prevents the simulation from going dead when no whales are near.
       Every ~80 frames fire 2 small impulses at random ocean positions. */
    frameCount.current += 1;
    if (frameCount.current % 80 === 0) {
      for (let s = 0; s < 2; s++) {
        _pendingBreachImpulses.push({
          x:        (Math.random() - 0.5) * 200,  /* world X: -100..+100  */
          z:        (Math.random() - 0.5) * 100,  /* world Z:  -50..+50   */
          strength: 0.08,                         /* subtle ambient chop  */
        });
      }
    }

    /* ── One-shot breach ring impulses ────────────────── */
    const breachUVs = simMat.uniforms.uBreachUV.value       as THREE.Vector2[];
    const breachStr = simMat.uniforms.uBreachStrength.value  as Float32Array;
    breachStr.fill(0);
    let bi = 0;
    while (_pendingBreachImpulses.length > 0 && bi < 4) {
      const ev = _pendingBreachImpulses.pop()!;
      const [u, v] = worldToWaterUV(ev.x, ev.z);
      breachUVs[bi].set(u, v);
      /* Whale breaches get full strength 2.5; autonomous seeds get 0.08 */
      breachStr[bi] = ev.strength ?? 2.5;
      bi++;
    }

    /* ── Run simulation ───────────────────────────────── */
    simMat.uniforms.uCurrent.value  = targets[curr].texture;
    simMat.uniforms.uPrevious.value = targets[prev].texture;
    gl.setRenderTarget(targets[prev]);   /* write into the stale "previous" */
    gl.render(simScene, orthoCamera);
    gl.setRenderTarget(null);            /* always restore to canvas */
    pingPong.current = prev;             /* freshly written target is now "current" */

    /* ── Update display ───────────────────────────────── */
    displayMat.uniforms.uHeightmap.value = targets[prev].texture;
    displayMat.uniforms.uTime.value      = performance.now() * 0.001;

    /* ── Detect whale surface crossings → spawn ring ripples ── */
    for (let w = 0; w < 5; w++) {
      const wy = WHALE_SHARED_Y[w];
      const py = prevWhaleY.current[w];
      if (py > -900 && wy > -900) {
        const crossed =
          (py < SURFACE_Y && wy >= SURFACE_Y) ||
          (py >= SURFACE_Y && wy < SURFACE_Y);
        if (crossed) {
          const wx = WHALE_SHARED_XZ[w * 2];
          const wz = WHALE_SHARED_XZ[w * 2 + 1];
          const [u, v] = worldToWaterUV(wx, wz);
          const slot = ringHead.current % RING_COUNT;
          ringUVs.current[slot].set(u, v);
          ringAges.current[slot] = 0.0;
          ringHead.current++;
        }
      }
      prevWhaleY.current[w] = wy;
    }

    /* ── Age active rings + upload ────────────────────── */
    const dispRingUVs  = displayMat.uniforms.uRingUV.value  as THREE.Vector2[];
    const dispRingAges = displayMat.uniforms.uRingAge.value as Float32Array;
    for (let i = 0; i < RING_COUNT; i++) {
      if (ringAges.current[i] >= 0) {
        ringAges.current[i] += delta;
        if (ringAges.current[i] > 2.5) ringAges.current[i] = -1; /* recycle */
      }
      dispRingAges[i] = ringAges.current[i];
      dispRingUVs[i].copy(ringUVs.current[i]);
    }
  });

  return (
    <mesh
      position={[0, SURFACE_Y, -35]}
      rotation={[-Math.PI / 2, 0, 0]}
      material={displayMat}
    >
      {/* 256×128 segments — vertex displacement done entirely on GPU */}
      <planeGeometry args={[240, 90, 256, 128]} />
    </mesh>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Caustic Floor — animated light pattern plane in the background
   ═══════════════════════════════════════════════════════════════ */

function CausticFloor() {
  const groupRef = useRef<THREE.Group>(null);

  const patches = useMemo(
    () =>
      Array.from({ length: 18 }, (_, i) => ({
        x: (Math.random() - 0.5) * 120,
        y: -22 + Math.random() * 10,
        z: -40 - Math.random() * 40,
        w: 8 + Math.random() * 18,
        h: 6 + Math.random() * 14,
        speed: 0.25 + Math.random() * 0.4,
        phase: (i / 18) * Math.PI * 2,
      })),
    [],
  );

  useFrame(() => {
    if (!groupRef.current) return;
    const t = performance.now() * 0.001;
    groupRef.current.children.forEach((child, i) => {
      const p = patches[i];
      if (!p) return;
      const mesh = child as THREE.Mesh;
      const mat = mesh.material as THREE.MeshBasicMaterial;
      mat.opacity =
        0.018 + 0.014 * Math.sin(t * p.speed + p.phase);
      mesh.position.x = p.x + Math.sin(t * 0.07 + p.phase) * 3;
      mesh.scale.x = 1 + 0.15 * Math.sin(t * p.speed * 1.3 + p.phase);
      mesh.scale.y = 1 + 0.1 * Math.cos(t * p.speed + p.phase + 0.5);
    });
  });

  return (
    <group ref={groupRef}>
      {patches.map((p, i) => (
        <mesh
          key={i}
          position={[p.x, p.y, p.z]}
          rotation={[-Math.PI / 2 + 0.05, 0, Math.random() * Math.PI]}
          scale={[p.w, p.h, 1]}
        >
          <circleGeometry args={[1, 14]} />
          <meshBasicMaterial
            color={0x1a88cc}
            transparent
            opacity={0.02}
            side={THREE.DoubleSide}
            depthWrite={false}
            blending={THREE.AdditiveBlending}
          />
        </mesh>
      ))}
    </group>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Splash Particles — burst of particles at y≈22 (surface)
   ═══════════════════════════════════════════════════════════════ */

function SurfaceSplash({ count = 40 }: { count?: number }) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);

  const particles = useMemo(
    () =>
      Array.from({ length: count }, () => ({
        x: (Math.random() - 0.5) * 180,
        z: -15 - Math.random() * 50,
        phase: Math.random() * Math.PI * 2,
        speed: 0.5 + Math.random() * 1.0,
        amp: 0.5 + Math.random() * 1.0,
        size: 0.06 + Math.random() * 0.12,
      })),
    [count],
  );

  useFrame(() => {
    if (!meshRef.current) return;
    const t = performance.now() * 0.001;
    particles.forEach((p, i) => {
      const y = SURFACE_Y + Math.sin(t * p.speed + p.phase) * p.amp;
      dummy.position.set(p.x + Math.sin(t * 0.3 + p.phase) * 2, y, p.z);
      dummy.scale.setScalar(p.size);
      dummy.updateMatrix();
      meshRef.current!.setMatrixAt(i, dummy.matrix);
    });
    meshRef.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, count]}>
      <sphereGeometry args={[1, 4, 3]} />
      <meshBasicMaterial
        color={0xaaddff}
        transparent
        opacity={0.25}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </instancedMesh>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Keepalive — force continuous rendering.
   The canvas is occluded by the page content (z-10 main over z-0
   canvas). Some browsers throttle or suspend rAF for fully-covered
   canvases. This component calls invalidate() every frame to
   prevent the browser from ever throttling the WebGL context.
   ═══════════════════════════════════════════════════════════════ */

function Kickstart() {
  const { invalidate } = useThree();
  useFrame(() => invalidate());
  return null;
}

/* ═══════════════════════════════════════════════════════════════
   Camera Rig — slow cinematic drift
   ═══════════════════════════════════════════════════════════════ */

function CameraRig() {
  useFrame(({ camera }) => {
    const t = performance.now() * 0.001;
    // Gentle cinematic drift — always looking at the waterline
    camera.position.x = Math.sin(t * 0.012) * 6;
    camera.position.y = 6 + Math.sin(t * 0.018) * 1.5;
    camera.position.z = 55 + Math.sin(t * 0.009) * 4;
    // Look at a point just above the surface so the waterline is
    // always in the middle-lower third of the frame.
    camera.lookAt(0, SURFACE_Y - 2, -5);
  });

  return null;
}

/* ═══════════════════════════════════════════════════════════════
   Main Scene
   ═══════════════════════════════════════════════════════════════ */

function Scene({ whaleConfigs }: { whaleConfigs: WhaleInstance[] }) {
  return (
    <>
      <SceneSetup />
      <CameraRig />
      <Kickstart />

      {/* Environment map for PBR materials — hidden skybox */}
      <Environment preset="sunset" background={false} />

      {/* Lighting — underwater feel */}
      <ambientLight intensity={0.6} color={0x446688} />

      {/* Key light from above (sun through surface) */}
      <directionalLight
        position={[5, 40, 10]}
        intensity={1.5}
        color={0x88bbdd}
      />

      {/* Rim light for whale silhouettes */}
      <directionalLight
        position={[-10, 10, -30]}
        intensity={0.6}
        color={0x3366aa}
      />

      {/* Soft fill from below (ambient scattering) */}
      <pointLight
        position={[0, -15, -10]}
        intensity={0.3}
        color={0x224466}
        distance={80}
        decay={2}
      />

      {/* Hemisphere light — sky blue above, dark below */}
      <hemisphereLight
        args={[0x446688, 0x020810, 0.6]}
      />

      {/* God rays */}
      <GodRays count={24} />

      {/* Stars above the waterline */}
      <StarField count={1800} />
      <ShootingStars />

      {/* Whale breach splash droplets */}
      <SplashSystem />

      {/* Interactive water surface — GPU ping-pong heightfield */}
      <InteractiveWaterSurface />

      {/* Caustic floor light patches */}
      <CausticFloor />

      {/* Surface splash droplets */}
      <SurfaceSplash count={40} />

      {/* Textured GLB whales — no Suspense, each whale renders when loaded */}
      {whaleConfigs.map((cfg, i) => (
        <SwimmingWhale key={i} config={cfg} />
      ))}

      {/* Particles */}
      <Bubbles count={160} />
      <WhaleBubbleTrails />
      <FloatingParticles count={300} />
    </>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Exported Component
   ═══════════════════════════════════════════════════════════════ */

export default function OceanScene({
  className = "",
}: {
  className?: string;
}) {
  const [whaleConfigs] = useState<WhaleInstance[]>(() => {
    // Each model has different internal scale due to how it was exported.
    // blue_whale: 286× root transform, ~5 local units → ~1430 effective
    // humpback:   ~1× root transform, ~19 local units → ~19 effective
    // Target: scale 1.0 → ~20 unit whale in the scene.
    const modelNormScale: Record<string, number> = {
      "/models/blue_whale.glb": 0.014,
      "/models/humpback_whale.glb": 1.05,
      "/models/sperm_whale.glb": 1.0,
      "/models/killer_whale.glb": 1.0,
    };

    const BLUE = "/models/blue_whale.glb";
    const HUMPBACK = "/models/humpback_whale.glb";

    // Screen width at z=0 with camera at z=55, fov=55: ±62 units.
    // Rule: position[1] + bobAmp < SURFACE_Y(12) − 4 (body clearance above surface).
    //   All slots sit at position[1] ≤ −4 so the full bob stays well below water.
    // xRange ≤8: each whale sweeps a distinct ≈16-unit horizontal band.
    // zRange: depth sweep (toward/away from camera). Larger = more 3-D movement.
    const slots: (Omit<WhaleInstance, "scale"> & {
      relativeScale: number;
    })[] = [
      {
        // Blue whale A — deep background, starts centre moving right
        modelPath: BLUE,
        position: [0, -5, -30],
        relativeScale: 1.2,
        swimSpeed: 0.35,
        xRange: 65,      // patrol half-width: 65 units — well off both screen edges
        bobAmp: 2.0,
        zRange: 12,
        phase: 0,        // sin(0)=0 → centre; cos(0)=+1 → moving right
        yRot: Math.PI * 0.35,
      },
      {
        // Blue whale B — near camera, starts centre moving left (opposite A)
        modelPath: BLUE,
        position: [0, -5, 8],
        relativeScale: 1.0,
        swimSpeed: 0.3,
        xRange: 58,
        bobAmp: 2.0,
        zRange: 18,
        phase: 26,       // cos(3.12)≈−1 → moving left
        yRot: -Math.PI * 0.35,
      },
      {
        // Humpback A — deep lane (Z=-24), left-biased centre, camera charge
        modelPath: HUMPBACK,
        position: [-6, -4, -24],
        relativeScale: 1.1,
        swimSpeed: 0.55,
        xRange: 58,
        bobAmp: 2.0,
        zRange: 18,
        phase: 4,
        yRot: Math.PI * 0.35,
        initialBehaviour: "whale|camcharge",
      },
      {
        // Humpback B — mid lane (Z=-14), centred, guaranteed leap
        modelPath: HUMPBACK,
        position: [0, -4, -14],
        relativeScale: 1.3,
        swimSpeed: 0.45,
        xRange: 60,
        bobAmp: 1.8,
        zRange: 14,
        phase: 30,
        yRot: -Math.PI * 0.35,
        initialBehaviour: "whale|leap1",
      },
      {
        // Humpback C — shallow lane (Z=-5), right-biased centre, widest depth sweep
        modelPath: HUMPBACK,
        position: [6, -4, -5],
        relativeScale: 1.0,
        swimSpeed: 0.6,
        xRange: 58,
        bobAmp: 2.5,
        zRange: 22,
        phase: 50,
        yRot: Math.PI * 0.35,
        initialBehaviour: "whale|swim3",
      },
    ];

    return slots.map(({ relativeScale, ...rest }, i) => {
      const norm = modelNormScale[rest.modelPath] ?? 1.0;
      return { ...rest, scale: relativeScale * norm, whaleIndex: i };
    });
  });

  return (
    <div
      className={`pointer-events-none fixed inset-0 z-0 ${className}`}
      aria-hidden="true"
    >
      <Canvas
        frameloop="always"
        camera={{
          position: [0, 2, 60],
          fov: 55,
          near: 0.1,
          far: 400,
        }}
        dpr={[1, 1.5]}
        gl={{
          antialias: true,
          alpha: false,
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 0.8,
          powerPreference: "high-performance",
        }}
        style={{ background: "#020c1a" }}
      >
        <Scene whaleConfigs={whaleConfigs} />
      </Canvas>
    </div>
  );
}
