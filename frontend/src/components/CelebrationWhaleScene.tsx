"use client";

/**
 * 3D humpback whale scene for the celebration overlay.
 * Loads the same GLB model used on the homepage OceanScene and
 * plays a single dramatic leap/dive animation.
 *
 * Separated from CelebrationOverlay so Three.js is only loaded
 * client-side via next/dynamic (Three.js cannot be SSR'd).
 */

import { useEffect, useRef, useMemo, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import * as SkeletonUtils from "three/examples/jsm/utils/SkeletonUtils.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { GLTF } from "three/examples/jsm/loaders/GLTFLoader.js";

/* ── GLB loader with global cache ─────────────────────────── */

const cache: Record<string, GLTF> = {};
const inflight: Record<string, Promise<GLTF>> = {};

function fetchGLTF(path: string): Promise<GLTF> {
  if (!inflight[path]) {
    inflight[path] = new Promise((resolve, reject) => {
      new GLTFLoader().load(
        path,
        (g) => {
          cache[path] = g;
          resolve(g);
        },
        undefined,
        reject,
      );
    });
  }
  return inflight[path];
}

function useCachedGLTF(path: string): GLTF | null {
  const [gltf, set] = useState<GLTF | null>(
    () => cache[path] ?? null,
  );
  useEffect(() => {
    if (cache[path]) {
      set(cache[path]);
      return;
    }
    fetchGLTF(path).then(set);
  }, [path]);
  return gltf;
}

/* ── Constants ────────────────────────────────────────────── */

const MODEL_PATH = "/models/humpback_whale.glb";
const PREFERRED_CLIP = "whale|leap1";

/* ── Diving whale ─────────────────────────────────────────── */

function DivingWhale({ playing }: { playing: boolean }) {
  const groupRef = useRef<THREE.Group>(null);
  const gltf = useCachedGLTF(MODEL_PATH);
  const mixer = useRef<THREE.AnimationMixer | null>(null);
  const elapsed = useRef(0);

  /* Clone the scene so we get our own skinned-mesh instance */
  const cloned = useMemo(() => {
    if (!gltf?.scene) return null;
    const clone = SkeletonUtils.clone(gltf.scene);

    /* Boost material brightness for dark overlay background */
    clone.traverse((node) => {
      if (node instanceof THREE.Mesh && node.material) {
        const enhance = (m: THREE.Material) => {
          const mc = m.clone();
          if (mc instanceof THREE.MeshStandardMaterial) {
            mc.envMapIntensity = 4.5;
            mc.emissive = new THREE.Color(0x1a5070);
            mc.emissiveIntensity = 0.25;
          }
          return mc;
        };
        if (Array.isArray(node.material)) {
          node.material = node.material.map(enhance);
        } else {
          node.material = enhance(node.material);
        }
      }
    });
    return clone;
  }, [gltf]);

  /* Set up animation — play one dramatic leap/dive */
  useEffect(() => {
    if (!cloned || !gltf?.animations?.length || !playing) return;

    elapsed.current = 0;
    const m = new THREE.AnimationMixer(cloned);
    mixer.current = m;

    const clip =
      gltf.animations.find((c) => c.name === PREFERRED_CLIP) ??
      gltf.animations.find((c) => c.name.includes("leap")) ??
      gltf.animations[0];

    const action = m.clipAction(clip, cloned);
    action.setLoop(THREE.LoopOnce, 1);
    action.clampWhenFinished = true;
    action.timeScale = 0.3;
    action.play();

    return () => {
      m.stopAllAction();
      mixer.current = null;
    };
  }, [cloned, gltf, playing]);

  /*
   * Per-frame: the whale travels one full arc through the
   * entire screen height alongside its GLB leap animation.
   * Path: center → dive to bottom → arc up to top → settle
   * back to center. Uses a sine curve over ~12s so the
   * journey feels natural and ends where it started.
   */
  useFrame((_, delta) => {
    if (!groupRef.current || !playing) return;
    mixer.current?.update(delta);
    elapsed.current += delta;

    const t = elapsed.current;
    /* One full sine cycle over ~12s, then hold at 0 */
    const period = 12;
    const progress = Math.min(t / period, 1);
    const arc = Math.sin(progress * Math.PI * 2) * 35;

    groupRef.current.position.y = arc;

    /* Nose pitches in direction of vertical travel */
    const velocityY =
      Math.cos(progress * Math.PI * 2) * 0.4;
    groupRef.current.rotation.x =
      -0.15 + (progress < 1 ? velocityY : 0);

    /* Slow rotation so viewer sees the whale from multiple angles */
    groupRef.current.rotation.y =
      0.3 + Math.sin(t * 0.15) * 0.3;
  });

  if (!cloned) return null;

  return (
    <group
      ref={groupRef}
      position={[0, 0, 0]}
      rotation={[-0.15, 0.3, 0]}
      scale={[2.4, 2.4, 2.4]}
    >
      <primitive object={cloned} dispose={null} />
    </group>
  );
}

/* ── Exported scene (Canvas wrapper) ──────────────────────── */

export default function CelebrationWhaleScene({
  playing,
}: {
  playing: boolean;
}) {
  return (
    <Canvas
      gl={{ alpha: true, antialias: true }}
      camera={{
        position: [0, 0, 50],
        fov: 80,
        near: 0.1,
        far: 300,
      }}
      style={{ background: "transparent" }}
    >
      {/* Lighting — bright ocean feel */}
      <ambientLight intensity={0.9} color="#88bbdd" />
      <directionalLight
        position={[5, 12, 8]}
        intensity={3.0}
        color="#aaddff"
      />
      <directionalLight
        position={[-4, -3, 3]}
        intensity={1.0}
        color="#4488bb"
      />
      <pointLight
        position={[0, 2, 15]}
        intensity={1.5}
        color="#88ddff"
        distance={60}
      />
      <pointLight
        position={[-3, 8, 5]}
        intensity={0.8}
        color="#99ccee"
        distance={50}
      />

      {/* Depth fog — pushed back so whale stays bright */}
      <fog attach="fog" args={[0x031525, 80, 200]} />

      <DivingWhale playing={playing} />
    </Canvas>
  );
}
